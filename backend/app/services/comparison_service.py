import re
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.models.document import Document
from backend.app.models.extraction import ExtractedDetail
from backend.app.services.acl_service import get_permitted_document_ids
from backend.app.services.retrieval_service import retrieval_service

class ComparisonService:
    """
    Cross-study evidence comparison service with a strict 4-Dimension Comparability Guard:
    1. Population / Dataset
    2. Setting
    3. Method
    4. Outcome Measure
    
    Before calling studies 'contradictory' or 'conflicting', the system evaluates differences
    across all 4 dimensions. If any dimension differs significantly, the result is classified as
    'not_directly_comparable' with a detailed explanation rather than a contradiction.
    """

    @classmethod
    async def compare_studies(
        cls,
        db: AsyncSession,
        question: str,
        document_ids: List[str],
        user_id: str,
        user_role: str = "viewer"
    ) -> Dict[str, Any]:
        # Limit to 5 studies per user specification
        doc_ids = document_ids[:5]
        
        # 1. Permission-aware retrieval of permitted document IDs
        all_permitted = await get_permitted_document_ids(db, user_id)
        permitted_doc_ids = [d for d in doc_ids if d in all_permitted]
        
        if not permitted_doc_ids:
            return {
                "question": question,
                "studies": [],
                "matrix": [],
                "pairwise_comparisons": [],
                "gaps": ["No permitted documents found for comparison."],
                "reading_priority": []
            }

        doc_res = await db.execute(select(Document).where(Document.id.in_(permitted_doc_ids)))
        docs = doc_res.scalars().all()
        doc_map = {doc.id: doc for doc in docs}

        # 2. Gather extracted details or retrieve relevant passages for each document
        studies_data = []
        for doc_id in permitted_doc_ids:
            doc = doc_map.get(doc_id)
            if not doc:
                continue

            ext_res = await db.execute(select(ExtractedDetail).where(ExtractedDetail.document_id == doc_id))
            extractions = ext_res.scalars().all()

            fields = {ext.field_name: ext.field_value for ext in extractions if not ext.is_unavailable}
            
            # Query relevant passages for the question to see what this study says about it
            passages = await retrieval_service.retrieve_passages(
                db=db,
                user_id=user_id,
                query=question,
                collection_id=doc.collection_id,
                top_k=2
            )
            passages = [p for p in passages if p["document_id"] == doc_id]
            
            finding_text = fields.get("findings", "")
            if not finding_text and passages:
                finding_text = passages[0]["content"]
            elif not finding_text:
                finding_text = "unavailable"

            study_info = {
                "document_id": doc_id,
                "title": doc.title,
                "population": fields.get("population", "unavailable"),
                "setting": fields.get("setting", "Standard experimental benchmark"),
                "method": fields.get("methodology", "unavailable"),
                "outcome_measure": fields.get("outcome_measure", "Task performance / accuracy"),
                "finding": finding_text,
                "passages": passages
            }
            studies_data.append(study_info)

        # 3. 4-Dimension Comparability Guard & Pairwise Comparison
        pairwise_comparisons = []
        for i in range(len(studies_data)):
            for j in range(i + 1, len(studies_data)):
                s1 = studies_data[i]
                s2 = studies_data[j]
                comparison = cls._evaluate_pairwise_comparability(s1, s2, question)
                pairwise_comparisons.append(comparison)

        # 4. Synthesize Study Matrix
        matrix = []
        for study in studies_data:
            status = "supporting"
            reason = "Study provides direct evidence supporting the query context."
            
            if study["finding"] == "unavailable":
                status = "missing"
                reason = "Study does not contain direct evidence addressing this research question."
            else:
                for pair in pairwise_comparisons:
                    if study["document_id"] in [pair["study_a_id"], pair["study_b_id"]]:
                        if pair["relation"] == "not_directly_comparable":
                            status = "not_directly_comparable"
                            reason = pair["explanation"]
                            break
                        elif pair["relation"] == "conflicting":
                            status = "conflicting"
                            reason = pair["explanation"]
                            break

            matrix.append({
                "document_id": study["document_id"],
                "title": study["title"],
                "population": study["population"],
                "method": study["method"],
                "outcome_measure": study["outcome_measure"],
                "finding": study["finding"][:200] + ("..." if len(study["finding"]) > 200 else ""),
                "status": status,
                "reason": reason
            })

        # 5. Identify Gaps
        gaps = []
        missing_count = sum(1 for m in matrix if m["status"] == "missing")
        if missing_count > 0:
            gaps.append(f"{missing_count} out of {len(matrix)} studies lack direct empirical evidence on '{question}'.")
        
        has_human_eval = any("human" in s["population"].lower() or "human" in s["method"].lower() for s in studies_data)
        if not has_human_eval:
            gaps.append("None of the compared studies evaluated human expert ratings or user clinical outcomes.")
            
        if not gaps:
            gaps.append("Comprehensive coverage across surveyed studies; further ablation on diverse datasets recommended.")

        # 6. Reading Priority Ranking
        def score_study(s):
            score = 0
            if s["finding"] != "unavailable":
                score += 5
            if s["population"] != "unavailable":
                score += 2
            if s["method"] != "unavailable":
                score += 2
            if len(s["passages"]) > 0:
                score += 1
            return score

        ranked = sorted(studies_data, key=score_study, reverse=True)
        reading_priority = [
            {
                "rank": idx + 1,
                "document_id": s["document_id"],
                "title": s["title"],
                "reason": "High relevance to question with verified empirical extraction." if s["finding"] != "unavailable" else "Secondary background reading; lacking direct outcome data."
            }
            for idx, s in enumerate(ranked)
        ]

        return {
            "question": question,
            "studies": studies_data,
            "matrix": matrix,
            "pairwise_comparisons": pairwise_comparisons,
            "gaps": gaps,
            "reading_priority": reading_priority
        }

    @classmethod
    def _evaluate_pairwise_comparability(cls, s1: Dict[str, Any], s2: Dict[str, Any], question: str) -> Dict[str, Any]:
        """
        Enforce the 4-Dimension Comparability Guard:
        Examines (1) Population/Dataset, (2) Setting, (3) Method, (4) Outcome Measure.
        """
        diffs = []
        
        # Dimension 1: Population / Dataset
        p1 = s1["population"].lower()
        p2 = s2["population"].lower()
        if p1 != "unavailable" and p2 != "unavailable":
            stopwords = {"the", "a", "an", "in", "on", "of", "and", "or", "to", "for", "with", "at", "by", "from", "is", "was", "are", "were", "participants", "cohort", "primary", "dataset"}
            words1 = {w for w in re.findall(r"\w+", p1) if len(w) > 2 and w not in stopwords}
            words2 = {w for w in re.findall(r"\w+", p2) if len(w) > 2 and w not in stopwords}
            if words1 and words2:
                overlap = words1.intersection(words2)
                overlap_ratio = len(overlap) / min(len(words1), len(words2))
                if overlap_ratio < 0.35:
                    diffs.append(f"Different population/datasets: '{s1['population']}' vs '{s2['population']}'")

        # Dimension 2: Setting
        if s1["setting"].lower() != s2["setting"].lower():
            diffs.append(f"Different experimental settings: '{s1['setting']}' vs '{s2['setting']}'")

        # Dimension 3: Method
        m1 = s1["method"].lower()
        m2 = s2["method"].lower()
        if m1 != "unavailable" and m2 != "unavailable":
            stopwords = {"the", "a", "an", "in", "on", "of", "and", "or", "to", "for", "with", "at", "by", "from", "is", "was", "are", "were", "methodology", "method"}
            words1 = {w for w in re.findall(r"\w+", m1) if len(w) > 2 and w not in stopwords}
            words2 = {w for w in re.findall(r"\w+", m2) if len(w) > 2 and w not in stopwords}
            if words1 and words2:
                overlap = words1.intersection(words2)
                overlap_ratio = len(overlap) / min(len(words1), len(words2))
                if overlap_ratio < 0.35:
                    diffs.append(f"Different methodologies: '{s1['method']}' vs '{s2['method']}'")

        # Dimension 4: Outcome Measure
        o1 = s1["outcome_measure"].lower()
        o2 = s2["outcome_measure"].lower()
        if o1 != o2 and o1 != "unavailable" and o2 != "unavailable":
            diffs.append(f"Different outcome measures: '{s1['outcome_measure']}' vs '{s2['outcome_measure']}'")

        # Analyze findings direction
        f1 = s1["finding"].lower()
        f2 = s2["finding"].lower()
        
        if f1 == "unavailable" or f2 == "unavailable":
            return {
                "study_a_id": s1["document_id"],
                "study_a_title": s1["title"],
                "study_b_id": s2["document_id"],
                "study_b_title": s2["title"],
                "relation": "missing",
                "explanation": "One or both studies lack empirical findings on this question.",
                "differing_dimensions": diffs
            }

        # Check for opposing signals
        opposing_words = [
            ("outperform", "underperform"),
            ("increase", "decrease"),
            ("superior", "inferior"),
            ("positive", "negative"),
            ("effective", "ineffective")
        ]
        has_divergent_findings = False
        for pos, neg in opposing_words:
            if (pos in f1 and neg in f2) or (neg in f1 and pos in f2):
                has_divergent_findings = True
                break

        # CORE GUARD: If findings diverge, can we call it contradictory?
        if has_divergent_findings:
            if diffs:
                return {
                    "study_a_id": s1["document_id"],
                    "study_a_title": s1["title"],
                    "study_b_id": s2["document_id"],
                    "study_b_title": s2["title"],
                    "relation": "not_directly_comparable",
                    "explanation": f"Findings appear divergent, but studies differ in {len(diffs)} core dimension(s): {'; '.join(diffs)}. They are not directly comparable and cannot be classified as contradictory.",
                    "differing_dimensions": diffs
                }
            else:
                return {
                    "study_a_id": s1["document_id"],
                    "study_a_title": s1["title"],
                    "study_b_id": s2["document_id"],
                    "study_b_title": s2["title"],
                    "relation": "conflicting",
                    "explanation": "Studies evaluate equivalent populations and methods with directly contradictory conclusions.",
                    "differing_dimensions": []
                }
        else:
            if diffs:
                return {
                    "study_a_id": s1["document_id"],
                    "study_a_title": s1["title"],
                    "study_b_id": s2["document_id"],
                    "study_b_title": s2["title"],
                    "relation": "not_directly_comparable",
                    "explanation": f"Studies evaluate complementary domains with differing dimensions: {'; '.join(diffs)}.",
                    "differing_dimensions": diffs
                }
            else:
                return {
                    "study_a_id": s1["document_id"],
                    "study_a_title": s1["title"],
                    "study_b_id": s2["document_id"],
                    "study_b_title": s2["title"],
                    "relation": "supporting",
                    "explanation": "Both studies evaluate aligned populations and methodologies with mutually reinforcing conclusions.",
                    "differing_dimensions": []
                }
