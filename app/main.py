"""FastAPI application for the SHL Assessment Recommender."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import ChatRequest, ChatResponse
from app.agent import agent
from app.retriever import retriever

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load catalog and index on startup."""
    logger.info("Loading catalog and building index...")
    retriever.load()
    logger.info(f"Loaded {len(retriever.catalog)} products from catalog.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational agent that recommends SHL assessments based on hiring needs.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for broad compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint. Returns status ok when service is ready."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Process a chat message and return the agent's response.
    
    The API is stateless — every call carries the full conversation history.
    The agent decides whether to clarify, recommend, refine, compare, or refuse.
    """
    logger.info(f"Received chat request with {len(request.messages)} messages")
    
    try:
        response = agent.chat(request)
        logger.info(
            f"Response: {len(response.recommendations)} recommendations, "
            f"end_of_conversation={response.end_of_conversation}"
        )
        return response
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        return ChatResponse(
            reply="I apologize, but I encountered an error. Please try again.",
            recommendations=[],
            end_of_conversation=False,
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
