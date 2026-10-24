import fitz

def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(50, 50, 550, 750), text)
    b = doc.tobytes()
    doc.close()
    return b

text = "In the multicenter randomized trial, participants randomized to adaptive closed-loop protocol achieved 92.4% retention at week 12 compared to 78.1% in static controls. Secondary fatigue was reduced solely in the severe baseline fatigue subgroup. Headaches were never recorded."
pdf_bytes = make_pdf(text)
doc = fitz.open(stream=pdf_bytes, filetype="pdf")
print("Extracted Wrapped:\n", doc[0].get_text())
