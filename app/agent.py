"""Core conversational agent for SHL Assessment Recommender."""
import json
import re
import time
import logging
import google.generativeai as genai
from groq import Groq
from app.config import GROQ_API_KEYS, GROQ_MODEL, GEMINI_API_KEYS, GEMINI_MODEL, MAX_TURNS
from app.models import ChatRequest, ChatResponse, Recommendation, Message
from app.retriever import retriever
from app.prompts import build_system_prompt

logger = logging.getLogger(__name__)


class SHLAgent:
    """Conversational agent that recommends SHL assessments."""

    def __init__(self):
        # Initialize Groq clients
        self.groq_clients = []
        for key in GROQ_API_KEYS:
            self.groq_clients.append(Groq(api_key=key))
        
        # Initialize Gemini models
        self.gemini_clients = []
        for key in GEMINI_API_KEYS:
            genai.configure(api_key=key)
            self.gemini_clients.append(genai.GenerativeModel(GEMINI_MODEL))

        if not self.groq_clients and not self.gemini_clients:
            logger.error("CRITICAL: No API keys found for any LLM provider!")
        else:
            logger.info(f"Initialized with {len(self.groq_clients)} Groq keys and {len(self.gemini_clients)} Gemini keys.")
        
        self._catalog_loaded = False

    def _ensure_catalog(self):
        """Ensure the catalog and retriever are loaded."""
        if not self._catalog_loaded:
            retriever.load()
            self._catalog_loaded = True

    def _extract_query_from_conversation(self, messages: list[Message]) -> str:
        """Extract a search query from the full conversation history.
        
        Combines all user messages to build a comprehensive search query,
        giving more weight to recent messages.
        """
        user_messages = [m.content for m in messages if m.role == "user"]
        if not user_messages:
            return ""

        # Use all user messages, but emphasize the latest
        if len(user_messages) == 1:
            return user_messages[0]

        # Combine: give recent messages more presence
        recent = user_messages[-1]
        earlier = " ".join(user_messages[:-1])
        return f"{recent} | Context: {earlier}"

    def _get_catalog_context(self, messages: list[Message]) -> str:
        """Retrieve relevant catalog items based on the conversation."""
        query = self._extract_query_from_conversation(messages)
        if not query:
            return "No query provided."

        # Retrieve top-K relevant products
        results = retriever.search(query, top_k=20)

        # Format for the prompt
        formatted = []
        for i, product in enumerate(results, 1):
            formatted.append(
                f"{i}. {retriever.format_product_for_context(product)}"
            )

        return "\n".join(formatted)

    def _parse_llm_response(self, raw_text: str) -> ChatResponse:
        """Parse LLM response text into a ChatResponse, handling malformed JSON."""
        # Try to extract JSON from the response
        text = raw_text.strip()
        
        # Remove markdown code fences if present
        if text.startswith("```"):
            # Remove opening fence (with optional language tag)
            text = re.sub(r'^```\w*\n?', '', text)
            # Remove closing fence
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON object in the text
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    # Fallback: return the raw text as reply
                    logger.warning(f"Failed to parse LLM response as JSON: {text[:200]}")
                    return ChatResponse(
                        reply=raw_text,
                        recommendations=[],
                        end_of_conversation=False,
                    )
            else:
                return ChatResponse(
                    reply=raw_text,
                    recommendations=[],
                    end_of_conversation=False,
                )

        # Build response
        reply = data.get("reply", "")
        end_of_conv = data.get("end_of_conversation", False)

        # Parse recommendations
        recs = []
        raw_recs = data.get("recommendations", [])
        if raw_recs and isinstance(raw_recs, list):
            for r in raw_recs:
                if isinstance(r, dict) and "name" in r and "url" in r:
                    recs.append(Recommendation(
                        name=r["name"],
                        url=r["url"],
                        test_type=r.get("test_type", "K"),
                    ))

        return ChatResponse(
            reply=reply,
            recommendations=recs,
            end_of_conversation=end_of_conv,
        )

    def _validate_recommendations(self, response: ChatResponse) -> ChatResponse:
        """Validate that all recommendations have valid catalog URLs."""
        if not response.recommendations:
            return response

        valid_urls = {p.get("link", "") for p in retriever.catalog}
        valid_names = {p.get("name", "").lower() for p in retriever.catalog}

        validated_recs = []
        for rec in response.recommendations:
            # Check URL validity
            if rec.url in valid_urls:
                validated_recs.append(rec)
            else:
                # Try to find by name and fix URL
                product = retriever.get_by_name(rec.name)
                if product:
                    validated_recs.append(Recommendation(
                        name=product["name"],
                        url=product.get("link", rec.url),
                        test_type=rec.test_type,
                    ))
                elif rec.name.lower() in valid_names:
                    # Name matches but URL doesn't — find and fix
                    for p in retriever.catalog:
                        if p["name"].lower() == rec.name.lower():
                            validated_recs.append(Recommendation(
                                name=p["name"],
                                url=p.get("link", rec.url),
                                test_type=rec.test_type,
                            ))
                            break
                else:
                    logger.warning(f"Dropping recommendation with invalid catalog entry: {rec.name}")

        response.recommendations = validated_recs
        return response

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Process a chat request and return the agent's response."""
        self._ensure_catalog()

        messages = request.messages

        # Check turn count — if we're near the limit, force a recommendation
        total_turns = len(messages)  # Current turns in history
        is_near_limit = total_turns >= MAX_TURNS - 2  # Leave room for response

        # Get catalog context based on conversation
        catalog_context = self._get_catalog_context(messages)
        system_prompt = build_system_prompt(catalog_context, len(retriever.catalog))

        if is_near_limit:
            system_prompt += (
                "\n\nIMPORTANT: The conversation is approaching the turn limit. "
                "You MUST provide your best recommendations NOW based on what you know. "
                "Do not ask more questions."
            )

        raw_text = None
        
        # 1. Try Groq clients first
        for i, client in enumerate(self.groq_clients):
            try:
                # Build messages for Groq (OpenAI-compatible format)
                groq_messages = [{"role": "system", "content": system_prompt}]
                for msg in messages:
                    groq_messages.append({"role": msg.role, "content": msg.content})

                response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=groq_messages,
                    temperature=0.3,
                    max_tokens=2048,
                )
                raw_text = response.choices[0].message.content
                logger.info(f"Response successfully generated using Groq client {i+1}.")
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    logger.warning(f"Groq client {i+1} rate limited. Trying next provider...")
                    continue
                else:
                    logger.error(f"Groq client {i+1} failed with error: {e}")
                    continue

        # 2. Fallback to Gemini if Groq failed
        if raw_text is None:
            logger.info("Falling back to Gemini providers...")
            for i, model in enumerate(self.gemini_clients):
                try:
                    # Gemini prompt
                    prompt = f"{system_prompt}\n\nConversation History:\n"
                    for msg in messages:
                        prompt += f"{msg.role}: {msg.content}\n"
                    
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.GenerationConfig(
                            temperature=0.3,
                            max_output_tokens=2048,
                        )
                    )
                    raw_text = response.text
                    logger.info(f"Response successfully generated using Gemini client {i+1}.")
                    break
                except Exception as e:
                    logger.error(f"Gemini client {i+1} failed: {e}")
                    continue

        if raw_text is None:
            logger.error("All LLM providers and keys failed!")
            return ChatResponse(
                reply="I apologize, but all my AI brains are currently busy or rate-limited. Please try again in a few minutes.",
                recommendations=[],
                end_of_conversation=False,
            )

        # Parse and validate
        chat_response = self._parse_llm_response(raw_text)
        chat_response = self._validate_recommendations(chat_response)

        return chat_response


# Singleton
agent = SHLAgent()
