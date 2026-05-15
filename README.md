---
title: SHL Conversational Assessment Recommender
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: app/main.py
pinned: false
---

# 🧠 SHL Conversational Assessment Recommender

A production-grade Conversational AI Agent built with **FastAPI**, **FAISS**, and a **Multi-Provider LLM backend (Groq + Gemini)**. This agent helps recruiters find the perfect SHL assessments through natural dialogue, ensuring 100% grounded recommendations.

> **"I'm hiring a senior Java developer with Docker experience"** → 100% accurate shortlist of SHL assessments with verified URLs.

---

## 🏗 High-Level Architecture Design
The following flow illustrates the request lifecycle from user input to the final validated JSON response, highlighting our multi-provider failover logic:

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

---

## ✨ Key Features
*   **Zero-Hallucination Retrieval:** Uses a **Retrieval-Augmented Generation (RAG)** pipeline to ensure all recommendations are grounded in the official SHL catalog.
*   **High Availability Failover:** Automatically rotates between **6 API keys** across **Groq (Llama 3.3 70B)** and **Google Gemini** to bypass rate limits and ensure 100% uptime.
*   **Deterministic Validation:** A post-processing layer cross-references every LLM-generated link against a ground-truth hash map, ensuring 100% URL integrity.
*   **Stateless Design:** The API is entirely stateless; the full conversation context is processed per-request for maximum scalability.

---

## 🛠 Tech Stack
| Component | Choice | Why |
|-----------|--------|-----|
| **API Framework** | FastAPI | Async performance, auto-generated OpenAPI docs, and Pydantic validation. |
| **Primary LLM** | Llama-3.3-70b (Groq) | Exceptional reasoning and sub-second inference speeds. |
| **Fallback LLM** | Gemini 2.0 Flash | Robust secondary provider for failover and high availability. |
| **Vector Engine** | FAISS | Ultra-fast local semantic similarity search without external infra. |
| **Embeddings** | `all-MiniLM-L6-v2` | High-quality 384-dim embeddings that run efficiently on CPU. |

---

## 📁 Project Structure
```
.
├── app/
│   ├── main.py              # FastAPI app — /health and /chat endpoints
│   ├── agent.py             # Core logic + multi-provider LLM orchestration
│   ├── retriever.py         # FAISS indexing + semantic search
│   ├── prompts.py           # System prompts with grounding guardrails
│   ├── models.py            # Pydantic data schemas
│   └── config.py            # Multi-key environment configuration
├── data/
│   ├── catalog_clean.json   # Sanitized SHL product catalog (377 items)
│   └── catalog_index/       # Pre-built FAISS vector index
├── scripts/
│   ├── evaluate.py          # Automated evaluation & groundedness testing
│   └── analyze_catalog.py   # Catalog sanitization and analysis script
├── Dockerfile               # Container configuration for cloud deployment
├── requirements.txt         # Pinned production dependencies
└── README.md                # This file
```

---

## 🚀 Setup & Installation

### Step 1: Clone and Install
```bash
git clone https://github.com/Adhamsafir1/conversational-hiring-agent.git
cd conversational-hiring-agent
pip install -r requirements.txt
```

### Step 2: Environment Configuration
Create a `.env` file and add your API keys (supports multiple keys separated by commas for rotation):
```env
# Groq Keys
GROQ_API_KEYS=key1,key2,key3
GROQ_MODEL=llama-3.3-70b-versatile

# Gemini Keys (Fallback)
GEMINI_API_KEYS=key1,key2,key3
GEMINI_MODEL=gemini-2.0-flash
```

### Step 3: Run Locally
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open **http://localhost:8000/docs** to test interactively.

---

## 🌐 Deployment (HuggingFace Spaces)
The application is optimized for **HuggingFace Spaces** with a **16GB RAM** hardware profile to handle the embedding models and FAISS index comfortably.

1.  Create a new Space on HuggingFace.
2.  Choose **Docker** as the SDK.
3.  Add your API keys to the **Secrets** section in Space Settings.
4.  Push your code. The Dockerfile will automatically build and deploy the API.

---

## 🧪 Evaluation
Run the automated evaluation suite to verify groundedness and accuracy:
```bash
python scripts/evaluate.py
```

---

**Live Demo:** [https://adhamsafir-conversational-hiring-agent.hf.space](https://adhamsafir-conversational-hiring-agent.hf.space)  
**Submitted By:** Adham Safir
