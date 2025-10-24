"""
Lightweight Cross-Encoder based reranker utility.

This module loads a Cross-Encoder model once and provides a simple function
to rerank retrieved documents given a user query. Scores are attached to
each Document's metadata under key 'ce_score'.

Dependencies: sentence-transformers (already listed in requirements)
"""

from typing import List, Tuple, Optional

from sentence_transformers import CrossEncoder

try:
    # Import only for type hints; avoid hard dependency in runtime imports
    from langchain_core.documents import Document  # type: ignore
except Exception:  # pragma: no cover
    try:
        from langchain.schema import Document  # type: ignore
    except Exception:  # pragma: no cover
        Document = object  # fallback for type hints


_cross_encoder_model: Optional[CrossEncoder] = None


def get_cross_encoder(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> CrossEncoder:
    """Get or initialize a global Cross-Encoder model.

    The chosen model balances speed and quality and is adequate for short reranking.
    """
    global _cross_encoder_model
    if _cross_encoder_model is None:
        _cross_encoder_model = CrossEncoder(model_name)
    return _cross_encoder_model


def rerank_with_cross_encoder(
    query: str,
    documents: List[Document],
    max_chars: int = 1000,
    batch_size: int = 32,
    top_k: Optional[int] = None,
) -> List[Document]:
    """Rerank documents using a Cross-Encoder.

    - Truncates each document's content to `max_chars` for efficiency.
    - Computes CE scores in batches and writes them to metadata['ce_score'].
    - Returns documents sorted by CE score in descending order.
    - If top_k is provided, returns only the top_k documents.
    """
    if not documents:
        return []

    model = get_cross_encoder()

    pairs: List[Tuple[str, str]] = []
    truncated_texts: List[str] = []
    for d in documents:
        text = getattr(d, "page_content", "") or ""
        text = text[:max_chars]
        truncated_texts.append(text)
        pairs.append((query, text))

    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)

    # Attach CE scores into document metadata
    for d, s in zip(documents, scores):
        meta = getattr(d, "metadata", None)
        if isinstance(meta, dict):
            meta["ce_score"] = float(s)
        else:
            # Ensure metadata exists and is dict-like
            setattr(d, "metadata", {"ce_score": float(s)})

    # Sort by CE score (higher is better)
    documents_sorted = sorted(documents, key=lambda x: (x.metadata or {}).get("ce_score", 0.0), reverse=True)

    if top_k is not None and top_k > 0:
        documents_sorted = documents_sorted[:top_k]

    return documents_sorted


