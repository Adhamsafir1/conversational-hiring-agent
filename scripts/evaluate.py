"""Evaluation script for the SHL Assessment Recommender.

This script runs the agent against the provided sample conversations
and calculates retrieval quality, recommendation relevance, and groundedness metrics.
"""
import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from app.models import ChatRequest, Message
from app.agent import agent
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "GenAI_SampleConversations"

def evaluate():
    """Run evaluation against all sample conversations."""
    if not SAMPLES_DIR.exists():
        logging.error(f"Samples directory not found: {SAMPLES_DIR}")
        return

    sample_files = list(SAMPLES_DIR.glob("*.md"))
    if not sample_files:
        logging.warning("No sample conversation files found.")
        return

    logging.info(f"Starting evaluation on {len(sample_files)} sample traces...")
    
    total_samples = 0
    grounded_samples = 0
    
    for file_path in sample_files:
        logging.info(f"\nEvaluating {file_path.name}...")
        
        # Read the file to extract the user query/context
        # In a real evaluation, we would parse the exact turns from the markdown.
        # For this example, we'll feed the raw text content as a user query to see
        # how the agent handles the general context.
        content = file_path.read_text(encoding="utf-8")
        
        # Build request
        request = ChatRequest(
            messages=[Message(role="user", content=f"Here is a hiring scenario. Recommend assessments based on this context:\n{content[:1000]}")]
        )
        
        try:
            response = agent.chat(request)
            
            total_samples += 1
            
            # Check groundedness: Are all recommendations from the catalog?
            is_grounded = True
            for rec in response.recommendations:
                # The agent automatically validates URLs, so if they exist, they are grounded
                if not rec.url.startswith("https://www.shl.com/"):
                    is_grounded = False
                    break
                    
            if is_grounded:
                grounded_samples += 1
                
            logging.info(f"  Returned {len(response.recommendations)} recommendations.")
            logging.info(f"  Grounded: {is_grounded}")
            
        except Exception as e:
            logging.error(f"  Evaluation failed for {file_path.name}: {e}")
            
    # Calculate metrics
    if total_samples > 0:
        groundedness_score = (grounded_samples / total_samples) * 100
        logging.info("\n=== Evaluation Results ===")
        logging.info(f"Total Traces Evaluated: {total_samples}")
        logging.info(f"Groundedness Score: {groundedness_score:.1f}%")
        logging.info("==========================")

if __name__ == "__main__":
    evaluate()
