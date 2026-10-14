"""Text relevance between a document and a job description.

`lexical_similarity` is a dependency-free cosine over stemmed content words. When an embedding
model is configured, `EmbeddingSimilarity` is used instead; both return a *calibrated* 0..1
relevance so the scoring weights mean the same thing regardless of backend.
"""

import math
import re
from collections import Counter
from typing import Protocol

from apps.api.services.llm import LLMClient, cosine

STOPWORDS = set("""
a an and are as at be been being but by can could did do does for from had has have having he her hers him his how i
if in into is it its me my myself no nor not of on or our ours out over own same she should so some such than that the
their them then there these they this those through to too under until up very was we were what when where which while
who whom why will with would you your yours am also dear sir madam regards sincerely yours faithfully position role
job apply application opportunity company team work working
""".split())


def _stem(word: str) -> str:
    for suffix in ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ed", "es", "ly", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def tokens(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z][a-z+#&]{1,}", text.lower()) if w not in STOPWORDS]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if s.strip()]


def raw_cosine(a: str, b: str) -> float:
    va, vb = Counter(tokens(a)), Counter(tokens(b))
    # sublinear tf dampens keyword stuffing
    wa = {t: 1 + math.log(c) for t, c in va.items()}
    wb = {t: 1 + math.log(c) for t, c in vb.items()}
    dot = sum(wa[t] * wb[t] for t in wa.keys() & wb.keys())
    na, nb = math.sqrt(sum(v * v for v in wa.values())), math.sqrt(sum(v * v for v in wb.values()))
    return dot / (na * nb) if na and nb else 0.0


def _calibrate(value: float, floor: float, ceiling: float) -> float:
    return max(0.0, min(1.0, (value - floor) / (ceiling - floor)))


def lexical_similarity(a: str, b: str) -> float:
    # Unrelated texts sit near 0.03; a strong, on-topic letter lands around 0.35+.
    return _calibrate(raw_cosine(a, b), floor=0.04, ceiling=0.38)


class Similarity(Protocol):
    name: str

    def __call__(self, a: str, b: str) -> float: ...


class LexicalSimilarity:
    name = "lexical"

    def __call__(self, a: str, b: str) -> float:
        return lexical_similarity(a, b)


class EmbeddingSimilarity:
    name = "embedding"

    def __init__(self, client: LLMClient, floor: float = 0.15, ceiling: float = 0.65):
        self.client, self.floor, self.ceiling = client, floor, ceiling

    def __call__(self, a: str, b: str) -> float:
        vectors = self.client.embed([a[:8000], b[:8000]])
        if not vectors:
            return lexical_similarity(a, b)
        return _calibrate(cosine(vectors[0], vectors[1]), self.floor, self.ceiling)


def similarity_from_env() -> Similarity:
    client = LLMClient.from_env()
    if client and client.embedding_model:
        return EmbeddingSimilarity(client)
    return LexicalSimilarity()
