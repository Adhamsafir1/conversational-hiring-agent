"""Core conversational agent for SHL Assessment Recommender."""
import json
import logging
import re
import time
import os

import google.generativeai as genai
from groq import Groq
from huggingface_hub import InferenceClient

from app.config import (
    ENABLE_RETRIEVAL_FALLBACK,
    GEMINI_API_KEYS,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MODEL,
    GROQ_API_KEYS,
    GROQ_FALLBACK_MODEL,
    GROQ_MODEL,
    LLM_MAX_RETRIES,
    LLM_RETRY_BASE_DELAY,
    MAX_TURNS,
    HF_MODEL_NAMES,
)
from app.llm_utils import (
    CLARIFY_GREETING_REPLY,
    call_with_retries,
    is_greeting_only,
    is_rate_limited_error,
    keys_to_test_type,
)
from app.models import ChatRequest, ChatResponse, Message, Recommendation
from app.prompts import build_system_prompt
from app.retriever import retriever

logger = logging.getLogger(__name__)


class SHLAgent:
    """Conversational agent that recommends SHL assessments."""

    def __init__(self):
        self.groq_clients = [Groq(api_key=key) for key in GROQ_API_KEYS]
        self.gemini_api_keys = list(GEMINI_API_KEYS)

        if not self.groq_clients and not self.gemini_api_keys:
            logger.error("CRITICAL: No API keys found for any LLM provider!")
        else:
            logger.info(
                "Initialized with %s Groq key(s) and %s Gemini key(s).",
                len(self.groq_clients),
                len(self.gemini_api_keys),
            )

        self._catalog_loaded = False

    def _ensure_catalog(self):
        if not self._catalog_loaded:
            retriever.load()
            self._catalog_loaded = True

    def _extract_query_from_conversation(self, messages: list[Message]) -> str:
        user_messages = [m.content for m in messages if m.role == "user"]
        if not user_messages:
            return ""
        if len(user_messages) == 1:
            return user_messages[0]
        recent = user_messages[-1]
        earlier = " ".join(user_messages[:-1])
        return f"{recent} | Context: {earlier}"

    def _get_catalog_context(self, messages: list[Message]) -> str:
        query = self._extract_query_from_conversation(messages)
        if not query:
            return "No query provided."
        
        results = retriever.search(query, top_k=40)
        
        # Always ensure core/proxy tests are in the context if available
        core_test_names = ["Smart Interview Live Coding", "SHL Verify Interactive G+", "Occupational Personality Questionnaire OPQ32r"]
        existing_names = {p.get("name") for p in results}
        
        for core_name in core_test_names:
            if core_name not in existing_names:
                core_product = retriever.get_by_name(core_name)
                if core_product:
                    results.append(core_product)

        return "\n".join(
            f"{i}. {retriever.format_product_for_context(product)}"
            for i, product in enumerate(results, 1)
        )

    def _parse_llm_response(self, raw_text: str) -> ChatResponse:
        """Parse the LLM response, handling common formatting errors and unescaped newlines."""
        text = raw_text.strip()
        
        # 1. Clean markdown blocks
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        # 2. Extract JSON block
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1:
            return ChatResponse(reply=raw_text, recommendations=[], end_of_conversation=False)
        
        json_str = text[start:end+1]

        # 3. Attempt direct parse
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # 4. Fix unescaped newlines in 'reply' string
            # This regex finds the content between "reply": " and the next quote before a structural char
            try:
                # Replace actual newlines with \n characters inside the reply value
                def fix_reply(match):
                    content = match.group(2)
                    fixed = content.replace("\n", "\\n").replace("\r", "\\r")
                    return f'{match.group(1)}"{fixed}"'

                # Targeted regex for the reply field
                json_str = re.sub(r'("reply"\s*:\s*)"([\s\S]*?)"(?=\s*,\s*"recommendations")', fix_reply, json_str)
                data = json.loads(json_str)
            except:
                # 5. Fallback: try to strip all literal newlines and hope for the best
                try:
                    fixed_str = re.sub(r'\n', ' ', json_str)
                    data = json.loads(fixed_str)
                except:
                    return ChatResponse(reply=raw_text, recommendations=[], end_of_conversation=False)

        reply = data.get("reply", "")
        end_of_conv = data.get("end_of_conversation", False)
        recs = []
        raw_recs = data.get("recommendations", [])
        if raw_recs and isinstance(raw_recs, list):
            for r in raw_recs:
                if isinstance(r, dict) and "name" in r and "url" in r:
                    langs = r.get("languages", "English")
                    if isinstance(langs, list):
                        langs = ", ".join(langs)
                    recs.append(
                        Recommendation(
                            name=r["name"],
                            url=r["url"],
                            test_type=r.get("test_type", "Knowledge"),
                            duration=r.get("duration", "Variable"),
                            languages=str(langs),
                        )
                    )

        return ChatResponse(
            reply=reply,
            recommendations=recs,
            end_of_conversation=end_of_conv,
        )

    def _validate_recommendations(self, response: ChatResponse) -> ChatResponse:
        if not response.recommendations:
            return response

        valid_urls = {p.get("link", "") for p in retriever.catalog}
        valid_names = {p.get("name", "").lower() for p in retriever.catalog}
        validated_recs = []

        for rec in response.recommendations:
            if rec.url in valid_urls:
                validated_recs.append(rec)
            else:
                product = retriever.get_by_name(rec.name)
                if product:
                    validated_recs.append(
                        Recommendation(
                            name=product["name"],
                            url=product.get("link", rec.url),
                            test_type=rec.test_type,
                            duration=product.get("duration", rec.duration),
                            languages=", ".join(product["languages"]) if isinstance(product.get("languages"), list) else str(product.get("languages", rec.languages)),
                        )
                    )
                elif rec.name.lower() in valid_names:
                    for p in retriever.catalog:
                        if p["name"].lower() == rec.name.lower():
                            validated_recs.append(
                                Recommendation(
                                    name=p["name"],
                                    url=p.get("link", rec.url),
                                    test_type=rec.test_type,
                                    duration=p.get("duration", rec.duration),
                                    languages=p.get("languages", rec.languages),
                                )
                            )
                            break
                else:
                    logger.warning(
                        "Dropping recommendation with invalid catalog entry: %s",
                        rec.name,
                    )

        response.recommendations = validated_recs
        return response

    def _try_groq(
        self,
        system_prompt: str,
        messages: list[Message],
        model: str,
    ) -> str | None:
        groq_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            groq_messages.append({"role": msg.role, "content": msg.content})

        for i, client in enumerate(self.groq_clients):
            label = f"Groq/{model}/key{i + 1}"

            def _call(c=client) -> str:
                response = c.chat.completions.create(
                    model=model,
                    messages=groq_messages,
                    temperature=0.3,
                    max_tokens=2048,
                )
                return response.choices[0].message.content

            try:
                result = call_with_retries(_call, label)
                if result:
                    logger.info("Response from %s", label)
                    return result
            except Exception as e:
                if is_rate_limited_error(e):
                    logger.warning("%s rate limited", label)
                else:
                    logger.error("%s failed: %s", label, e)
        return None

    def _try_gemini(
        self,
        system_prompt: str,
        messages: list[Message],
        model_name: str,
    ) -> str | None:
        prompt = f"{system_prompt}\n\nConversation History:\n"
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n"

        for i, api_key in enumerate(self.gemini_api_keys):
            label = f"Gemini/{model_name}/key{i + 1}"

            def _call(key=api_key, model=model_name) -> str:
                genai.configure(api_key=key)
                model_client = genai.GenerativeModel(model)
                response = model_client.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        max_output_tokens=2048,
                    ),
                )
                return response.text

            try:
                result = call_with_retries(_call, label)
                if result:
                    logger.info("Response from %s", label)
                    return result
            except Exception as e:
                if is_rate_limited_error(e):
                    logger.warning("%s rate limited", label)
                else:
                    logger.error("%s failed: %s", label, e)
        return None

    def _try_hf(self, system_prompt: str, messages: list[Message], model_name: str) -> str | None:
        """Attempt to get a response from a HuggingFace model via InferenceClient."""
        hf_messages = []
        if messages and messages[0].role == "user":
            hf_messages.append({
                "role": "user", 
                "content": f"{system_prompt}\n\nUser: {messages[0].content}"
            })
            for msg in messages[1:]:
                hf_messages.append({"role": msg.role, "content": msg.content})
        else:
            hf_messages.append({"role": "system", "content": system_prompt})
            for msg in messages:
                hf_messages.append({"role": msg.role, "content": msg.content})

        token = os.getenv("HF_TOKEN") or os.getenv("HF_API_TOKEN")
        client = InferenceClient(token=token) if token else InferenceClient()
        label = f"HF/{model_name}"

        def _call() -> str:
            response = client.chat_completion(
                model=model_name,
                messages=hf_messages,
                max_tokens=2048,
            )
            return response.choices[0].message.content

        try:
            result = call_with_retries(_call, label)
            if result:
                logger.info("Response from %s", label)
                return result
        except Exception as e:
            logger.error("%s failed: %s", label, e)
        return None

    def _generate_llm_text(
        self,
        system_prompt: str,
        messages: list[Message],
    ) -> str | None:
        """Try HuggingFace → Groq → Gemini in order, returning first successful response."""
        # 1. Try HuggingFace models (Primary)
        for hf_model in HF_MODEL_NAMES:
            logger.info("Trying HuggingFace model: %s", hf_model)
            text = self._try_hf(system_prompt, messages, hf_model)
            if text:
                return text

        # 2. Try Groq (primary + fallback model)
        for model in (GROQ_MODEL, GROQ_FALLBACK_MODEL):
            if model and self.groq_clients:
                text = self._try_groq(system_prompt, messages, model)
                if text:
                    return text

        # 3. Try Gemini (primary + fallback model)
        for model in (GEMINI_MODEL, GEMINI_FALLBACK_MODEL):
            if model and self.gemini_api_keys:
                text = self._try_gemini(system_prompt, messages, model)
                if text:
                    return text

        return None

    def _retrieval_fallback(self, messages: list[Message]) -> ChatResponse:
        """Grounded shortlist from FAISS when LLM providers are unavailable."""
        last_user = messages[-1].content if messages else ""

        if is_greeting_only(last_user):
            return ChatResponse(
                reply=CLARIFY_GREETING_REPLY,
                recommendations=[],
                end_of_conversation=False,
            )

        query = self._extract_query_from_conversation(messages)
        results = retriever.search(query, top_k=8)
        if not results:
            return ChatResponse(
                reply=(
                    "I'm temporarily unable to reach the language model. "
                    "Please try again in a few minutes, or describe the role "
                    "and skills you need to assess."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        recs = []
        for p in results[:8]:
            if not p.get("link"):
                continue
            
            langs = p.get("languages", "English")
            if isinstance(langs, list):
                langs = ", ".join(langs)
                
            recs.append(
                Recommendation(
                    name=p["name"],
                    url=p.get("link", ""),
                    test_type=keys_to_test_type(p.get("keys", [])),
                    duration=p.get("duration", "Variable"),
                    languages=str(langs),
                )
            )

        return ChatResponse(
            reply=(
                "Our AI providers are currently experiencing high traffic, so I've used our internal **semantic search** to find the most relevant assessments for you. "
                "For a role like this, I have prioritized a mix of **Ability** (reasoning) and **Personality/Safety** instruments (to predict reliability and rule compliance). "
                "Once the AI is back in a moment, we can refine this list further or add specific technical knowledge checks!"
            ),
            recommendations=recs,
            end_of_conversation=False,
        )

    def chat(self, request: ChatRequest) -> ChatResponse:
        self._ensure_catalog()
        messages = request.messages

        if messages and is_greeting_only(messages[-1].content):
            return ChatResponse(
                reply=CLARIFY_GREETING_REPLY,
                recommendations=[],
                end_of_conversation=False,
            )

        total_turns = len(messages)
        is_near_limit = total_turns >= MAX_TURNS - 2
        catalog_context = self._get_catalog_context(messages)
        system_prompt = build_system_prompt(catalog_context, len(retriever.catalog))

        if is_near_limit:
            system_prompt += (
                "\n\nIMPORTANT: The conversation is approaching the turn limit. "
                "You MUST provide your best recommendations NOW based on what you know. "
                "Do not ask more questions."
            )

        raw_text = self._generate_llm_text(system_prompt, messages)

        if raw_text is None:
            logger.error("All LLM providers and keys failed.")
            if ENABLE_RETRIEVAL_FALLBACK:
                logger.info("Using retrieval fallback response.")
                return self._validate_recommendations(
                    self._retrieval_fallback(messages)
                )
            return ChatResponse(
                reply=(
                    "I apologize — all configured LLM API keys are rate-limited or unavailable. "
                    "Please try again in a few minutes, or ask the space owner to refresh "
                    "Groq/Gemini keys in HuggingFace Secrets."
                ),
                recommendations=[],
                end_of_conversation=False,
            )

        chat_response = self._parse_llm_response(raw_text)
        return self._validate_recommendations(chat_response)


agent = SHLAgent()
