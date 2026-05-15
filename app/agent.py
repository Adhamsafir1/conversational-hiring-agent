"""Core conversational agent for SHL Assessment Recommender."""
import json
import logging
import re
import time

import google.generativeai as genai
from groq import Groq

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
        results = retriever.search(query, top_k=20)
        return "\n".join(
            f"{i}. {retriever.format_product_for_context(product)}"
            for i, product in enumerate(results, 1)
        )

    def _parse_llm_response(self, raw_text: str) -> ChatResponse:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
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

        reply = data.get("reply", "")
        end_of_conv = data.get("end_of_conversation", False)
        recs = []
        raw_recs = data.get("recommendations", [])
        if raw_recs and isinstance(raw_recs, list):
            for r in raw_recs:
                if isinstance(r, dict) and "name" in r and "url" in r:
                    recs.append(
                        Recommendation(
                            name=r["name"],
                            url=r["url"],
                            test_type=r.get("test_type", "K"),
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

    def _generate_llm_text(
        self,
        system_prompt: str,
        messages: list[Message],
    ) -> str | None:
        """Try Groq (primary + fallback model), then Gemini (primary + fallback)."""
        for model in (GROQ_MODEL, GROQ_FALLBACK_MODEL):
            if model and self.groq_clients:
                text = self._try_groq(system_prompt, messages, model)
                if text:
                    return text

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

        recs = [
            Recommendation(
                name=p["name"],
                url=p.get("link", ""),
                test_type=keys_to_test_type(p.get("keys", [])),
            )
            for p in results[:8]
            if p.get("link")
        ]

        return ChatResponse(
            reply=(
                "Our AI providers are briefly rate-limited, so this reply uses "
                "**semantic search** over the official SHL catalog (all links verified). "
                "For clarifying questions and refinements like the sample conversations, "
                "please retry in a minute — or continue refining from this shortlist.\n\n"
                f"Based on your description, here are {len(recs)} relevant assessments:"
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
