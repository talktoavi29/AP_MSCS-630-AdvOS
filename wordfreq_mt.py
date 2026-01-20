"""
wordfreq_mt.py

CLI runner for the multithreaded word frequency counter.

Usage:
  python wordfreq_mt.py <input_file> <N> [--k-thread 10] [--k-final 20]

Example:
  python wordfreq_mt.py sample.txt 4 --k-thread 10 --k-final 20
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

import wordfreq_core as core


def count_words_multithreaded(segments: List[List[str]], max_workers: int) -> List[Dict[str, int]]:
    """
    Run one thread per segment (via ThreadPoolExecutor) and collect per-segment dicts.
    This list is the required 'intermediate data structure'.
    """
    if max_workers <= 0:
        raise ValueError("max_workers must be >= 1")

    segment_counts: List[Dict[str, int]] = [None] * len(segments)  # type: ignore

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = []
        for seg_id, seg_lines in enumerate(segments):
            fut = ex.submit(core.count_segment_words, seg_lines, seg_id)
            futures.append((seg_id, fut))

        # Wait for all to finish (future.result() blocks until done)
        for seg_id, fut in futures:
            segment_counts[seg_id] = fut.result()

    return segment_counts


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Word Frequency Counter using multithreading (N segments).")
    p.add_argument("input_file", help="Path to the input text file.")
    p.add_argument("N", type=int, help="Number of segments / threads.")
    p.add_argument("--k-thread", type=int, default=10, help="Top-K words to show per thread (default: 10).")
    p.add_argument("--k-final", type=int, default=20, help="Top-K words to show for final result (default: 20).")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    lines = core.read_text_lines(args.input_file)
    if len(lines) == 0:
        print("Input file appears to be empty. Nothing to count.")
        return

    if args.N <= 0:
        raise SystemExit("Error: N must be >= 1")

    # Segment by lines (safe: does not split words across boundaries)
    segments = core.segment_lines(lines, args.N)
    actual_n = len(segments)

    print(f"Input file: {args.input_file}")
    print(f"Requested segments (N): {args.N}")
    if actual_n != args.N:
        print(f"Adjusted segments to: {actual_n} (cannot exceed number of lines)")
    print("-" * 60)

    # Multithreaded count
    segment_counts = count_words_multithreaded(segments, max_workers=actual_n)

    # Intermediate results (top-k per segment)
    for i, freq in enumerate(segment_counts):
        top = core.top_k(freq, args.k_thread)
        seg_tokens = core.total_tokens(freq)
        unique = len(freq)
        print(f"[Thread/Segment {i}] tokens={seg_tokens}, unique_words={unique}, top-{args.k_thread}:")
        for w, c in top:
            print(f"  {w}: {c}")
        print("-" * 60)

    # Merge
    final_counts = core.merge_counts(segment_counts)
    final_top = core.top_k(final_counts, args.k_final)

    print("FINAL CONSOLIDATED RESULTS")
    print(f"Total tokens: {core.total_tokens(final_counts)}")
    print(f"Unique words: {len(final_counts)}")
    print(f"Top-{args.k_final} words:")
    for w, c in final_top:
        print(f"  {w}: {c}")


if __name__ == "__main__":
    main()
