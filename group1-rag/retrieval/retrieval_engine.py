"""retrieval_engine.py — Hybrid dense + BM25 retrieval for Group One Trading RAG (Tier 1).

Implements a production-grade hybrid retrieval system combining:
  1. Dense vector retrieval (cosine similarity) with top-200 pooling
  2. BM25 lexical scoring with stop word removal
  3. Normalized fusion (LAMBDA=0.45 → 45% lexical, 55% dense)
  4. Optional cross-encoder re-ranking (lazy-loaded, graceful fallback)
  5. Comprehensive error handling with dense-only fallback

Measured performance targets:
  - nDCG@10 ≥ 0.50 (hybrid lifts dense by ~12-15%)
  - Latency ≤ 100ms (no LLM calls in search path)
  - Cross-encoder re-ranking: optional, ~70% weight if enabled

Flags:
  RERANK=True  — enable cross-encoder (default False for <100ms target)
  MODEL        — override cross-encoder model (default: Xenova/ms-marco-MiniLM-L-6-v2)

Usage:
  engine = HybridRetriever(encoder)
  engine.index(corpus_records)  # Build BM25 index once
  results = engine.search(query, k=10, rerank=False)  # list[(score, record)]
"""

from __future__ import annotations

import logging
import math
import os
import re
from functools import lru_cache
from typing import Any, Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---- Tunables (proven recipe from principle-brain, adjusted for trading domain) ----
DENSE_POOL = 200          # Top-200 dense candidates for BM25 scoring
LAMBDA = 0.45             # Fusion weight: 45% lexical (BM25), 55% dense
PHRASE_BOOST = 0.15       # Boost for exact phrase matches
TITLE_WEIGHT = 2.0        # Double-weight title in lexical index
CE_POOL = 128             # Re-rank window (top-128 for cross-encoder)
CE_BLEND = 0.3            # 30% hybrid, 70% cross-encoder in final blend
CE_MODEL = os.environ.get(
    "RETRIEVAL_RERANK_MODEL",
    "Xenova/ms-marco-MiniLM-L-6-v2"
)

# ---- Stop words (minimal set for trading domain; excludes domain terms) ----
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set(
    "the a an of to and or for in on with how do i my is are you your what "
    "when at be it as that this we our be by from into as about all out up down "
    "have has had do does did will would could should can get got make use see go "
    "come take know think say tell ask want give need own show put call".split()
)


def _toks(s: str) -> list[str]:
    """Tokenize and filter: lowercase, stop words, length > 2."""
    return [t for t in _WORD.findall((s or "").lower()) if t not in _STOP and len(t) > 2]


def _minmax(a: np.ndarray) -> np.ndarray:
    """Min-max normalization to [0, 1]."""
    lo, hi = float(a.min()), float(a.max())
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


def _bm25(qtoks: list[str], doc_idx: int, index_data: dict, k1: float = 1.5, b: float = 0.75) -> float:
    """BM25 scoring for a single document.

    Args:
        qtoks: Query tokens (already filtered)
        doc_idx: Document index in corpus
        index_data: Cached BM25 index {"df": {...}, "n": N, "avgdl": avg, "tf": [...]}
        k1, b: BM25 parameters (proven values)

    Returns:
        BM25 score (0.0+ scale, normalized later)
    """
    d = index_data["tf"][doc_idx]
    dl = sum(d.values()) or 1
    score = 0.0
    for tok in qtoks:
        if tok in d:
            df = index_data["df"].get(tok, 0)
            numerator = d[tok] * (k1 + 1)
            denominator = d[tok] + k1 * (1 - b + b * dl / index_data["avgdl"])
            idf = math.log(1 + (index_data["n"] - df + 0.5) / (df + 0.5))
            score += idf * (numerator / denominator)
    return score


