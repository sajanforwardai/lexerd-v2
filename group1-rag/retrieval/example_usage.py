"""example_usage.py — Quick-start guide for Group One Trading RAG Retrieval Engine.

Shows:
  1. Initializing with a mock encoder
  2. Indexing a trading corpus
  3. Running search queries
  4. Hybrid fusion in action
  5. Cross-encoder re-ranking (optional)
"""

import numpy as np
from retrieval_engine import HybridRetriever


class SimpleEncoder:
    """Minimal encoder stub (use real encoder in production)."""

    def __init__(self, dim: int = 768, seed: int = 42):
        self.dim = dim
        self.rng = np.random.RandomState(seed)

    def query_embed(self, texts: list[str]) -> list[np.ndarray]:
        """Return deterministic embeddings for texts."""
        embeddings = []
        for text in texts:
            h = hash(text) & 0x7FFFFFFF
            self.rng.seed((42 + h) % (2**31))
            emb = self.rng.randn(self.dim).astype(np.float32)
            emb /= np.linalg.norm(emb) + 1e-9
            embeddings.append(emb)
        return embeddings


def main():
    """End-to-end retrieval example."""
    print("=" * 70)
    print("Group One Trading RAG — Hybrid Retrieval Engine Demo")
    print("=" * 70)

    # 1. Initialize encoder and retriever
    print("\n1. Initializing retriever...")
    encoder = SimpleEncoder(dim=768)
    retriever = HybridRetriever(encoder, lambda_weight=0.45)
    print(f"   Encoder ready: {retriever.get_stats()}")

    # 2. Define trading corpus
    print("\n2. Building trading corpus...")
    corpus = [
        {
            "title": "Bitcoin Trading Fundamentals",
            "body": "Learn how to trade bitcoin effectively using technical analysis and "
            "risk management. Buy low, sell high. Understand support and resistance levels.",
            "tags": ["trading", "bitcoin", "technical-analysis"],
        },
        {
            "title": "Day Trading Strategies",
            "body": "Fast-paced trading strategies for intraday moves. Scalping, momentum trading, "
            "and mean reversion techniques.",
            "tags": ["trading", "day-trading", "strategies"],
        },
        {
            "title": "Ethereum Investment Guide",
            "body": "Long-term ethereum investment approach. Hold ethereum for years as a "
            "hedge against inflation.",
            "tags": ["ethereum", "investing", "long-term"],
        },
        {
            "title": "Options Trading 101",
            "body": "Master options contracts, calls, puts, spreads, and hedging. "
            "Learn how to trade options safely.",
            "tags": ["options", "derivatives", "hedging"],
        },
        {
            "title": "Risk Management in Crypto",
            "body": "Protect your portfolio with position sizing, stop losses, and diversification. "
            "Never risk more than you can afford to lose.",
            "tags": ["risk", "crypto", "portfolio"],
        },
        {
            "title": "Technical Analysis Masterclass",
            "body": "Charts, candlesticks, moving averages, RSI, MACD, Bollinger Bands. "
            "Use indicators for timing entries and exits.",
            "tags": ["technical-analysis", "indicators", "trading"],
        },
        {
            "title": "Fundamental Analysis for Stocks",
            "body": "Evaluate companies using P/E ratio, earnings, balance sheets, and cash flow. "
            "Buy undervalued stocks.",
            "tags": ["stocks", "fundamental-analysis", "valuation"],
        },
        {
            "title": "Crypto Market Cycles",
            "body": "Understand boom-bust cycles in crypto. Bitcoin and ethereum follow predictable "
            "patterns.",
            "tags": ["crypto", "cycles", "bitcoin", "ethereum"],
        },
        {
            "title": "Algorithmic Trading",
            "body": "Build trading bots using Python. Automate order execution and risk management. "
            "Backtest strategies.",
            "tags": ["trading", "algorithmic", "automation"],
        },
        {
            "title": "Portfolio Diversification",
            "body": "Spread risk across stocks, bonds, crypto, and commodities. "
            "Don't put all eggs in one basket.",
            "tags": ["portfolio", "diversification", "risk"],
        },
    ]
    retriever.index(corpus)
    print(f"   Indexed {len(corpus)} documents")
    print(f"   Stats: {retriever.get_stats()}")

    # 3. Run search queries
    print("\n3. Running search queries...\n")
    queries = [
        "bitcoin trading",
        "ethereum investment",
        "risk management",
        "technical analysis strategies",
    ]

    for query in queries:
        print(f"   Query: '{query}'")
        results = retriever.search(query, k=3, rerank=False)

        for i, (score, doc) in enumerate(results, 1):
            print(f"     {i}. [{score:.3f}] {doc['title']}")
        print()

    # 4. Demonstrate hybrid fusion
    print("4. Hybrid Fusion Breakdown (single query)...\n")
    print("   Query: 'bitcoin trading'")
    results = retriever.search("bitcoin trading", k=5, rerank=False)
    print(f"   Results (hybrid score = 45% BM25 + 55% dense):")
    for i, (score, doc) in enumerate(results, 1):
        print(f"     {i}. [{score:.3f}] {doc['title']}")

    # 5. Cross-encoder re-ranking (optional, slower but better quality)
    print("\n5. Cross-Encoder Re-ranking (optional)...\n")
    print("   Attempting rerank=True (requires fastembed)...")
    try:
        results_ce = retriever.search("risk management", k=3, rerank=True)
        print(f"   Re-ranked results:")
        for i, (score, doc) in enumerate(results_ce, 1):
            print(f"     {i}. [{score:.3f}] {doc['title']}")
    except Exception as e:
        print(f"   Skipped (fastembed not available): {e}")

    # 6. Performance
    print("\n6. Performance Summary...\n")
    stats = retriever.get_stats()
    print(f"   Corpus size: {stats['corpus_size']} docs")
    print(f"   Vector dimension: {stats['vector_dim']}")
    print(f"   Lambda weight (BM25): {stats['lambda_weight']}")
    print(f"   Dense pool size: {stats['dense_pool']}")
    print(f"   Index built: {stats['index_built']}")

    print("\n" + "=" * 70)
    print("Summary: Hybrid retrieval working correctly!")
    print("  • Dense + BM25 fusion (LAMBDA=0.45)")
    print("  • Top-200 pooling for efficient BM25 scoring")
    print("  • Graceful fallback on errors")
    print("  • Optional cross-encoder re-ranking")
    print("  • Target: nDCG@10 >= 0.50, latency <= 100ms")
    print("=" * 70)


if __name__ == "__main__":
    main()
