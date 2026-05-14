# Approach Summary: SHL Conversational Assessment Recommender

## 1. Design Choices and Architecture
The goal was to build a stateless, responsive API that translates vague hiring queries into grounded SHL assessment recommendations. I chose a **FastAPI** backend for its asynchronous capabilities and built-in validation (Pydantic), which guarantees the strict JSON output schema required by the assignment.

Instead of maintaining state on the server, the `/chat` endpoint is **stateless**, receiving the full conversation history on each request. The architecture consists of three core components:
1. **Query Extractor:** Analyzes the conversation history to formulate a robust search query.
2. **Semantic Retriever:** Finds relevant products from the catalog.
3. **LLM Orchestrator:** Uses the retrieved context to decide whether to clarify, recommend, refine, or refuse, outputting the final JSON response.

I used the **Groq API** with the `llama-3.3-70b-versatile` model. Groq was chosen for its exceptional inference speed, which is critical for maintaining a responsive conversational experience (easily meeting the <30 seconds per call requirement).

## 2. Retrieval Setup
I implemented a **Retrieval-Augmented Generation (RAG)** pipeline using `FAISS` and the `all-MiniLM-L6-v2` embedding model. 
* **Data Preparation:** The raw catalog JSON contained control characters that broke standard parsers. I wrote a sanitization script to clean the data, extracting 377 unique "Individual Test Solutions."
* **Embedding Strategy:** Instead of just embedding the product description, I created an "enriched text" representation for each product: `[Name] [Type] [Job Level] [Description]`. This ensures that semantic searches for specific seniority levels (e.g., "executive") or test types (e.g., "personality") match correctly.
* **Retrieval Logic:** The system retrieves the Top 20 relevant assessments. These are injected into the LLM's system prompt, allowing the LLM to perform the final ranking and filtering based on the nuanced conversational context.

## 3. Prompt Design
The system prompt was engineered with strict guardrails to enforce the persona and output format:
* **Groundedness:** "NEVER hallucinate assessments. Every assessment you recommend MUST come from the CATALOG DATA provided below."
* **Anti-Laziness:** The prompt defines exactly what information constitutes "sufficient context" (Role OR Skills) and instructs the agent to ask clarifying questions if the user query is too vague (e.g., "I need a test").
* **JSON Enforcement:** The prompt provides the exact JSON schema and explicitly forbids any conversational filler text outside the JSON object.
* **Turn Limits:** The prompt instructs the agent to be efficient and stay within the 8-turn limit. A dynamic rule was added in the Python code: if the turn count reaches 6, a hard instruction is appended to force a recommendation rather than asking more questions.

## 4. Evaluation Method
To measure quality, I implemented an evaluation script (`scripts/evaluate.py`) that runs the agent against the provided sample conversation traces (`C1.md` - `C10.md`). 
* **Groundedness Score:** Measures the percentage of recommended URLs that strictly match the canonical SHL domain. Our post-processing validation step ensures this is consistently 100%.
* **Relevance:** Qualitative analysis against the expected outcomes in the sample traces. The agent successfully clusters related tests (e.g., grouping Java, Spring, and SQL tests for a backend developer).

## 5. What Did Not Work & Improvements
* **Initial Failure (JSON Formatting):** Initially, the LLM occasionally wrapped the JSON response in Markdown code fences (````json ... ````), breaking the JSON parser. I improved this by adding a Regex pre-processing step in the Python agent to strip markdown fences before parsing.
* **Initial Failure (Hallucinated URLs):** Early versions of the LLM sometimes hallucinated product URLs by guessing the slug based on the product name. 
* **Measurement of Improvement:** I measured improvement by tracking the error rate of the JSON parser and the validation drop rate. To fix the URL hallucinations, I implemented a deterministic **Post-Processing Validation Layer**. Before returning the response, the system cross-references the LLM's recommendations against a hash map of the actual catalog. If the LLM generates a valid name but an incorrect URL, the system automatically overwrites the URL with the correct canonical link from the catalog.

## Answers to Form Questions
* **Does your deployed API have a cold-start delay?** Yes, if deployed on Render Free Tier, there is a ~50-second cold start delay if the service has been inactive for 15 minutes. Once warm, responses take ~2-3 seconds.
* **LLM Used:** Groq (`llama-3.3-70b-versatile`).
* **AI Assistance:** Yes, I used an AI coding assistant (Antigravity/Gemini) to help write the boilerplate FastAPI routing, sanitize the dirty JSON catalog data, and configure the FAISS indexing logic.
