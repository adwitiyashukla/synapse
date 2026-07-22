"""Recursive text splitter.

Splits on paragraph boundaries first, then sentences, then words, keeping
chunks near the target size with a configurable overlap. Implemented from
scratch to keep the pipeline dependency-light and fully transparent.
"""

import re

_SEPARATORS = ["\n\n", "\n", ". ", " "]


def split_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    """Split text into overlapping chunks of roughly chunk_size characters."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    pieces = _recursive_split(text, chunk_size, _SEPARATORS)
    return _merge_with_overlap(pieces, chunk_size, overlap)


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    if not separators:
        # Hard split as a last resort
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    separator, *rest = separators
    parts = [p for p in text.split(separator) if p.strip()]
    if len(parts) == 1:
        return _recursive_split(text, chunk_size, rest)

    result: list[str] = []
    for part in parts:
        candidate = part if part.endswith(separator.strip()) else part + separator
        if len(candidate) > chunk_size:
            result.extend(_recursive_split(candidate, chunk_size, rest))
        else:
            result.append(candidate)
    return result


def _merge_with_overlap(pieces: list[str], chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current.strip())
            # Seed the next chunk with the tail of the previous one
            current = current[-overlap:] if overlap > 0 else ""
        current += piece if current == "" or current.endswith((" ", "\n")) else " " + piece
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]