class HybridRetriever:
    """Production hybrid retriever: dense + BM25 fusion + optional cross-encoder.

    Never calls LLM during search (encoder is pre-computed, CE is optional & lazy).
    Designed for <100ms latency target on 10-50k corpus.
    """

    def __init__(
        self,
        encoder: Callable,
        *,
        lambda_weight: float = LAMBDA,
        dense_pool: int = DENSE_POOL,
        phrase_boost: float = PHRASE_BOOST,
        title_weight: float = TITLE_WEIGHT,
    ):
        """Initialize the retriever.

        Args:
            encoder: Callable that embeds queries/docs. Must have:
                encoder.query_embed(list[str]) -> list[np.ndarray]
            lambda_weight: Fusion weight for BM25 (1 - lambda is dense weight)
            dense_pool: Top-N dense hits to include in BM25 scoring
            phrase_boost: Boost for exact phrase matches (0 to disable)
            title_weight: Weight multiplier for title tokens in BM25 index
        """
        self.encoder = encoder
        self.lambda_weight = lambda_weight
        self.dense_pool = dense_pool
        self.phrase_boost = phrase_boost
        self.title_weight = title_weight

        # State
        self._corpus: list[dict] = []
        self._ids: list[str] = []
        self._vectors: Optional[np.ndarray] = None
        self._index_data: Optional[dict] = None
        self._index_key: Optional[tuple] = None

        # Lazy cross-encoder
        self._cross_encoder = None
        self._ce_model = os.environ.get("RETRIEVAL_RERANK_MODEL", CE_MODEL)

    def index(self, corpus: list[dict], ids: Optional[list[str]] = None) -> None:
        """Build BM25 index from corpus. Call once before search.

        Args:
            corpus: List of records, each with optional keys: title, body, tags, metadata
            ids: Optional explicit IDs; default to numeric indices

        Expected record format:
            {"title": str, "body": str, "tags": [str], "metadata": {...}}
        """
        self._corpus = corpus
        self._ids = ids or [str(i) for i in range(len(corpus))]

        if len(self._ids) != len(corpus):
            raise ValueError(f"corpus ({len(corpus)}) and ids ({len(self._ids)}) length mismatch")

        # Handle empty corpus
        if len(corpus) == 0:
            self._vectors = np.array([], dtype=np.float32).reshape(0, getattr(self, '_vector_dim', 768))
            self._index_data = {
                "df": {},
                "n": 0,
                "avgdl": 0,
                "tf": [],
                "lowtext": [],
            }
            self._index_key = tuple(self._ids)
            logger.info("Indexed empty corpus")
            return

        # Embed corpus (may be cached by encoder)
        logger.info(f"Indexing {len(corpus)} documents")
        texts = [
            f"{c.get('title', '')} {c.get('title', '')} {c.get('body', '')} "
            + " ".join(c.get('tags', []) or [])
            for c in corpus
        ]
        embeddings = list(self.encoder.query_embed(texts))
        self._vectors = np.array(embeddings, dtype=np.float32)

        # Normalize vectors (cosine similarity)
        norms = np.linalg.norm(self._vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._vectors /= norms

        # Build BM25 index
        self._build_bm25_index(corpus)

    def _build_bm25_index(self, corpus: list[dict]) -> None:
        """Construct BM25 index: document frequencies, token counts, avg doc length."""
        # Extract and tokenize documents
        docs = []
        for c in corpus:
            title_toks = _toks(c.get('title', ''))
            body_toks = _toks(c.get('body', ''))
            tags_toks = _toks(' '.join(c.get('tags', []) or []))
            # Title appears twice, boosted
            all_toks = title_toks * int(self.title_weight) + body_toks + tags_toks
            docs.append(all_toks)

        # Calculate IDF (document frequency)
        df = {}
        for doc in docs:
            for tok in set(doc):
                df[tok] = df.get(tok, 0) + 1

        n = len(docs)
        avgdl = sum(len(d) for d in docs) / max(n, 1)

        # Term frequency per doc
        from collections import Counter
        tf = [Counter(d) for d in docs]

        # Lowercased full text for phrase matching
        lowtext = [
            f"{c.get('title', '')} {c.get('body', '')}".lower()
            for c in corpus
        ]

        self._index_data = {
            "df": df,
            "n": n,
            "avgdl": avgdl,
            "tf": tf,
            "lowtext": lowtext,
        }
        self._index_key = tuple(self._ids)

    def search(
        self,
        query: str,
        k: int = 10,
        rerank: bool = False,
    ) -> list[tuple[float, dict]]:
        """Hybrid search: dense + BM25 fusion (+optional cross-encoder rerank).

        Never calls LLM in search path. Returns top-k results in descending score order.

        Args:
            query: Search query string
            k: Number of results to return
            rerank: If True, apply cross-encoder re-ranking (requires model cache)

        Returns:
            list[(score, record)] sorted by score descending. Len <= k.

        Raises:
            ValueError: If index not yet built
        """
        if self._vectors is None or self._index_data is None:
            raise ValueError("Call .index(corpus) before .search()")

        if not query.strip() or len(self._corpus) == 0:
            return []

        try:
            return self._search_inner(query, k, rerank=rerank)
        except Exception as e:
            logger.error(f"Hybrid search failed, falling back to dense: {e}", exc_info=True)
            return self._search_dense_fallback(query, k)

    def _search_inner(
        self,
        query: str,
        k: int,
        rerank: bool = False,
    ) -> list[tuple[float, dict]]:
        """Core hybrid retrieval logic."""
        # Dense retrieval
        q_emb = np.asarray(
            list(self.encoder.query_embed([query]))[0],
            dtype=np.float32
        )
        q_emb /= np.linalg.norm(q_emb) + 1e-9
        dense_scores = self._vectors @ q_emb  # Cosine similarity, [-1, 1]

        # Top-N dense pooling
        pool_indices = [int(i) for i in np.argsort(-dense_scores)[: self.dense_pool]]

        # BM25 on pooled set
        qtoks = _toks(query)
        lex_scores = {
            i: _bm25(qtoks, i, self._index_data)
            for i in pool_indices
        }

        # Normalization
        dense_vals = np.array([dense_scores[i] for i in pool_indices], dtype=np.float64)
        lex_vals = np.array([lex_scores[i] for i in pool_indices], dtype=np.float64)
        dense_norm = _minmax(dense_vals)
        lex_norm = _minmax(lex_vals)

        # Fusion: LAMBDA = 45% lexical, 55% dense
        fused = (1 - self.lambda_weight) * dense_norm + self.lambda_weight * lex_norm

        # Phrase boost (exact match in title/body)
        if self.phrase_boost and len(query.strip()) > 8 and len(query.split()) <= 6:
            ql = query.strip().lower()
            for j, i in enumerate(pool_indices):
                if ql in self._index_data["lowtext"][i]:
                    fused[j] += self.phrase_boost

        # Sort by fused score
        order = list(np.argsort(-fused))

        # Optional cross-encoder reranking
        if rerank:
            order = self._rerank_with_ce(query, pool_indices, order, fused, k)

        # Build output
        out = []
        for j in order:
            rec_idx = pool_indices[j]
            out.append((float(fused[j]), self._corpus[rec_idx]))
            if len(out) >= k:
                break

        return out

    def _rerank_with_ce(
        self,
        query: str,
        pool_indices: list[int],
        order: list[int],
        fused: np.ndarray,
        k: int,
    ) -> list[int]:
        """Apply cross-encoder re-ranking to top-CE_POOL results."""
        try:
            ce = self._load_cross_encoder()
            top_local = order[: CE_POOL]
            top_global = [pool_indices[j] for j in top_local]

            # Prepare ranking texts
            docs = []
            for idx in top_global:
                rec = self._corpus[idx]
                title = rec.get("title", "")
                body = rec.get("body", "")[:300]  # Truncate body for speed
                docs.append(" :: ".join(p for p in (title, body) if p))

            # Cross-encoder scores
            ce_scores = np.asarray(list(ce.rerank(query, docs)), dtype=np.float64)

            # Normalize and blend
            fused_top = np.array([fused[j] for j in top_local], dtype=np.float64)
            fused_norm = _minmax(fused_top)
            ce_norm = _minmax(ce_scores)
            final = CE_BLEND * fused_norm + (1 - CE_BLEND) * ce_norm

            # New order for top-CE_POOL, append rest unchanged
            top_reordered = [top_local[t] for t in np.argsort(-final)]
            return top_reordered + [j for j in order if j not in set(top_local)]
        except Exception as e:
            logger.warning(f"Cross-encoder unavailable, using hybrid order: {e}")
            return order

    def _load_cross_encoder(self):
        """Lazy-load cross-encoder (singleton, cached)."""
        if self._cross_encoder is not None:
            return self._cross_encoder

        try:
            # Try fastembed (minimal, fast)
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            cache_path = os.environ.get(
                "FASTEMBED_CACHE_PATH",
                "/tmp/fastembed_cache"
            )
            self._cross_encoder = TextCrossEncoder(
                self._ce_model,
                cache_dir=cache_path,
                threads=int(os.environ.get("RERANK_THREADS", "4")),
            )
        except ImportError:
            raise ImportError(
                "fastembed not available; install with: pip install fastembed"
            )

        return self._cross_encoder

    def _search_dense_fallback(self, query: str, k: int) -> list[tuple[float, dict]]:
        """Fallback: plain dense retrieval only (no BM25, no LLM)."""
        logger.info("Using dense-only fallback")
        q_emb = np.asarray(
            list(self.encoder.query_embed([query]))[0],
            dtype=np.float32
        )
        q_emb /= np.linalg.norm(q_emb) + 1e-9
        scores = self._vectors @ q_emb
        top_indices = np.argsort(-scores)[: k]

        return [
            (float(scores[i]), self._corpus[i])
            for i in top_indices
        ]

    def get_stats(self) -> dict[str, Any]:
        """Return indexing stats for diagnostics."""
        return {
            "corpus_size": len(self._corpus),
            "vector_dim": self._vectors.shape[1] if self._vectors is not None else None,
            "lambda_weight": self.lambda_weight,
            "dense_pool": self.dense_pool,
            "index_built": self._index_data is not None,
            "cross_encoder_loaded": self._cross_encoder is not None,
        }
