# SHL Conversational Hiring Agent — Assignment Report

**Author:** Adham Safir  
**Repository:** [github.com/Adhamsafir1/conversational-hiring-agent](https://github.com/Adhamsafir1/conversational-hiring-agent)  
**Live Demo:** [huggingface.co/spaces/adhamsafir/conversational-hiring-agent](https://huggingface.co/spaces/adhamsafir/conversational-hiring-agent)  
**Date:** May 2026

---

## 1. Executive Summary

This project delivers a **conversational AI hiring agent** that acts as a strategic SHL assessment consultant. Given a job description (JD), the agent engages the hiring manager in a structured multi-turn dialogue — narrowing broad requirements, asking informed follow-up questions about seniority and ownership, then producing a focused, predictive assessment battery drawn from the official SHL product catalog (377+ assessments).

The agent goes beyond simple keyword matching. It reasons about role focus, seniority level, and test complementarity, then renders results as interactive UI cards with verified catalog links.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Chat UI)                       │
│            index.html  ·  chat.js  ·  chat.css              │
└───────────────────────────┬─────────────────────────────────┘
                            │  POST /chat  (full history)
┌───────────────────────────▼─────────────────────────────────┐
│              FastAPI  (app/main.py)                         │
│         Stateless REST API  ·  /chat  ·  /health            │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              SHLAgent  (app/agent.py)                       │
│                                                             │
│  ┌─────────────────────┐   ┌─────────────────────────────┐  │
│  │  Semantic Retriever │   │      LLM Fallback Chain     │  │
│  │  FAISS + MiniLM-L6  │   │  HF → Groq → Gemini        │  │
│  │  Top-40 retrieval   │   │  (Multi-key rotation)       │  │
│  └────────┬────────────┘   └──────────────┬──────────────┘  │
│           │ Catalog Context               │ JSON Response    │
│           └──────────────┬────────────────┘                  │
│                          │                                   │
│              ┌───────────▼──────────┐                        │
│              │  Bulletproof Parser  │                        │
│              │  (Regex JSON Rescue) │                        │
│              └───────────┬──────────┘                        │
│                          │                                   │
│              ┌───────────▼──────────┐                        │
│              │  Pydantic Validator  │                        │
│              │  ChatResponse model  │                        │
│              └──────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

| File | Role |
|---|---|
| `app/main.py` | FastAPI server; stateless `/chat` endpoint; `/health` check |
| `app/agent.py` | Core agent: LLM orchestration, JSON parsing, validation, RAG fallback |
| `app/retriever.py` | FAISS-based semantic search over SHL catalog |
| `app/prompts.py` | Strategic consultant system prompt (principled, rule-driven) |
| `app/models.py` | Pydantic data models: `Message`, `ChatRequest`, `ChatResponse`, `Recommendation` |
| `app/config.py` | Environment-driven configuration; multi-key rotation support |
| `app/llm_utils.py` | Shared utilities: retry logic, rate-limit detection, test-type mapping |
| `app/static/` | Vanilla HTML/CSS/JS chat UI with dynamic assessment cards |

---

## 3. Key Features

### 3.1 Multi-Turn Conversational Consulting

The agent follows a structured five-step consulting process:

1. **Count & Diagnose** — On Turn 1, it explicitly counts distinct technical areas in the JD. If there are 5 or more, it explains the candidate-fatigue risk and asks a JD-specific narrowing question ("Is this backend-leaning or a true balanced full-stack role?"). **No cards are shown yet.**

2. **Clarify Seniority** — On Turn 2, it acknowledges the user's answer and asks a targeted seniority question ("Senior IC leading design on one service, or Tech Lead setting architecture across teams?"). **Still no cards.**

3. **Strategic Recommendation** — Once the role is focused, it selects 3–5 technical tests matching confirmed Day-1 priorities, and **always proactively adds Verify G+** (cognitive) and **OPQ32r** (personality) for senior/professional roles, explaining the rationale.

4. **Refine** — Accepts precise add/drop commands ("add Docker", "drop REST") while persisting all other items in the shortlist.

5. **Finalize** — On user confirmation, writes a one-sentence summary of the battery and sets `end_of_conversation: true`.

### 3.2 RAG-Powered Catalog Retrieval

- **Embedding Model:** `all-MiniLM-L6-v2` (sentence-transformers)
- **Vector Store:** FAISS with cosine similarity (`IndexFlatIP` on normalized embeddings)
- **Retrieval Strategy:** Top-40 semantic search injected into the LLM context window
- **Enriched Indexing:** Each product is indexed with enriched text including name, description, key type descriptions, job levels, and duration

### 3.3 Multi-Provider LLM with Token Rotation

The agent uses a waterfall fallback strategy to maximize uptime:

```
HuggingFace (Qwen/Qwen2.5-7B → Llama-3.2-1B)
    ↓ (if 402/429)
Groq (llama-3.3-70b-versatile → llama-3.1-8b-instant)
    ↓ (if 429)
Gemini (gemini-2.0-flash → gemini-1.5-flash)
    ↓ (if all fail)
Semantic Search Emergency Fallback
```

Each provider supports **comma-separated multi-key rotation** via environment variables (`GROQ_API_KEYS`, `GEMINI_API_KEYS`, `HF_TOKENS`), so a single exhausted key does not stop the service.

### 3.4 Bulletproof JSON Parser

LLMs occasionally produce malformed JSON (unescaped newlines, extra brackets). The agent has a three-layer defense:

1. **Direct parse** — `json.loads()` on the extracted JSON block.
2. **Reply-field healing** — Regex targets the `reply` field and escapes raw newlines without touching the structured `recommendations` array.
3. **Emergency rescue** — If the JSON is completely broken (e.g., `[ { {`), a regex extractor pulls the readable `reply` text and scans for valid SHL catalog URLs, then rebuilds the `Recommendation` objects from the live catalog.

This guarantees the UI **never** shows raw JSON to the user.

### 3.5 Dynamic Assessment Card UI

The frontend renders each assessment as a rich card with:
- Color-coded test type badges (K = Knowledge, P = Personality, A = Ability, S = Simulation)
- Duration, language support, and a verified "View Assessment" link
- Live filter bar (search by name) and type filter dropdown
- Smooth CSS animations and a premium dark-mode design

---

## 4. Technical Stack

| Layer | Technology |
|---|---|
| **API Server** | FastAPI 0.136 + Uvicorn |
| **Data Validation** | Pydantic v2 |
| **LLM Providers** | HuggingFace Inference API, Groq, Google Gemini |
| **Embeddings** | `sentence-transformers` (all-MiniLM-L6-v2) |
| **Vector Search** | FAISS (faiss-cpu) |
| **Frontend** | Vanilla HTML5, CSS3, JavaScript (no framework) |
| **Markdown Rendering** | marked.js |
| **Deployment** | Hugging Face Spaces (Docker) |
| **Config Management** | python-dotenv |
| **Testing** | pytest + httpx |

---

## 5. API Reference

### `POST /chat`

The single, stateless conversational endpoint. The client sends the **full conversation history** on every call.

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "We're hiring a Senior Java Engineer..."},
    {"role": "assistant", "content": "...previous response..."},
    {"role": "user", "content": "Backend-leaning, Senior IC."}
  ]
}
```

**Response Body:**
```json
{
  "reply": "Understood. Here is a focused battery for a Senior IC...",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "Knowledge",
      "duration": "13 minutes",
      "languages": "English (USA)"
    }
  ],
  "end_of_conversation": false
}
```

### `GET /health`

Returns the count of configured API keys and whether the LLM is ready.

---

## 6. Deployment

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in GROQ_API_KEYS, GEMINI_API_KEYS, HF_TOKENS

# Start server
python -m uvicorn app.main:app --port 8000 --reload
```

