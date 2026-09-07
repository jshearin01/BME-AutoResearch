"""Tiny offline RAG: chunk text, keyword-overlap retrieval. No embeddings needed.

Upgrade path: swap score() for chroma/embeddings later without changing API.
"""

import re

_WORD = re.compile(r"[a-z0-9]{3,}")

STOP = {"the", "and", "for", "with", "this", "that", "from", "have", "were",
        "are", "was", "will", "would", "should", "could", "about", "into",
        "using", "used", "use", "such", "than", "then", "also", "each"}


def tokens(s: str) -> set[str]:
    return {t for t in _WORD.findall(s.lower()) if t not in STOP}


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


def score(query: str, doc: str) -> float:
    q, d = tokens(query), tokens(doc)
    if not q or not d:
        return 0.0
    inter = len(q & d)
    return inter / max(len(q), 1)
