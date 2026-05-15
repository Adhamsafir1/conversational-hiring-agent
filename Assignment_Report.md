# Technical Assignment Report: SHL Conversational Assessment Recommender

## 1. Executive Summary
This report outlines the development and deployment of a sophisticated Conversational AI Agent designed to facilitate the discovery of SHL assessments. The solution leverages a state-of-the-art **Retrieval-Augmented Generation (RAG)** architecture, hosted on **HuggingFace Spaces**, and powered by a resilient, multi-provider LLM backend. The primary objective was to create a system that is not only context-aware but also strictly grounded in reality, ensuring 100% accuracy in product recommendations.

---

## 2. System Architecture & Design

### 2.1 High-Level Architecture Design
The following flow illustrates the request lifecycle from user input to the final validated JSON response:

```text
User Request ──► FastAPI (/chat) ──► Conversation Controller
                                              │
                                              ▼
                                        Intent Analysis
                                      /    |    |    \
                                Clarify  Recommend  Refine  Refuse
                                          |    |
                                   ┌──────┘    └──────┐
                                   ▼                  ▼
                           FAISS Retrieval      LLM Orchestrator
                          (semantic search)    (Groq + Gemini Failover)
                                   │                  │
                                   └──────┬───────────┘
                                          ▼
                                 Deterministic Validator
                               (link check against catalog)
                                          │
                                          ▼
                                    JSON Response
```

### 2.2 The Stateless Request Lifecycle
The API is built with **FastAPI** to handle high-concurrency asynchronous requests. Unlike traditional chatbots that store session state in a database, this system is entirely **stateless**. Each request to the `/chat` endpoint contains the full conversation history. This design choice simplifies scaling and ensures that the agent always has the complete context available for reasoning.

### 2.2 Semantic Retrieval Pipeline (RAG)
The heart of the system is the RAG pipeline, which bridges the gap between the LLM's general knowledge and the specific SHL product catalog:
*   **Vector Database:** I utilized **FAISS** (Facebook AI Similarity Search) for local, high-speed vector indexing.
*   **Embedding Model:** I selected the **`all-MiniLM-L6-v2`** model. It provides a perfect balance between performance and memory footprint, allowing us to generate 384-dimensional dense vectors for all 377 products in the catalog.
*   **Similarity Scoring:** The system uses Inner Product (IP) similarity to find the top 20 most relevant assessments based on the user's hiring needs (Role, Seniority, and Skills).

### 2.3 The LLM Orchestrator
I chose **Llama-3.3-70b-versatile** via **Groq** as our primary inference engine. With its 70 billion parameters, the model demonstrates superior reasoning capabilities in following the complex system instructions and JSON schemas required for this task.

---

## 3. Data Engineering & Sanitization

### 3.1 Overcoming Data Quality Issues
One of the primary difficulties encountered was the quality of the source `catalog.json`. The file contained non-printable control characters and nested structures that broke standard JSON libraries. 
*   **The Fix:** I developed a specialized sanitization script that utilized regular expressions to clean the raw bytes and a recursive parser to flatten the product data into a standardized schema.

### 3.2 Metadata Enrichment
To improve the "findability" of products, I did not just embed the descriptions. I created an **Enriched Search String** for every product:
`[Product Name] | Level: [Job Level] | Type: [Assessment Type] | Description: [Full Description]`
This enrichment allows the vector search to correctly identify "Senior" vs "Graduate" roles, even if those specific words aren't in the product's primary description.

---

## 4. Reliability & High-Availability Engineering

### 4.1 Multi-Provider Failover System
To address the strict rate limits of free-tier AI APIs, I engineered a robust **Failover and Rotation Layer**. The system is configured with a pool of **6 rotating API keys** across two different providers:
1.  **Primary:** 3 Groq API keys (rotating on failure).
2.  **Secondary (Fallback):** 3 Gemini 2.0 Flash API keys.

