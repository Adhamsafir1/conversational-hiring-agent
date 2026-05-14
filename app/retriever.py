"""Catalog retrieval using FAISS + sentence-transformers embeddings."""
import json
import os
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.config import CATALOG_PATH, INDEX_DIR, EMBEDDING_MODEL, TOP_K_RETRIEVAL


# Key category mapping for enriching search text
KEY_TYPE_MAP = {
    "Knowledge & Skills": "technical knowledge skills test multiple choice",
    "Personality & Behavior": "personality behavioral workplace behavior traits style",
    "Simulations": "simulation hands-on practical exercise work sample",
    "Ability & Aptitude": "cognitive ability reasoning aptitude general mental",
    "Competencies": "competency competencies workplace performance",
    "Biodata & Situational Judgment": "situational judgment biodata scenarios decision making",
    "Development & 360": "development 360 feedback review growth",
    "Assessment Exercises": "assessment center exercise group role-play presentation",
}


class CatalogRetriever:
    """Retrieves relevant SHL assessments using semantic search."""

    def __init__(self):
        self.catalog: list[dict] = []
        self.index: faiss.IndexFlatIP | None = None
        self.model: SentenceTransformer | None = None
        self._loaded = False

    def load(self):
        """Load catalog data and build/load FAISS index."""
        if self._loaded:
            return

        # Load catalog
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            self.catalog = json.loads(f.read(), strict=False)

        # Load embedding model
        self.model = SentenceTransformer(EMBEDDING_MODEL)

        # Build or load index
        index_path = INDEX_DIR / "faiss.index"
        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
        else:
            self._build_index()

        self._loaded = True

    def _build_search_text(self, product: dict) -> str:
        """Create enriched search text for a catalog product."""
        parts = [
            product.get("name", ""),
            product.get("description", ""),
        ]

        # Add key type descriptions
        for key in product.get("keys", []):
            if key in KEY_TYPE_MAP:
                parts.append(KEY_TYPE_MAP[key])

        # Add job levels
        job_levels = product.get("job_levels", [])
        if job_levels:
            parts.append("job levels: " + ", ".join(job_levels))

        # Add duration info
        duration = product.get("duration", "")
        if duration:
            parts.append(f"duration: {duration}")

        return " | ".join(filter(None, parts))

    def _build_index(self):
        """Build FAISS index from catalog data."""
        texts = [self._build_search_text(p) for p in self.catalog]
        embeddings = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

        # Use inner product (cosine similarity since normalized)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(np.array(embeddings, dtype=np.float32))

        # Save index
        os.makedirs(INDEX_DIR, exist_ok=True)
        faiss.write_index(self.index, str(INDEX_DIR / "faiss.index"))

    def search(self, query: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
        """Search catalog for assessments matching the query."""
        if not self._loaded:
            self.load()

        # Encode query
        query_embedding = self.model.encode([query], normalize_embeddings=True)
        query_embedding = np.array(query_embedding, dtype=np.float32)

        # Search
        scores, indices = self.index.search(query_embedding, min(top_k, len(self.catalog)))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            product = self.catalog[idx].copy()
            product["_score"] = float(score)
            results.append(product)

        return results

    def get_by_name(self, name: str) -> dict | None:
        """Get a product by exact or partial name match."""
        name_lower = name.lower().strip()
        for product in self.catalog:
            if product["name"].lower().strip() == name_lower:
                return product
        # Partial match
        for product in self.catalog:
            if name_lower in product["name"].lower():
                return product
        return None

    def get_all_products(self) -> list[dict]:
        """Return the full catalog."""
        if not self._loaded:
            self.load()
        return self.catalog

    def format_product_for_context(self, product: dict) -> str:
        """Format a product as a concise string for LLM context."""
        keys_str = ", ".join(product.get("keys", []))
        levels_str = ", ".join(product.get("job_levels", []))
        return (
            f"Name: {product['name']} | "
            f"URL: {product.get('link', '')} | "
            f"Type: {keys_str} | "
            f"Levels: {levels_str} | "
            f"Duration: {product.get('duration', 'N/A')} | "
            f"Remote: {product.get('remote', 'N/A')} | "
            f"Adaptive: {product.get('adaptive', 'N/A')} | "
            f"Description: {product.get('description', 'N/A')}"
        )


# Singleton instance
retriever = CatalogRetriever()
