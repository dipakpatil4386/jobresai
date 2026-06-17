import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

_STOP_WORDS = frozenset({
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but',
    'by', 'can', 'did', 'do', 'does', 'doing', 'don', 'down', 'during', 'each', 'few', 'for',
    'from', 'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself',
    'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just',
    'me', 'more', 'most', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on', 'once',
    'only', 'or', 'other', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she',
    'should', 'so', 'some', 'such', 'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves',
    'then', 'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too', 'under', 'until',
    'up', 'very', 'was', 'we', 'were', 'what', 'when', 'where', 'which', 'while', 'who', 'whom',
    'why', 'with', 'you', 'your', 'yours', 'yourself', 'yourselves',
})


class TfidfVectorizer:
    def __init__(
        self,
        max_features: int = 5000,
        stop_words: str = 'english',
        ngram_range: Tuple[int, int] = (1, 1),
    ):
        self.max_features = max_features
        self.ngram_range = ngram_range
        self._stop = _STOP_WORDS if stop_words == 'english' else frozenset()
        self._vocab: Dict[str, int] = {}
        self._idf: List[float] = []

    def _analyze(self, text: str) -> List[str]:
        tokens = re.findall(r'\b[a-z][a-z0-9+#./-]{2,}\b', text.lower())
        tokens = [t for t in tokens if t not in self._stop]
        min_n, max_n = self.ngram_range
        features: List[str] = []
        for n in range(min_n, max_n + 1):
            for i in range(len(tokens) - n + 1):
                features.append(' '.join(tokens[i:i + n]) if n > 1 else tokens[i])
        return features

    def _fit(self, docs: Sequence[str]) -> None:
        n_docs = len(docs)
        df: Dict[str, int] = {}
        doc_term_counts: List[Counter] = []

        for doc in docs:
            terms = self._analyze(doc)
            tf = Counter(terms)
            doc_term_counts.append(tf)
            for term in tf:
                df[term] = df.get(term, 0) + 1

        scores: Dict[str, float] = {}
        for term, doc_freq in df.items():
            idf = math.log((1 + n_docs) / (1 + doc_freq)) + 1
            total_tf = sum(tf.get(term, 0) for tf in doc_term_counts)
            scores[term] = total_tf * idf

        ranked = sorted(scores.keys(), key=lambda t: -scores[t])[: self.max_features]
        self._vocab = {term: idx for idx, term in enumerate(ranked)}
        self._idf = [
            math.log((1 + n_docs) / (1 + df.get(term, 0))) + 1
            for term in ranked
        ]

    def _doc_vector(self, doc: str) -> List[float]:
        terms = self._analyze(doc)
        tf = Counter(terms)
        vec = [0.0] * len(self._vocab)
        norm_tf = sum(tf.values()) or 1
        for term, count in tf.items():
            idx = self._vocab.get(term)
            if idx is not None:
                vec[idx] = (count / norm_tf) * self._idf[idx]
        return vec

    def fit_transform(self, raw_documents: Sequence[str]) -> List[List[float]]:
        self._fit(raw_documents)
        return [self._doc_vector(doc) for doc in raw_documents]

    def transform(self, raw_documents: Sequence[str]) -> List[List[float]]:
        return [self._doc_vector(doc) for doc in raw_documents]


def cosine_similarity(
    a: Sequence[Sequence[float]],
    b: Sequence[Sequence[float]],
) -> List[List[float]]:
    def dot(left: Sequence[float], right: Sequence[float]) -> float:
        return sum(x * y for x, y in zip(left, right))

    def norm(vec: Sequence[float]) -> float:
        return math.sqrt(sum(x * x for x in vec)) or 1.0

    return [
        [dot(row_a, row_b) / (norm(row_a) * norm(row_b)) for row_b in b]
        for row_a in a
    ]
