import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from backend.app.models.document import Document, DocumentChunk
from backend.app.models.extraction import ExtractedDetail
from backend.app.services.acl_service import check_document_access

logger = logging.getLogger(__name__)

FIELD_DEFINITIONS = [
    {
        "name": "objective",
        "keywords": ["objective", "aim", "purpose", "hypothesize", "we propose", "in this paper we", "goal"],
        "fallback_unavailable": "Primary study objective or formal research hypothesis was not stated in the abstract/introduction sections."
    },
    {
        "name": "methodology",
        "keywords": ["methodology", "method", "protocol", "architecture", "algorithm", "randomized", "loss function", "training"],
        "fallback_unavailable": "Experimental methodology or algorithmic formulation is absent in the document."
    },
    {
        "name": "population",
        "keywords": ["population", "participants", "cohort", "dataset", "benchmarks", "sample size", "patients", "subjects"],
        "fallback_unavailable": "Study cohort or benchmark dataset characteristics were not specified in the document."
    },
    {
        "name": "findings",
        "keywords": ["findings", "results", "achieved", "accuracy", "statistically significant", "p <", "retention", "win rate"],
        "fallback_unavailable": "Quantitative outcomes or empirical findings are unavailable in the text."
    },
    {
        "name": "limitations",
        "keywords": ["limitations", "threats to validity", "constraints", "future work", "caution", "did not monitor", "drawbacks"],
        "fallback_unavailable": "Study limitations or constraints were not explicitly discussed by the authors."
    }
]

class ExtractionService:
    async def extract_study_details(
        self,
        db: AsyncSession,
        user_id: str,
        document_id: str
    ) -> List[ExtractedDetail]:
        """
        Extracts structured 5-field study details from document chunks.
        Strict zero-hallucination: If field is absent, flags is_unavailable=True.
        """
        # 1. Server-side ACL verification
        doc = await check_document_access(db, user_id, document_id, required_level="view")

        # 2. Check if already extracted
        existing_stmt = select(ExtractedDetail).where(ExtractedDetail.document_id == document_id)
        existing_res = await db.execute(existing_stmt)
        existing = existing_res.scalars().all()
        if existing:
            return existing

        # 3. Retrieve document chunks
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
        chunks_res = await db.execute(stmt)
        chunks = chunks_res.scalars().all()

        extracted_records = []

        for field_def in FIELD_DEFINITIONS:
            field_name = field_def["name"]
            keywords = field_def["keywords"]
            best_chunk = None
            best_sentence = None
            best_score = 0

            # Scan all sentences in all chunks directly for field-specific keywords
            for c in chunks:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", c.content) if len(s.strip()) > 10]
                for s in sentences:
                    s_lower = s.lower()
                    score = sum(2 for kw in keywords if kw in s_lower)
                    for kw in keywords:
                        if f"{kw}:" in s_lower or f"{kw} -" in s_lower:
                            score += 3
                    if score > best_score:
                        best_score = score
                        best_sentence = s
                        best_chunk = c

            if best_chunk and best_sentence and best_score >= 2:
                record = ExtractedDetail(
                    document_id=document_id,
                    field_name=field_name,
                    field_value=best_sentence,
                    is_unavailable=False,
                    confidence=round(min(0.98, 0.70 + (best_score * 0.08)), 2),
                    page_number=best_chunk.page_number,
                    passage_excerpt=best_chunk.content[:350],
                    review_status="proposed"
                )
            else:
                # Explicit zero-hallucination abstention
                record = ExtractedDetail(
                    document_id=document_id,
                    field_name=field_name,
                    field_value="unavailable",
                    is_unavailable=True,
                    unavailable_reason=field_def["fallback_unavailable"],
                    confidence=0.0,
                    page_number=None,
                    passage_excerpt=None,
                    review_status="unavailable"
                )

            db.add(record)
            extracted_records.append(record)

        await db.commit()
        for r in extracted_records:
            await db.refresh(r)

        return extracted_records

extraction_service = ExtractionService()
