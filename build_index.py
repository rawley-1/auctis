import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI


# =========================
# CONFIG
# =========================

MODEL = "text-embedding-3-small"
ROOT = Path(__file__).resolve().parent
OPINIONS_DIR = ROOT / "opinions"
DOCTRINES_DIR = ROOT / "doctrines"
OUTFILE = ROOT / "index.json"

MAX_CHARS = 1800
OVERLAP_CHARS = 250

client = OpenAI()


# =========================
# CLEANING
# =========================

def clean_opinion_text(text: str) -> str:
    if not text:
        return ""

    text = str(text)

    text = text.replace("\xad", "")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = text.replace("—", "-").replace("–", "-")

    # Remove common OCR/page artifacts
    text = re.sub(r"\bPage\s+\d+\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d+\s+of\s+\d+\b", " ", text, flags=re.I)
    text = re.sub(r"\*+\d+\s*", " ", text)

    # Fix hyphenated OCR line breaks
    text = re.sub(r"([A-Za-z])-[\s\n]+([A-Za-z])", r"\1\2", text)

    # Collapse spacing
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_source_name(path: Path) -> str:
    return path.name.lower().replace("_", " ")


# =========================
# DOCTRINE INFERENCE
# =========================

def infer_doctrine_line(source: str, text: str = "") -> str:
    s = (source or "").lower()
    t = (text or "").lower()
    combined = f"{s} {t}"

    if any(x in combined for x in ["caremark", "stone", "marchand", "oversight", "red flag", "mission critical"]):
        return "oversight"

    if any(x in combined for x in ["revlon", "qvc", "lyondell", "barkan", "sale of control", "change of control"]):
        return "sale_of_control"

    if any(x in combined for x in ["unocal", "unitrin", "airgas", "defensive measure", "coercive", "preclusive"]):
        return "takeover_defense"

    if any(x in combined for x in ["mfw", "kahn", "controller", "majority of the minority", "special committee"]):
        return "controller_transactions"

    if any(x in combined for x in ["corwin", "fully informed", "uncoerced"]):
        return "stockholder_vote_cleansing"

    if any(x in combined for x in ["aronson", "rales", "zuckerberg", "demand futility"]):
        return "demand_futility"

    if any(x in combined for x in ["weinberger", "entire fairness", "fair dealing", "fair price"]):
        return "entire_fairness"

    if "blasius" in combined:
        return "blasius"

    if "schnell" in combined:
        return "schnell"

    if any(x in combined for x in ["section 220", "books and records", "credible basis", "proper purpose"]):
        return "section_220"

    if any(x in combined for x in ["malone", "disclosure", "materially misleading"]):
        return "disclosure_loyalty"

    return "general"


def infer_chunk_role(text: str) -> str:
    t = (text or "").lower()

    if any(x in t for x in ["standard", "must", "requires", "duty", "obligation", "test", "rule"]):
        return "rule"

    if any(x in t for x in ["here", "in this case", "complaint", "plaintiff", "defendant", "board failed"]):
        return "application"

    if any(x in t for x in ["background", "facts", "agreement", "transaction", "merger"]):
        return "facts"

    if any(x in t for x in ["dismiss", "motion", "affirm", "reverse", "remand"]):
        return "procedural"

    return "general"


# =========================
# QUALITY SCORING
# =========================

def chunk_quality_score(text: str) -> int:
    if not text:
        return 0

    score = 100
    t = text.lower()
    words = text.split()

    if len(words) < 25:
        score -= 25

    if len(words) > 450:
        score -= 10

    bad_markers = [
        "reashowing",
        "dangrounds",
        "selectresponse",
        "the po in that",
        "shareequitable",
        "corpothe",
        "thestockhold",
        "rbc never- least",
        "must respond theless",
        "serve as the ad hoe",
        "valua- fairness",
        "tion football field",
        "judge process conduct neither",
    ]

    for marker in bad_markers:
        if marker in t:
            score -= 35

    tiny_words = [w for w in words if len(w.strip(".,;:()[]{}\"'")) <= 2]
    if words and len(tiny_words) / len(words) > 0.34:
        score -= 30

    weird_words = [
        w for w in words
        if len(w) > 18 and not re.search(r"[aeiouAEIOU]", w)
    ]
    score -= min(30, len(weird_words) * 10)

    if text.count("§") >= 3:
        score -= 20

    if text.count(",") > 35:
        score -= 15

    if not re.search(r"[.!?]", text):
        score -= 20

    return max(0, min(100, score))


def is_corrupt_chunk(text: str) -> bool:
    return chunk_quality_score(text) < 45


# =========================
# CHUNKING
# =========================

def split_into_paragraphs(text: str) -> List[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    paragraphs = split_into_paragraphs(text)

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current.strip())

            if len(para) <= max_chars:
                current = para
            else:
                start = 0
                while start < len(para):
                    end = start + max_chars
                    chunks.append(para[start:end].strip())
                    start = max(0, end - overlap)
                current = ""

    if current:
        chunks.append(current.strip())

    return chunks


# =========================
# EMBEDDINGS
# =========================

def embed_text(text: str) -> List[float]:
    response = client.embeddings.create(
        model=MODEL,
        input=text,
    )
    return response.data[0].embedding


# =========================
# FILE LOADING
# =========================

def load_text_files(directory: Path, source_type: str) -> List[Dict[str, Any]]:
    files = []

    if not directory.exists():
        print(f"WARNING: missing directory: {directory}")
        return files

    for path in sorted(directory.glob("*.txt")):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_opinion_text(raw)

        if not cleaned:
            continue

        files.append(
            {
                "path": path,
                "source": normalize_source_name(path),
                "source_type": source_type,
                "text": cleaned,
            }
        )

    return files


# =========================
# BUILD INDEX
# =========================

def build_index() -> List[Dict[str, Any]]:
    documents = []
    documents.extend(load_text_files(OPINIONS_DIR, "opinion"))
    documents.extend(load_text_files(DOCTRINES_DIR, "doctrine"))

    print(f"Loaded {len(documents)} documents.")

    index = []
    total_chunks = 0

    for doc in documents:
        source = doc["source"]
        source_type = doc["source_type"]
        text = doc["text"]

        doctrine_line = infer_doctrine_line(source, text)
        chunks = chunk_text(text)

        print(f"{source}: {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            quality = chunk_quality_score(chunk)
            corrupt = quality < 45

            # Keep corrupt chunks out of the index entirely.
            # This is the biggest quality improvement.
            if corrupt:
                continue

            chunk_role = infer_chunk_role(chunk)

            embedding = embed_text(chunk)

            index.append(
                {
                    "source": source,
                    "source_type": source_type,
                    "chunk_id": f"{source}:{i}",
                    "text": chunk,
                    "embedding": embedding,
                    "doctrine_line": doctrine_line,
                    "chunk_role": chunk_role,
                    "quality_score": quality,
                    "corrupt": corrupt,
                }
            )

            total_chunks += 1

    return index


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Run: export OPENAI_API_KEY='your-key-here'"
        )

    index = build_index()

    OUTFILE.write_text(
        json.dumps(index, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved {len(index)} chunks to {OUTFILE}")


if __name__ == "__main__":
    main()
