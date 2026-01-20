"""
wordfreq_core.py

Core logic for:
- reading text
- segmenting into N chunks
- tokenizing
- per-segment word counting (thread worker)
- merging counts
- top-k extraction
"""

from __future__ import annotations

import re
from collections import Counter
from typing import List, Dict, Tuple


# Tokenization rule:
# - lowercase
# - keep letters/digits
# - allow one apostrophe chunk inside a word (e.g., don't, we're)
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?")

def read_text_lines(file_path: str) -> List[str]:
    """Read file as UTF-8 (with graceful fallback) and return list of lines."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()
    except UnicodeDecodeError:
        # fallback: replace invalid chars
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()


def segment_lines(lines: List[str], n_segments: int) -> List[List[str]]:
    """
    Split lines into n_segments chunks as evenly as possible.
    Each segment is a list of lines.
    """
    if n_segments <= 0:
        raise ValueError("n_segments must be >= 1")

    total = len(lines)
    if total == 0:
        return [[] for _ in range(n_segments)]

    # If N > number of lines, cap N so each segment has at least 1 line (when possible)
    n_segments = min(n_segments, total)

    base = total // n_segments
    remainder = total % n_segments

    segments: List[List[str]] = []
    idx = 0
    for i in range(n_segments):
        size = base + (1 if i < remainder else 0)
        segments.append(lines[idx: idx + size])
        idx += size

    return segments


def tokenize(text: str) -> List[str]:
    """
    Convert text to lowercase and extract tokens using regex.
    Returns list of words.
    """
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]


def count_segment_words(segment_lines: List[str], segment_id: int) -> Dict[str, int]:
    """
    Worker function for one segment.
    Returns a dict(word -> count) for that segment.
    """
    c = Counter()
    for line in segment_lines:
        for tok in tokenize(line):
            c[tok] += 1
    # Return a plain dict for JSON friendliness / simpler printing if desired
    return dict(c)


def merge_counts(segment_counts: List[Dict[str, int]]) -> Dict[str, int]:
    """Merge list of dict(word->count) into one final dict."""
    final = Counter()
    for d in segment_counts:
        final.update(d)
    return dict(final)


def top_k(freq: Dict[str, int], k: int) -> List[Tuple[str, int]]:
    """
    Return top-k words sorted by:
    - count descending
    - word ascending (tie-breaker)
    """
    if k <= 0:
        return []
    items = list(freq.items())
    items.sort(key=lambda x: (-x[1], x[0]))
    return items[:k]


def total_tokens(freq: Dict[str, int]) -> int:
    """Total tokens counted (sum of all frequencies)."""
    return sum(freq.values())
