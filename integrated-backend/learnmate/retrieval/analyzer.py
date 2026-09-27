"""
The text analyzer behind the server-side BM25 index.

    text  ->  NFKD, lowercase  ->  [a-z0-9]+ tokens  ->  drop stopwords  ->  Porter stem

The in-process BM25 in bm25.py matched raw lowercase words, so "duty" never met "duties"
and every "the" in a question scored against every "the" in a chunk (IDF keeps that small,
but not zero). A lexical retriever is only as good as its analyzer, and this is the
standard one: the same pipeline Lucene's EnglishAnalyzer runs, minus possessive handling,
which the tokenizer's apostrophe split already covers.

Everything here is deterministic and dependency-free on purpose. The sparse vectors built
from these tokens are written into Qdrant at ingest and compared against query vectors
built at search time, possibly by a different process on a different machine -- so the
analyzer is part of the index format. ANALYZER_VERSION is stamped on every point; change
the pipeline and that string together, then re-run scripts/reindex_qdrant.py.
"""

import re
import unicodedata
from functools import lru_cache
from typing import List

ANALYZER_VERSION = "bm25-porter-v1"

_TOKEN = re.compile(r"[a-z0-9]+")

# A conventional English list: function words that carry no topic. Deliberately not the
# aggressive 500-word kind -- "state", "right", "case" and "order" are stopwords to a
# general-purpose engine and content words to a law student.
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before
being below between both but by can could did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is
it its itself just me more most my myself no nor not now of off on once only or other our
ours ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we
were what when where which while who whom why will with would you your yours yourself
yourselves also may might must shall s t d ll m o re ve y
""".split())


def _is_consonant(word: str, i: int) -> bool:
    """Porter's consonant: not a vowel, and 'y' only when it follows a vowel (or starts)."""
    ch = word[i]
    if ch in "aeiou":
        return False
    if ch == "y":
        return i == 0 or not _is_consonant(word, i - 1)
    return True


def _measure(stem: str) -> int:
    """m in [C](VC)^m[V]: how many vowel-consonant sequences the stem contains."""
    n, i, length = 0, 0, len(stem)
    while i < length and _is_consonant(stem, i):
        i += 1
    while i < length:
        while i < length and not _is_consonant(stem, i):
            i += 1
        if i >= length:
            break
        while i < length and _is_consonant(stem, i):
            i += 1
        n += 1
    return n


def _has_vowel(stem: str) -> bool:
    return any(not _is_consonant(stem, i) for i in range(len(stem)))


def _double_consonant(word: str) -> bool:
    return (len(word) >= 2 and word[-1] == word[-2]
            and _is_consonant(word, len(word) - 1))


def _cvc(word: str) -> bool:
    """Ends consonant-vowel-consonant, the last not w, x or y (hop, not snow)."""
    return (len(word) >= 3 and _is_consonant(word, len(word) - 3)
            and not _is_consonant(word, len(word) - 2)
            and _is_consonant(word, len(word) - 1)
            and word[-1] not in "wxy")


# (suffix, replacement), longest first so the first match is the one Porter's reference
# implementation would take. A matched suffix whose stem fails the measure test stops the
# step -- a shorter suffix is not tried -- which is also what the reference does.
_STEP2 = sorted([
    ("ational", "ate"), ("tional", "tion"), ("enci", "ence"), ("anci", "ance"),
    ("izer", "ize"), ("bli", "ble"), ("alli", "al"), ("entli", "ent"), ("eli", "e"),
    ("ousli", "ous"), ("ization", "ize"), ("ation", "ate"), ("ator", "ate"),
    ("alism", "al"), ("iveness", "ive"), ("fulness", "ful"), ("ousness", "ous"),
    ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"), ("logi", "log"),
], key=lambda pair: -len(pair[0]))

_STEP3 = sorted([
    ("icate", "ic"), ("ative", ""), ("alize", "al"), ("iciti", "ic"), ("ical", "ic"),
    ("ful", ""), ("ness", ""),
], key=lambda pair: -len(pair[0]))

_STEP4 = sorted([
    "al", "ance", "ence", "er", "ic", "able", "ible", "ant", "ement", "ment", "ent",
    "ion", "ou", "ism", "ate", "iti", "ous", "ive", "ize",
], key=lambda suffix: -len(suffix))


def _replace(word: str, rules, min_measure: int) -> str:
    for suffix, replacement in rules:
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            return stem + replacement if _measure(stem) > min_measure else word
    return word


@lru_cache(maxsize=65536)
def stem(word: str) -> str:
    """
    The Porter (1980) stemmer, as in Martin Porter's reference implementation.

    Cached: a textbook repeats a few thousand distinct words tens of thousands of times,
    and indexing re-stems every occurrence otherwise.
    """
    if len(word) <= 2 or not word.isalpha():
        return word

    # Step 1a: plurals.
    if word.endswith("sses"):
        word = word[:-2]
    elif word.endswith("ies"):
        word = word[:-2]
    elif word.endswith("ss"):
        pass
    elif word.endswith("s"):
        word = word[:-1]

    # Step 1b: -ed and -ing.
    trimmed = False
    if word.endswith("eed"):
        if _measure(word[:-3]) > 0:
            word = word[:-1]
    elif word.endswith("ed") and _has_vowel(word[:-2]):
        word, trimmed = word[:-2], True
    elif word.endswith("ing") and _has_vowel(word[:-3]):
        word, trimmed = word[:-3], True
    if trimmed:
        if word.endswith(("at", "bl", "iz")):
            word += "e"
        elif _double_consonant(word) and word[-1] not in "lsz":
            word = word[:-1]
        elif _measure(word) == 1 and _cvc(word):
            word += "e"

    # Step 1c: terminal y after a vowel-bearing stem.
    if word.endswith("y") and _has_vowel(word[:-1]):
        word = word[:-1] + "i"

    # Steps 2-4: derivational suffixes, each gated on the measure of what is left.
    word = _replace(word, _STEP2, 0)
    word = _replace(word, _STEP3, 0)
    for suffix in _STEP4:
        if word.endswith(suffix):
            stem_part = word[: -len(suffix)]
            if _measure(stem_part) > 1 and (
                    suffix != "ion" or stem_part.endswith(("s", "t"))):
                word = stem_part
            break

    # Step 5: a final e, and a double l.
    if word.endswith("e"):
        stem_part = word[:-1]
        measure = _measure(stem_part)
        if measure > 1 or (measure == 1 and not _cvc(stem_part)):
            word = stem_part
    if word.endswith("ll") and _measure(word) > 1:
        word = word[:-1]
    return word


def _normalise(text: str) -> str:
    """Fold accents and case, so "Café" and "cafe" are one term."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def display_tokens(text: str) -> List[str]:
    """
    Lowercased, stopword-free words, *not* stemmed.

    For anything a person reads -- topic labels in the confusion heatmap, say. Stems are
    index terms, not words: "fiduciary" is stored as "fiduciari", which is right for
    matching and wrong for a label.
    """
    return [token for token in _TOKEN.findall(_normalise(text))
            if token not in STOPWORDS and (len(token) > 1 or token.isdigit())]


def analyze(text: str) -> List[str]:
    """The index terms of `text`, in order and with repeats (term frequency matters)."""
    return [stem(token) for token in display_tokens(text)]
