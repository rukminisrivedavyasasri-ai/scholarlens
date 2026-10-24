from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import re
import logging

from backend.app.config import settings
from backend.app.models.document import Document, DocumentChunk
from backend.app.services.acl_service import get_permitted_document_ids
from backend.app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

def is_reference_or_boilerplate_chunk(text: str) -> bool:
    """
    Detects whether a chunk is part of a reference list, bibliography,
    diagram scheme caption, or figure metadata so it can be downranked or excluded.
    """
    clean = text.strip()
    if not clean:
        return True
    
    # Check if section title is References or Bibliography
    if re.match(r"^(references|bibliography|literature cited)\b", clean, re.IGNORECASE):
        return True

    # Check for heavy citation patterns like [1] ... [2] ... [3]
    cite_matches = re.findall(r"\[\d+\]\s+[A-Z]", clean)
    if len(cite_matches) >= 3:
        return True

    # Check for strings dominated by DOI/volume citation patterns
    doi_matches = re.findall(r"\b(doi:|https?://doi\.org|vol\.|pp\.)", clean, re.IGNORECASE)
    if len(doi_matches) >= 3:
        return True

    # Check if text is just a figure or scheme caption fragment
    if re.match(r"^(scheme|figure|fig\.|table)\s+\d+[:.]", clean, re.IGNORECASE) and len(clean) < 120:
        return True

    return False

class RetrievalService:
    async def retrieve_passages(
        self,
        db: AsyncSession,
        user_id: str,
        query: str,
        collection_id: Optional[str] = None,
        top_k: int = 5,
        min_score: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top-k relevant passages strictly filtered by authorization
        BEFORE similarity ranking inside the database query.
        Applies reference list downranking and configurable relevance threshold filtering.
        """
        effective_min_score = min_score if min_score is not None else settings.QA_RELEVANCE_THRESHOLD
        # 1. Authorize: compute whitelisted document IDs for this user
        permitted_doc_ids = await get_permitted_document_ids(db, user_id, collection_id)
        if not permitted_doc_ids:
            logger.info(f"User {user_id} has no permitted documents in scope.")
            return []

        # 2. Vectorize query
        query_vector = embedding_service.embed_text(query)

        # 3. Query chunks filtered by permitted document IDs (strictly pre-retrieval)
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.document_id.in_(permitted_doc_ids))
        )
        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            return []

        # 4. Fast vectorized cosine similarity ranking
        import numpy as np
        q_arr = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm > 0:
            q_arr = q_arr / q_norm

        scored_chunks = []
        embeddings_list = []
        valid_indices = []

        for idx, (chunk, doc_title) in enumerate(rows):
            if chunk.embedding:
                embeddings_list.append(chunk.embedding)
                valid_indices.append(idx)

        # Batch compute dot product for pre-computed unit-normalized embeddings
        if embeddings_list:
            emb_matrix = np.array(embeddings_list, dtype=np.float32)
            # Normalize matrix rows if needed
            norms = np.linalg.norm(emb_matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            emb_matrix = emb_matrix / norms
            batch_scores = np.dot(emb_matrix, q_arr)
        else:
            batch_scores = []

        score_map = {}
        for pos, row_idx in enumerate(valid_indices):
            score_map[row_idx] = float(batch_scores[pos])

        for idx, (chunk, doc_title) in enumerate(rows):
            if idx in score_map:
                score = score_map[idx]
            else:
                emb = embedding_service.embed_text(chunk.content)
                score = embedding_service.cosine_similarity(query_vector, emb)

            # Apply downranking or exclusion to reference lists and diagram captions
            is_noise = is_reference_or_boilerplate_chunk(chunk.content)
            adjusted_score = score * 0.4 if is_noise else score

            scored_chunks.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_title": doc_title,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "bounding_box": chunk.bounding_box,
                "score": round(adjusted_score, 4),
                "is_reference": is_noise
            })

        # 5. Sort descending by score and filter by effective minimum score threshold
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        top_results = [c for c in scored_chunks if c["score"] >= effective_min_score][:top_k]
        return top_results

retrieval_service = RetrievalService()
