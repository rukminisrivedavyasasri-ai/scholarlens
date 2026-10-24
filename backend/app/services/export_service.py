import csv
import io
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from backend.app.models.board import EvidenceBoardItem
from backend.app.models.document import Document
from backend.app.services.acl_service import get_permitted_document_ids

class ExportService:
    """
    Export Service generating structured Markdown and CSV exports from the Evidence Board.
    Enforces strict pre-retrieval authorization: users can only export evidence derived from
    documents they are permitted to view.
    """

    @classmethod
    async def export_board(
        cls,
        db: AsyncSession,
        workspace_id: str,
        user_id: str,
        user_role: str,
        export_format: str = "markdown",
        status_filter: str = "approved"
    ) -> Dict[str, Any]:
        export_format = export_format.lower()
        if export_format not in ["markdown", "csv"]:
            raise HTTPException(status_code=400, detail="Invalid export format. Only 'markdown' and 'csv' are supported.")

        # 1. Negative authorization check: Get permitted doc IDs
        permitted_doc_ids = await get_permitted_document_ids(db, user_id)
        if not permitted_doc_ids:
            if export_format == "markdown":
                return {
                    "filename": f"evidence_board_{workspace_id}.md",
                    "media_type": "text/markdown",
                    "content": "# Research Evidence Synthesis Board\n\n*No permitted documents or evidence items accessible.*"
                }
            else:
                return {
                    "filename": f"evidence_board_{workspace_id}.csv",
                    "media_type": "text/csv",
                    "content": "id,title,document_title,claim,page_number,evidence_status,board_status,citation_excerpt\n"
                }

        # 2. Query board items belonging to permitted documents only
        stmt = select(EvidenceBoardItem).where(
            EvidenceBoardItem.workspace_id == workspace_id,
            EvidenceBoardItem.document_id.in_(permitted_doc_ids)
        )
        if status_filter:
            stmt = stmt.where(EvidenceBoardItem.board_status == status_filter)
        stmt = stmt.order_by(EvidenceBoardItem.created_at.desc())
        
        res = await db.execute(stmt)
        items = res.scalars().all()

        docs_res = await db.execute(select(Document).where(Document.id.in_(permitted_doc_ids)))
        docs = {doc.id: doc.title for doc in docs_res.scalars().all()}

        if export_format == "markdown":
            content = cls._generate_markdown(items, docs, workspace_id, status_filter)
            return {
                "filename": f"evidence_board_{workspace_id}.md",
                "media_type": "text/markdown",
                "content": content
            }
        else:
            content = cls._generate_csv(items, docs)
            return {
                "filename": f"evidence_board_{workspace_id}.csv",
                "media_type": "text/csv",
                "content": content
            }

    @classmethod
    def _generate_markdown(cls, items: List[EvidenceBoardItem], docs: Dict[str, str], workspace_id: str, status_filter: str) -> str:
        lines = [
            f"# Research Evidence Synthesis Board",
            f"**Workspace ID:** `{workspace_id}`  ",
            f"**Export Status Filter:** `{status_filter.upper()}`  ",
            f"**Total Records:** {len(items)}  ",
            "",
            "---",
            ""
        ]

        if not items:
            lines.append("*No evidence items found for the selected filter.*")
            return "\n".join(lines)

        for idx, item in enumerate(items, 1):
            doc_title = docs.get(item.document_id, "Unknown Document")
            page_str = f"Page {item.page_number}" if item.page_number else "Page N/A"
            lines.append(f"### {idx}. {item.title}")
            lines.append(f"- **Document:** {doc_title}")
            lines.append(f"- **Evidence Status:** `{item.evidence_status}` | **Board State:** `{item.board_status}`")
            lines.append(f"- **Claim:** {item.claim}")
            lines.append(f"- **Citation Location:** {page_str}")
            if item.citation_excerpt:
                lines.append(f"- **Verifiable Excerpt:**\n  > \"{item.citation_excerpt}\"")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def _generate_csv(cls, items: List[EvidenceBoardItem], docs: Dict[str, str]) -> str:
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        writer.writerow([
            "id",
            "title",
            "document_title",
            "claim",
            "page_number",
            "evidence_status",
            "board_status",
            "citation_excerpt"
        ])

        for item in items:
            doc_title = docs.get(item.document_id, "Unknown Document")
            writer.writerow([
                item.id,
                item.title,
                doc_title,
                item.claim,
                item.page_number or "",
                item.evidence_status,
                item.board_status,
                (item.citation_excerpt or "").replace("\n", " ").strip()
            ])

        return output.getvalue()
