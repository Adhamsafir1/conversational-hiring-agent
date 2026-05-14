---
title: Conversational Hiring Agent
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# 🧠 SHL Conversational Assessment Recommender

A conversational AI agent built with **FastAPI** + **Gemini** + **FAISS** that helps hiring managers and recruiters find the right SHL assessments through natural dialogue.

> **"I'm hiring a Java developer"** → clarifying questions → grounded shortlist of SHL assessments with names, URLs, and test types.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Setup & Installation](#-setup--installation)
- [Running Locally](#-running-locally)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [How It Works](#-how-it-works)
- [Sample Conversations](#-sample-conversations)

---

## ✨ Features

| Behavior | Description |
|----------|-------------|
| **Clarify** | Asks focused questions when the user query is vague |
| **Recommend** | Returns 1–10 grounded assessments from the SHL catalog |
| **Refine** | Updates the shortlist when the user changes constraints |
| **Compare** | Explains differences between assessments using catalog data only |
| **Refuse** | Politely declines off-topic questions, legal advice, prompt injections |

### Guardrails
- ✅ Every recommended assessment comes from the real SHL catalog (377 products)
- ✅ Every URL is a verified catalog link — zero hallucination
- ✅ Stays within 8-turn conversation limit
- ✅ Responds within 30 seconds per call
- ✅ Strict JSON schema compliance on every response

---

## 🏗 Architecture

```
User Request ─► FastAPI (/chat) ─► Conversation Controller
                                        │
                                        ▼
                                  Intent Analysis
                                 /    |    |    \
                           Clarify  Recommend  Refine  Refuse
                                     |    |
                              ┌──────┘    └──────┐
                              ▼                  ▼
                      FAISS Retrieval      LLM (Gemini)
                    (semantic search)    (grounded response)
                              │                  │
                              └──────┬───────────┘
                                     ▼
                            Validate Recommendations
                          (check against real catalog)
                                     │
                                     ▼
                              JSON Response
```

---

## 🛠 Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **API Framework** | FastAPI | Required by spec, async-ready, auto-docs |
| **LLM** | Google Gemini 2.0 Flash | Free tier, fast, strong instruction following |
| **Embeddings** | `all-MiniLM-L6-v2` | Free, runs locally, 384-dim, good quality |
| **Vector Store** | FAISS | Lightweight, no external infra, CPU-only |
| **Validation** | Pydantic v2 | Strict schema enforcement |
| **Language** | Python 3.11 | ML + FastAPI ecosystem |

---

## 📁 Project Structure

```
d:\SHL\
├── app/
│   ├── __init__.py          # Package init
│   ├── main.py              # FastAPI app — /health and /chat endpoints
│   ├── agent.py             # Core conversation controller + LLM orchestration
│   ├── retriever.py         # FAISS index + semantic search over catalog
│   ├── prompts.py           # System prompt with grounding rules
│   ├── models.py            # Pydantic request/response schemas
│   └── config.py            # Environment config + paths
├── data/
│   ├── catalog.json         # Raw scraped SHL catalog (377 products)
│   ├── catalog_clean.json   # Cleaned catalog used by the app
│   └── catalog_index/
│       └── faiss.index      # Pre-built FAISS vector index
├── GenAI_SampleConversations/
│   ├── C1.md ... C10.md     # 10 public conversation traces for evaluation
├── scripts/
│   └── analyze_catalog.py   # Catalog analysis utility
├── .env.example             # Environment variables template
├── requirements.txt         # Pinned Python dependencies
└── README.md                # This file
```

---

## 🚀 Setup & Installation

### Prerequisites

- **Python 3.11+** installed
- **Gemini API key** (free) from [Google AI Studio](https://aistudio.google.com/apikey)

### Step 1: Clone / Navigate to the project

```bash
cd d:\SHL
```

### Step 2: Install dependencies

```bash
python -m pip install -r requirements.txt
```

This installs FastAPI, Uvicorn, Gemini SDK, sentence-transformers, FAISS, and more. First install may take a few minutes (downloads PyTorch ~120MB).

### Step 3: Set up your Gemini API key

Create a `.env` file in the project root:

```bash
# Copy the template
copy .env.example .env
```

Then edit `.env` and add your real API key:

```env
GEMINI_API_KEY=AIzaSy...your_actual_key_here
GEMINI_MODEL=gemini-2.0-flash
```

> 💡 **Get a free key:** Go to https://aistudio.google.com/apikey → click **"Create API Key"** → copy it.

### Step 4: Build the FAISS index (first time only)

The FAISS index is pre-built in `data/catalog_index/`. If you need to rebuild it:

```bash
python -c "from app.retriever import retriever; retriever.load(); print(f'Index built: {retriever.index.ntotal} products')"
```

This downloads the embedding model (~90MB) and encodes all 377 products. Takes ~30 seconds.

---

## ▶️ Running Locally

### Start the server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or simply:

```bash
python app/main.py
```

The server starts at **http://localhost:8000**.

### Verify it's running

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status": "ok"}
```

### Interactive API docs

Open **http://localhost:8000/docs** in your browser for the Swagger UI where you can test the API interactively.

---

## 📡 API Reference

### `GET /health`

Health check endpoint.

**Response:**
```json
{"status": "ok"}
```

---

### `POST /chat`

Send a conversation and receive the agent's next reply.

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "I need to assess a Java developer"},
    {"role": "assistant", "content": "Sure! What seniority level?"},
    {"role": "user", "content": "Mid-level, around 4 years experience"}
  ]
}
```

**Response:**
```json
{
  "reply": "Here are assessments for a mid-level Java developer:",
  "recommendations": [
    {
      "name": "Core Java (Advanced Level) (New)",
      "url": "https://www.shl.com/products/product-catalog/view/core-java-advanced-level-new/",
      "test_type": "K"
    },
    {
      "name": "Java 8 (New)",
      "url": "https://www.shl.com/products/product-catalog/view/java-8-new/",
      "test_type": "K"
    }
  ],
  "end_of_conversation": false
}
```

**Field Details:**

| Field | Type | Description |
|-------|------|-------------|
| `reply` | string | Agent's conversational response |
| `recommendations` | array | Empty `[]` when gathering context; 1–10 items when recommending |
| `recommendations[].name` | string | Exact assessment name from the SHL catalog |
| `recommendations[].url` | string | Direct link to the SHL product page |
| `recommendations[].test_type` | string | Category code (see below) |
| `end_of_conversation` | bool | `true` only when the user confirms satisfaction |

**Test Type Codes:**

| Code | Category |
|------|----------|
| `K` | Knowledge & Skills |
| `P` | Personality & Behavior |
| `S` | Simulations |
| `A` | Ability & Aptitude |
| `C` | Competencies |
| `B` | Biodata & Situational Judgment |
| `D` | Development & 360 |
| `E` | Assessment Exercises |

---

## 🧪 Testing

### Quick smoke test with curl

```bash
# Health check
curl http://localhost:8000/health

# Simple chat — vague query (should clarify)
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\": [{\"role\": \"user\", \"content\": \"I need an assessment\"}]}"

# Specific query (should recommend)
curl -X POST http://localhost:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"messages\": [{\"role\": \"user\", \"content\": \"I am hiring a mid-level Java developer who will work with Spring Boot and SQL\"}]}"
```

### Quick smoke test with Python

```python
import requests

# Health
r = requests.get("http://localhost:8000/health")
print(r.json())  # {"status": "ok"}

# Chat — vague query
r = requests.post("http://localhost:8000/chat", json={
    "messages": [
        {"role": "user", "content": "I need an assessment"}
    ]
})
print(r.json())
# Should ask clarifying questions, recommendations = []

# Chat — specific query
r = requests.post("http://localhost:8000/chat", json={
    "messages": [
        {"role": "user", "content": "Hiring a mid-level Java developer with Spring and SQL"}
    ]
})
print(r.json())
# Should return recommendations with Java, Spring, SQL tests

# Multi-turn refinement
r = requests.post("http://localhost:8000/chat", json={
    "messages": [
        {"role": "user", "content": "Hiring a Java developer"},
        {"role": "assistant", "content": "What seniority level and specific skills?"},
        {"role": "user", "content": "Senior, 5+ years, needs Java, Spring, AWS"}
    ]
})
print(r.json())
```

### Running against sample conversation traces

The `GenAI_SampleConversations/` folder contains 10 conversation traces (C1.md – C10.md) provided by SHL. Each has a persona, facts, and expected shortlist. Use them to validate Recall@10.

---

## 🌐 Deployment

### Deploying to Render (Free Tier)

1. Push the project to a GitHub repository.

2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.

3. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables:** Add `GEMINI_API_KEY` in the Render dashboard.

4. Deploy. The service will be available at `https://your-service.onrender.com`.

### Deploying to Hugging Face Spaces

1. Create a new Space (Docker or Gradio).
2. Add a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build FAISS index on startup
RUN python -c "from app.retriever import retriever; retriever.load()"

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

3. Set the `GEMINI_API_KEY` secret in the Space settings.

### Deploying to Railway

```bash
# Install Railway CLI, then:
railway login
railway init
railway add --service web
railway variables set GEMINI_API_KEY=your_key
railway up
```

---

## 🧩 How It Works

### 1. User sends a message → `POST /chat`

The API receives the full conversation history (stateless design).

### 2. Query extraction

The agent combines all user messages into a search query, weighted towards the most recent message.

### 3. Semantic retrieval (FAISS)

The query is embedded using `all-MiniLM-L6-v2` and matched against the 377 pre-embedded catalog entries. The top 20 most relevant assessments are retrieved.

### 4. LLM reasoning (Gemini)

The retrieved assessments are injected into the system prompt as grounded context. Gemini then:
- Classifies the user's intent (clarify / recommend / refine / compare / refuse)
- Generates a response following the strict JSON schema
- Selects the most relevant assessments from the retrieved set

### 5. Validation

Every recommendation is cross-checked against the real catalog:
- Names must match a real product
- URLs must be real catalog links
- Invalid entries are silently dropped or corrected

### 6. Response returned

A clean JSON response with `reply`, `recommendations`, and `end_of_conversation`.

---

## 💬 Sample Conversations

### Conversation 1: Senior Leadership Assessment
```
User: "We need a solution for senior leadership."
Agent: → Clarifies: who is this for?
User: "CXOs, director-level, 15+ years experience."
Agent: → Clarifies: selection or development?
User: "Selection — comparing against a leadership benchmark."
Agent: → Recommends OPQ32r + leadership reports ✅
```

### Conversation 9: Full-Stack Engineer Battery
```
User: "Here's the JD for a Senior Full-Stack Engineer — Java, Spring, REST, Angular, SQL, AWS, Docker..."
Agent: → Clarifies: backend-leaning or balanced full-stack?
User: "Backend-leaning. Java and Spring primary."
Agent: → Clarifies: senior IC or tech lead?
User: "Senior IC."
Agent: → Recommends Java Advanced, Spring, SQL, Verify G+, OPQ32r
User: "Add AWS and Docker. Drop REST."
Agent: → Updates shortlist ✅
```

---

## 📝 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ Yes | — | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.0-flash` | Gemini model to use |

---

## 📄 License

This project is built as part of the SHL AI Intern take-home assessment.
