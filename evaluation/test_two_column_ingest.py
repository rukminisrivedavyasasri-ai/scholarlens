import fitz
import sys
from backend.app.services.pdf_parser import extract_metadata_and_chunks, validate_pdf_file

sys.stdout.reconfigure(encoding='utf-8')

def test_two_column():
    pdf_path = "evaluation/benchmark_dataset/dpo_paper.pdf"
    file_bytes = open(pdf_path, "rb").read()
    
    validate_pdf_file("dpo_paper.pdf", file_bytes)
    info, chunks = extract_metadata_and_chunks(file_bytes)
    
    print(f"=== PDF METADATA ===")
    print(f"Title: {info['title']}")
    print(f"Authors: {info['authors']}")
    print(f"Total Pages: {info['page_count']}")
    print(f"Total Chunks Extracted: {len(chunks)}\n")
    
    print("=== INSPECTING FIRST 5 CHUNKS (Page numbers & Spatial Coordinates) ===")
    for i, c in enumerate(chunks[:5]):
        bbox = c["bounding_box"]
        print(f"Chunk #{i+1}: Page {c['page_number']} (Index {c['chunk_index']})")
        print(f"  Coords: [x0={bbox['x0']}, y0={bbox['y0']}, x1={bbox['x1']}, y1={bbox['y1']}]")
        print(f"  Canvas Dimensions: {bbox['page_width']} x {bbox['page_height']}")
        print(f"  Excerpt: {repr(c['content'][:120])}...\n")
        
    # Inspect chunks around tables (Page 7 or 8 typically has the summary comparison table in DPO paper)
    print("=== INSPECTING TABLE / METRICS CHUNKS (Searching for Table / Accuracy / Win Rate) ===")
    table_chunks = [c for c in chunks if "Table" in c["content"] or "Win Rate" in c["content"] or "Summary" in c["content"]]
    for i, c in enumerate(table_chunks[:3]):
        bbox = c["bounding_box"]
        print(f"Table Chunk #{i+1}: Page {c['page_number']}")
        print(f"  Coords: [x0={bbox['x0']}, y0={bbox['y0']}, x1={bbox['x1']}, y1={bbox['y1']}]")
        print(f"  Text: {repr(c['content'][:150])}...\n")

if __name__ == "__main__":
    test_two_column()
