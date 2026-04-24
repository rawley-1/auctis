from pathlib import Path
from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "raw_cases"
OPINIONS_DIR = BASE_DIR / "opinions"

OPINIONS_DIR.mkdir(exist_ok=True)

def main():
    pdf_files = list(RAW_DIR.glob("*.pdf"))

    if not pdf_files:
        print("No PDFs found in raw_cases.")
        return

    for pdf_path in pdf_files:
        print(f"Converting {pdf_path.name}...")

        reader = PdfReader(str(pdf_path))
        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        out_path = OPINIONS_DIR / f"{pdf_path.stem}.txt"

        out_path.write_text("\n\n".join(text_parts), encoding="utf-8")

        print(f"Saved {out_path.name}")

if __name__ == "__main__":
    main()