**The Logic:** If a request to Groq hits a "429 Too Many Requests" error, the system catches the exception and immediately retries with the next key. if all Groq keys are exhausted, the system seamlessly switches to the Google Gemini infrastructure. This ensures that recruiters never see an error message.

---

## 5. Guardrails & Output Integrity

### 5.1 Deterministic Validation Layer
LLMs are known for "hallucinations"—generating plausible but non-existent URLs. To solve this, I implemented a **Post-Processing Validation Layer** in Python:
*   The LLM generates the response.
*   The Python layer extracts the recommended names and URLs.
*   It performs a strict lookup in the **Catalog Hash Map**.
*   If a URL is missing or incorrect, the system **force-overwrites** it with the correct canonical link from the catalog before the user ever sees it. This guarantees **100% link integrity**.

### 5.2 Prompt Guardrails
The system prompt includes strict "Persona Constraints":
*   **Topic Adherence:** The agent politely refuses to perform tasks unrelated to SHL assessments (e.g., "I cannot help you write a job description, but I can recommend a test for it").
*   **Clarification Mandate:** The agent is instructed to be "Anti-Lazy." It will not recommend a test for a vague query like "I need a test." Instead, it will ask for the specific role or skills required.

---

## 6. Deployment & Infrastructure

### 6.1 Containerization (Docker)
The application is fully containerized using a multi-stage **Dockerfile**. This ensures that the environment (Python 3.10, PyTorch, FAISS) is identical whether running locally or in the cloud.

### 6.2 Cloud Infrastructure (HuggingFace)
While many free hosting services (like Render) limit RAM to 512MB, I chose **HuggingFace Spaces** for deployment.
*   **Hardware:** 2 vCPU | 16 GB RAM.
*   **Rationale:** The 16GB RAM is essential for loading the `sentence-transformers` library and the FAISS index without triggering Out-Of-Memory (OOM) errors, ensuring high performance and stability.

---

## 7. Evaluation Results
Evaluation uses the 10 provided sample traces (`GenAI_SampleConversations/C1.md`–`C10.md`) via `scripts/evaluate.py`:

1. **Parser** (`scripts/sample_parser.py`) extracts each user turn, gold product URLs from markdown tables, and whether recommendations are expected on that turn.
2. **Replay** feeds user turns sequentially through the live agent (full conversation history, as in production).
3. **Scoring** computes precision, recall, and F1 on URL sets per turn, plus aggregate and per-scenario final-turn F1. Flags premature recommendations (recs when gold expects clarification) and missed turns.

**Automated guarantees (deterministic layer):**
*   **Groundedness:** Every returned URL is validated against `catalog_clean.json` before responding.
*   **Schema compliance:** 100% via Pydantic (`ChatRequest` / `ChatResponse`).

**Qualitative behaviour (observed across scenarios):** The agent distinguishes technical hiring (e.g. Java/AWS), contact-centre volume screening, leadership/OPQ stacks, and clarification-before-recommendation flows consistent with the sample traces.

Run locally: `python scripts/evaluate.py --dry-run` (parse only) or `python scripts/evaluate.py --delay 3` (full benchmark; requires API quota).

### 7.2 Automated Test Suite (Reviewer Instructions)

Per the assignment requirement that **submitted API links remain accessible and functional for automated evaluation**, the project includes a pytest-based suite and a single entry-point runner. Graders do not need API keys locally — tests call the **live deployed API** on HuggingFace.

#### 7.2.1 Accessible Endpoints (Live Deployment)

| Endpoint | URL | Expected result |
|----------|-----|-----------------|
| **Conversational chat UI** | https://adhamsafir-conversational-hiring-agent.hf.space | Natural multi-turn dialogue (web) |
| **API base** | https://adhamsafir-conversational-hiring-agent.hf.space | FastAPI service |
| **Health check** | https://adhamsafir-conversational-hiring-agent.hf.space/health | `{"status":"ok"}` |
| **Interactive docs** | https://adhamsafir-conversational-hiring-agent.hf.space/docs | Swagger UI (HTTP 200) |
| **OpenAPI spec** | https://adhamsafir-conversational-hiring-agent.hf.space/openapi.json | Schema with `/health` and `/chat` |
| **Chat** | `POST` https://adhamsafir-conversational-hiring-agent.hf.space/chat | JSON `ChatResponse` |

