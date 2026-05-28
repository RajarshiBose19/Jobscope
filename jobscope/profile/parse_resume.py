from pathlib import Path
import pdfplumber

def extract_text(pdf_path: Path) -> str:
    out = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            out.append(t)
    return "\n".join(out)
