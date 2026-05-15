# Approach Summary: SHL Conversational Assessment Recommender

## 1. Design Choices and Architecture
The goal was to build a stateless, responsive API that translates vague hiring queries into grounded SHL assessment recommendations. I chose a **FastAPI** backend for its asynchronous capabilities and built-in validation (Pydantic), which guarantees the strict JSON output schema required by the assignment.

Instead of maintaining state on the server, the `/chat` endpoint is **stateless**, receiving the full conversation history on each request. The architecture consists of three core components:
1. **Semantic Query Extractor:** Analyzes conversation history to formulate a robust search vector.
2. **FAISS-based Retriever:** Performs similarity searches against the SHL product catalog.
3. **LLM Orchestrator:** Uses the retrieved context to decide whether to clarify, recommend, refine, or refuse, outputting a strictly valid JSON response.

I utilized the **Groq API** with the `llama-3.3-70b-versatile` model. Groq was chosen for its exceptional inference speed and high reasoning capability, which is critical for maintaining a "zero-latency" conversational experience while strictly following complex RAG instructions.

## 2. Retrieval & Data Engineering
I implemented a **Retrieval-Augmented Generation (RAG)** pipeline using `FAISS` and the `all-MiniLM-L6-v2` embedding model. 
* **Data Sanitization:** The raw catalog JSON provided contained several non-printable control characters that caused parsing errors. I implemented a pre-processing pipeline to sanitize the text and extract 377 unique "Individual Test Solutions."
* **Enriched Metadata:** Instead of embedding only the product names, I created an "enriched" document representation for each product: `[Name] [Test Type] [Job Level] [Description]`. This improves search accuracy for specific job levels (e.g., "graduate") and test categories (e.g., "coding").
* **Dynamic Context Injection:** The system retrieves the top 20 relevant assessments. These candidates are injected into the LLM's context, allowing the model to perform high-level reasoning to select the best matches for the specific user request.

## 3. Prompt Engineering & Guardrails
The system prompt was designed to enforce groundedness and the SHL persona:
* **Strict Groundedness:** The agent is explicitly forbidden from "hallucinating" assessments. Every recommendation must be a direct match from the retrieved catalog data.
* **Clarification Logic:** To prevent "lazy" or irrelevant recommendations, the prompt requires the agent to ask clarifying questions until at least the **Role** or **Key Skills** are identified.
* **Schema Enforcement:** The prompt provides a strict JSON schema. To further ensure robustness, I added a Python post-processing layer that uses regex to strip any markdown formatting before parsing the JSON.

## 4. Deployment & Infrastructure
Initially, I attempted to deploy on Render (Free Tier), but the system encountered "Out of Memory" (OOM) errors because PyTorch and the embedding models require more than 512MB of RAM.

I successfully migrated the deployment to **HuggingFace Spaces** (using a Docker container). HuggingFace provides **16GB of RAM**, which allows the system to load the embedding model and the FAISS index comfortably.

* **Deployment URL:** `https://adhamsafir-conversational-hiring-agent.hf.space`
* **Performance:** Average response time is ~2.5 seconds (Groq inference + local FAISS retrieval).

## 5. Evaluation & Quality Control
I measured quality using a custom evaluation script (`scripts/evaluate.py`) against the provided sample traces.
* **100% URL Integrity:** To eliminate hallucinated URLs, I implemented a **Deterministic Validation Layer**. After the LLM generates its response, the system cross-references the recommendations against the source catalog. If an LLM-suggested URL is incorrect, it is automatically replaced with the canonical link from the catalog before reaching the user.
* **Zero-Hallucination Policy:** The system successfully refuses off-topic requests (e.g., writing job descriptions) while maintaining its helpful persona for recruitment-related queries.

## Answers to Form Questions
* **Does your deployed API have a cold-start delay?** Yes, HuggingFace Spaces "sleep" after inactivity. The first request may take ~60 seconds to wake up the container and load the models into RAM. Once active, responses are sub-3-seconds.
* **LLM Used:** Groq (`llama-3.3-70b-versatile`).
* **AI Assistance:** Yes, I used an AI coding assistant (Antigravity/Gemini) to help accelerate the generation of FastAPI boilerplate, assist in regex-based data sanitization, and help configure the Dockerfile for HuggingFace deployment.
