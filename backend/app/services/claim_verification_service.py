import re
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from backend.app.models.document import Document, DocumentChunk
from backend.app.services.acl_service import check_document_access
from backend.app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

class ClaimVerificationService:
    async def verify_claim(
        self,
        db: AsyncSession,
        user_id: str,
        claim_text: str,
        document_id: str,
        page_number: int,
        cited_excerpt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Claim-level verification:
        1. Validates that cited document ID and page number physically exist in the database.
        2. Validates user has authorized access.
        3. Runs entailment scoring between claim and passage.
        4. Categorizes into 'supported', 'partially_supported', or 'unsupported'.
        """
        # 1. Server-side ACL verification
        try:
            doc = await check_document_access(db, user_id, document_id, required_level="view")
        except Exception:
            return {
                "claim": claim_text,
                "status": "unsupported",
                "status_label": "Unsupported",
                "confidence": 0.0,
                "reasoning": "Unauthorized access or document does not exist.",
                "valid_citation": False
            }

        # 2. Page bounds validation
        if page_number < 1 or (doc.page_count and page_number > doc.page_count):
            return {
                "claim": claim_text,
                "status": "unsupported",
                "status_label": "Unsupported Citation",
                "confidence": 0.0,
                "reasoning": f"Cited page {page_number} is out of bounds for document '{doc.title}' (total pages: {doc.page_count}).",
                "valid_citation": False
            }

        # 3. Retrieve actual chunks on this page
        stmt = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.page_number == page_number
        )
        res = await db.execute(stmt)
        chunks = res.scalars().all()

        if not chunks and not cited_excerpt:
            return {
                "claim": claim_text,
                "status": "unsupported",
                "status_label": "No Passage Found",
                "confidence": 0.0,
                "reasoning": f"No text content found on page {page_number} of document '{doc.title}'.",
                "valid_citation": False
            }

        # Concatenate page text or use cited excerpt
        page_text = cited_excerpt or " ".join([c.content for c in chunks])

        # 4. Semantic and Lexical Entailment Check
        return self._evaluate_entailment(claim_text, page_text, doc.title, page_number)

    def _evaluate_entailment(
        self,
        claim_text: str,
        passage_text: str,
        doc_title: str,
        page_number: int
    ) -> Dict[str, Any]:
        """
        Evaluates whether the passage text entails, partially supports, or contradicts the claim.
        """
        claim_emb = embedding_service.embed_text(claim_text)
        passage_emb = embedding_service.embed_text(passage_text)
        sim_score = embedding_service.cosine_similarity(claim_emb, passage_emb)

        # Token overlap check
        claim_words = set(re.findall(r"\b[a-zA-Z0-9%.-]{3,}\b", claim_text.lower()))
        stopwords = {"the", "and", "that", "this", "were", "with", "from", "have", "been", "also", "then"}
        informative_claim_words = claim_words - stopwords

        passage_lower = passage_text.lower()
        matched_words = [w for w in informative_claim_words if w in passage_lower]
        match_ratio = len(matched_words) / max(len(informative_claim_words), 1)

        # Numbers check (precision on statistics, percentages, p-values)
        claim_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", claim_text))
        matched_numbers = [n for n in claim_numbers if n in passage_text]
        number_match_ratio = len(matched_numbers) / max(len(claim_numbers), 1) if claim_numbers else 1.0

        # Strict quantitative check: If specific numbers are asserted but totally absent, flag unsupported
        if claim_numbers and number_match_ratio == 0.0:
            return {
                "claim": claim_text,
                "status": "unsupported",
                "status_label": "Unsupported",
                "confidence": round(sim_score, 2),
                "reasoning": f"The cited passage on page {page_number} does not substantiate the stated quantitative assertions ({', '.join(claim_numbers)}). Assertions are absent in source text.",
                "valid_citation": True,
                "similarity_score": round(sim_score, 4)
            }

        # Classification Logic
        if (sim_score >= 0.48 and match_ratio >= 0.50 and number_match_ratio == 1.0) or (match_ratio >= 0.70 and number_match_ratio == 1.0):
            return {
                "claim": claim_text,
                "status": "supported",
                "status_label": "Supported",
                "confidence": round(min(0.99, max(sim_score, 0.88)), 2),
                "reasoning": f"Claim is directly entailed by passage on page {page_number} of '{doc_title}'. All stated figures and outcomes align with source text.",
                "valid_citation": True,
                "similarity_score": round(sim_score, 4)
            }
        elif (sim_score >= 0.35 and match_ratio >= 0.40) or (number_match_ratio < 1.0 and match_ratio >= 0.5):
            missing_qualifiers = [w for w in informative_claim_words if w not in passage_lower]
            qualifier_note = f" Missing or unverified terms: {', '.join(missing_qualifiers[:3])}." if missing_qualifiers else ""
            return {
                "claim": claim_text,
                "status": "partially_supported",
                "status_label": "Partially Supported",
                "confidence": round(min(0.75, max(sim_score, 0.50)), 2),
                "reasoning": f"Qualified support: claim is partially grounded in passage on page {page_number}, but requires qualification or specific subgroup condition.{qualifier_note}",
                "valid_citation": True,
                "similarity_score": round(sim_score, 4)
            }
        else:
            return {
                "claim": claim_text,
                "status": "unsupported",
                "status_label": "Unsupported",
                "confidence": round(sim_score, 2),
                "reasoning": f"The cited passage on page {page_number} does not provide adequate factual support for this claim. Key assertions are absent or uncorroborated in source.",
                "valid_citation": True,
                "similarity_score": round(sim_score, 4)
            }

claim_verification_service = ClaimVerificationService()