### Hugging Face Spaces

The project includes a `Dockerfile`. Add the following **Secrets** in the HF Space Settings panel:

| Secret Name | Value |
|---|---|
| `HF_TOKENS` | Comma-separated HF read tokens |
| `GROQ_API_KEYS` | Comma-separated Groq API keys |
| `GEMINI_API_KEYS` | Comma-separated Gemini API keys |
| `LLM_PROVIDER` | `huggingface` |
| `HF_MODEL_NAME` | `Qwen/Qwen2.5-7B-Instruct,meta-llama/Llama-3.2-1B-Instruct` |

---

## 7. Design Decisions & Tradeoffs

### Stateless API
The `/chat` endpoint receives the full conversation history on every request. This simplifies horizontal scaling (no server-side session storage) and matches the pattern of OpenAI's Chat Completions API.

### RAG over Fine-tuning
The SHL catalog changes over time. A FAISS-based retrieval system stays current by simply replacing `catalog_clean.json`; no model retraining is required. Top-40 retrieval gives the LLM a focused context window without exceeding token limits.

### Multi-Key Rotation
Free-tier API quotas are the primary reliability risk for a demo deployment. Supporting N comma-separated keys per provider allows the system to distribute load and survive individual key exhaustion without manual intervention.

### Principled Prompt over Few-Shot Examples
Hardcoding specific JDs and test names in the prompt creates a brittle system. A principled, rule-driven prompt ("count areas", "ask about seniority", "never list names in reply") generalizes to any role type — technical, frontline, executive, or administrative — without needing new examples for every scenario.

---

## 8. Known Limitations & Future Work

| Area | Current Limitation | Future Improvement |
|---|---|---|
| **LLM Reliability** | Free-tier credits deplete; model quality varies | Switch to a paid production API or self-hosted Ollama |
| **Catalog Freshness** | Static JSON snapshot of the SHL catalog | Scheduled crawler to keep catalog up-to-date |
| **Conversation Memory** | Full history grows unboundedly | Implement sliding window summarization for long chats |
| **UI Interactions** | Cards cannot be dropped from the UI directly | Add a "Remove" button on each card |
| **Analytics** | No logging of recommendations | Add a database to track recommendation patterns |

---

## 9. Sample Conversation Alignment (C9 Reference)

| Turn | Expected Behavior | Agent Behavior |
|---|---|---|
| T1 — Broad JD (7 areas) | Count areas, ask Backend/Frontend focus, **empty cards** | ✅ Counts, narrows, no cards |
| T2 — "Backend-leaning" | Ask seniority (Senior IC vs Tech Lead), **empty cards** | ✅ Asks seniority, no cards |
| T3 — "Senior IC" | Recommend 4–6 tests incl. Verify G+ + OPQ32r | ✅ Full battery with cards |
| T4 — "Add AWS, drop REST" | Update shortlist precisely, persist all others | ✅ Precise add/drop |
| T5 — Justify a test choice | Explain rationale, keep list unchanged | ✅ Reasoning + persistent cards |
| T7 — "Lock it in" | Final summary, `end_of_conversation: true` | ✅ Closes gracefully |

---

*Report generated for the SHL GenAI Engineer Assessment — May 2026*