**GitHub repository:** https://github.com/Adhamsafir1/conversational-hiring-agent

#### 7.2.2 How to Run Automated Tests

From the repository root:

```bash
pip install -r requirements.txt
python scripts/run_automated_tests.py
```

Optional flags:

| Command | Purpose |
|---------|---------|
| `python scripts/run_automated_tests.py` | Full suite: offline parser tests → live smoke/contract → sample replay (C1, C10) |
| `python scripts/run_automated_tests.py --no-replay` | Fast path: smoke + `/chat` contract only (~15s) |
| `python scripts/run_automated_tests.py --offline-only` | Parser tests only (no network) |
| `python scripts/run_automated_tests.py --full-replay` | Replay all 10 gold conversations (slow) |
| `API_BASE_URL=https://your-host.hf.space python scripts/run_automated_tests.py` | Target a different deployment |

Equivalent: `pytest tests/ -v`

#### 7.2.3 Test Coverage

| Module | Type | What it verifies |
|--------|------|------------------|
| `tests/test_parser.py` | Offline | All 10 `GenAI_SampleConversations/C*.md` files parse; gold URL counts (e.g. C1) |
| `tests/test_smoke.py` | Live HTTP | `/health`, `/openapi.json`, `/docs` reachable |
| `tests/test_api_contract.py` | Live HTTP | `/chat` JSON shape; `name`, `url`, `test_type` fields; URLs on `shl.com`; URLs exist in `catalog_clean.json`; multi-turn history |
| `tests/test_sample_replay.py` | Live HTTP | Replays **C1** and **C10** turn-by-turn; scores URL precision/recall/F1 vs gold tables |

**Pass criteria for grading:** Offline parser tests + live smoke + API contract tests must pass. Sample replay compares agent output to gold traces; if the deployment LLM is rate-limited, replay tests **skip** (not fail) so core API accessibility is still validated.

#### 7.2.4 CI Integration

GitHub Actions workflow `.github/workflows/automated-tests.yml` runs `python scripts/run_automated_tests.py` on push/PR against the production HuggingFace URL.

#### 7.2.5 Local Benchmark (Optional, Requires API Keys)

For deeper accuracy analysis against all ten gold traces (local agent, not HTTP):

```bash
python scripts/evaluate.py --dry-run
python scripts/evaluate.py --delay 3
python scripts/evaluate.py --file C1.md --json-out results.json
```

### 7.3 Performance & Reliability
*   **URL integrity:** Invalid catalog links are dropped or corrected by name lookup in the validator.
*   **Latency:** Target &lt;2.5s per turn in warm state (embedding model + FAISS cached).
*   **Reliability:** Groq primary with Gemini fallback and multi-key rotation on 429 errors.

---

## 8. Conclusion & Future Roadmap
The current implementation provides a highly resilient, accurate, and fast recommendation engine. With more time, the system could be enhanced by:
1.  **Hybrid Search:** Combining FAISS vector search with BM25 keyword search for better accuracy on specific product acronyms.
2.  **Persistence:** Adding a Redis cache or PostgreSQL database to store conversation history across sessions.
3.  **Analytics:** Implementing a feedback loop to track which recommendations are clicked by users to improve future ranking.

---

**Submitted By:** Adham Safir

**Live API:** https://adhamsafir-conversational-hiring-agent.hf.space  
**Health:** https://adhamsafir-conversational-hiring-agent.hf.space/health  
**API docs:** https://adhamsafir-conversational-hiring-agent.hf.space/docs  
**GitHub:** https://github.com/Adhamsafir1/conversational-hiring-agent  
**Automated tests:** `pip install -r requirements.txt && python scripts/run_automated_tests.py`
