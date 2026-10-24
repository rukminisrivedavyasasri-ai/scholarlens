import fitz  # PyMuPDF
import hashlib
from typing import List, Dict, Any, Tuple
from fastapi import HTTPException, status
from backend.app.config import settings

def validate_pdf_file(filename: str, file_bytes: bytes, content_type: str = "application/pdf"):
    """
    Validates file type and size limits before processing.
    """
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB.",
        )
    
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF documents (.pdf) are allowed.",
        )

    # Magic bytes check for PDF
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File header is not a valid PDF document.",
        )

def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()

def extract_metadata_and_chunks(
    file_bytes: bytes,
    chunk_size: int = 500,
    chunk_overlap: int = 100
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Parses PDF using PyMuPDF, preserving exact 1-based page numbers
    and spatial bounding box coordinates for each passage chunk.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse PDF document: {str(e)}",
        )

    meta = doc.metadata or {}
    pdf_info = {
        "title": meta.get("title") or "Untitled Academic Document",
        "authors": meta.get("author") or "Unknown Author",
        "page_count": len(doc),
    }

    chunks = []
    chunk_global_idx = 0

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_number = page_idx + 1  # 1-based
        page_width = float(page.rect.width)
        page_height = float(page.rect.height)

        # Extract text blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")

        for b in blocks:
            # block_type 0 is text
            if len(b) >= 5 and b[6] == 0:
                text = b[4].strip()
                if not text or len(text) < 15:
                    continue

                x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
                bbox = {
                    "x0": round(x0, 2),
                    "y0": round(y0, 2),
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                    "page_width": round(page_width, 2),
                    "page_height": round(page_height, 2),
                }

                # If block is large, break into overlapping chunks
                if len(text) > chunk_size:
                    start = 0
                    while start < len(text):
                        end = min(start + chunk_size, len(text))
                        chunk_text = text[start:end].strip()
                        if len(chunk_text) >= 15:
                            chunks.append({
                                "page_number": page_number,
                                "chunk_index": chunk_global_idx,
                                "content": chunk_text,
                                "bounding_box": bbox,
                            })
                            chunk_global_idx += 1
                        start += (chunk_size - chunk_overlap)
                else:
                    chunks.append({
                        "page_number": page_number,
                        "chunk_index": chunk_global_idx,
                        "content": text,
                        "bounding_box": bbox,
                    })
                    chunk_global_idx += 1

    doc.close()
    return pdf_info, chunks
