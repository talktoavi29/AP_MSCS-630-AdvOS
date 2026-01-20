Lab 1: Word Frequency Counter Using Multithreading (Python)

Files:
- wordfreq_mt.py      (CLI runner)
- wordfreq_core.py    (core logic)

Requirements:
- Python 3.9+ (no external libraries needed)

How to run:
  python wordfreq_mt.py <input_file> <N> [--k-thread 10] [--k-final 20]

Example:
  python wordfreq_mt.py sample.txt 4 --k-thread 10 --k-final 20

The program:
- Reads the input file
- Splits the file into N segments by lines
- Uses N threads to count words per segment
- Prints intermediate top-K results per segment
- Merges results and prints final top-K words

Tokenization rule:
- lowercases text
- words include letters/digits and optional apostrophes inside a word (e.g., don't)