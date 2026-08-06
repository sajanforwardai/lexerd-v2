"""
Example usage of the Qdrant Vector Database Client for Group One RAG

This script demonstrates:
1. Initializing the vector store
2. Ingesting corpus files
3. Querying the vector store
4. Filtering results
5. Monitoring performance
"""

import logging
from pathlib import Path
import time
from vector_client import QdrantVectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_basic_setup():
    """Example 1: Basic setup and health check"""
    logger.info("=" * 80)
    logger.info("Example 1: Basic Setup and Health Check")
    logger.info("=" * 80)

    # Initialize vector store
    vector_store = QdrantVectorStore(
        collection_name="group1-rag",
        host="localhost",
        port=6333,
        embedding_model='finbert',
        fallback_model='bge-large-en-v1.5',
        recreate_collection=False  # Set to True to start fresh
    )

    # Health check
    health = vector_store.health_check()
    logger.info(f"Health Status: {health}")

    return vector_store


def example_ingest_corpus(vector_store: QdrantVectorStore):
    """Example 2: Ingest corpus files"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 2: Ingest Corpus Files")
    logger.info("=" * 80)

    # Define corpus directories
    corpus_dirs = [
        Path("/workspace/corpus/finance"),
        Path("/workspace/corpus/financial-services")
    ]

    for corpus_dir in corpus_dirs:
        if corpus_dir.exists():
            logger.info(f"\nIngesting from: {corpus_dir}")

            start_time = time.time()
            stats = vector_store.ingest_corpus_files(
                corpus_dir=corpus_dir,
                domain=corpus_dir.name.replace('-', '_'),
                batch_size=50
            )

            elapsed = time.time() - start_time
            logger.info(f"✓ Documents ingested: {stats['documents_ingested']}")
            logger.info(f"✓ Chunks created: {stats['chunks_ingested']}")
            logger.info(f"✓ Time elapsed: {elapsed:.2f}s")
            logger.info(f"✓ Throughput: {stats['chunks_ingested']/elapsed:.1f} chunks/sec")
        else:
            logger.warning(f"Corpus directory not found: {corpus_dir}")


def example_simple_query(vector_store: QdrantVectorStore):
    """Example 3: Simple query"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 3: Simple Query")
    logger.info("=" * 80)

    query_text = "What is implied volatility and how does it affect option pricing?"
    logger.info(f"\nQuery: {query_text}\n")

    start_time = time.time()
    results = vector_store.query(
        query_text=query_text,
        top_k=3,
        score_threshold=0.5
    )
    elapsed_ms = (time.time() - start_time) * 1000

    logger.info(f"Results ({elapsed_ms:.2f}ms):\n")
    for i, result in enumerate(results, 1):
        logger.info(f"Result {i}:")
        logger.info(f"  Title: {result['title']}")
        logger.info(f"  Score: {result['score']:.4f}")
        logger.info(f"  Section: {result['section']}")
        logger.info(f"  Content: {result['content'][:150]}...")
        logger.info()


def example_filtered_query(vector_store: QdrantVectorStore):
    """Example 4: Filtered query"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 4: Filtered Query (by Domain)")
    logger.info("=" * 80)

    query_text = "options trading strategies"
    logger.info(f"\nQuery: {query_text}")
    logger.info(f"Filter: domain='finance'\n")

    results = vector_store.query(
        query_text=query_text,
        top_k=5,
        score_threshold=0.6,
        filters={'domain': 'finance'}
    )

    logger.info(f"Found {len(results)} results:\n")
    for i, result in enumerate(results, 1):
        logger.info(f"Result {i}:")
        logger.info(f"  Title: {result['title']}")
        logger.info(f"  Domain: {result['domain']}")
        logger.info(f"  Score: {result['score']:.4f}")
        logger.info(f"  Metadata:")
        logger.info(f"    Phase: {result['metadata']['phase']}")
        logger.info(f"    Difficulty: {result['metadata']['difficulty']}")
        if result['metadata']['tools']:
            logger.info(f"    Tools: {', '.join(result['metadata']['tools'])}")
        logger.info()


def example_multiple_queries(vector_store: QdrantVectorStore):
    """Example 5: Multiple queries and latency tracking"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 5: Query Latency Analysis")
    logger.info("=" * 80)

    queries = [
        "What are the Greeks in options trading?",
        "How does Value at Risk work?",
        "What is a call option?",
        "Risk management for traders",
        "Options pricing models"
    ]

    latencies = []

    logger.info(f"\nRunning {len(queries)} queries...\n")

    for query in queries:
        start = time.time()
        results = vector_store.query(query, top_k=3)
        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)

        logger.info(f"Query: '{query}'")
        logger.info(f"  Results: {len(results)}")
        logger.info(f"  Latency: {latency_ms:.2f}ms")
        logger.info()

    # Statistics
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)

    logger.info("Query Latency Statistics:")
    logger.info(f"  Average: {avg_latency:.2f}ms")
    logger.info(f"  Min: {min_latency:.2f}ms")
    logger.info(f"  Max: {max_latency:.2f}ms")
    logger.info(f"  Target: <100ms ✓" if avg_latency < 100 else f"  Target: <100ms ✗")


def example_statistics(vector_store: QdrantVectorStore):
    """Example 6: View statistics"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 6: Vector Store Statistics")
    logger.info("=" * 80)

    stats = vector_store.get_stats()

    logger.info("\nIngestion Statistics:")
    logger.info(f"  Documents ingested: {stats['documents_ingested']}")
    logger.info(f"  Chunks ingested: {stats['chunks_ingested']}")
    logger.info(f"  Last ingestion: {stats['last_ingestion']}")

    logger.info("\nQuery Statistics:")
    logger.info(f"  Total queries: {stats['queries_executed']}")
    logger.info(f"  Average latency: {stats['avg_query_time_ms']:.2f}ms")


def example_metadata_exploration(vector_store: QdrantVectorStore):
    """Example 7: Explore document metadata"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 7: Document Metadata Exploration")
    logger.info("=" * 80)

    query_text = "derivatives and hedging"

    results = vector_store.query(
        query_text=query_text,
        top_k=5,
        score_threshold=0.6
    )

    logger.info(f"\nQuery: {query_text}\n")

    if results:
        logger.info("Retrieved Documents with Full Metadata:\n")
        for result in results:
            logger.info(f"Document: {result['title']}")
            logger.info(f"  Content Preview: {result['content'][:100]}...")
            logger.info(f"  Similarity Score: {result['score']:.4f}")
            logger.info(f"  Metadata:")
            logger.info(f"    Domain: {result['domain']}")
            logger.info(f"    Section: {result['section']}")
            logger.info(f"    Phase: {result['metadata']['phase']}")
            logger.info(f"    Difficulty: {result['metadata']['difficulty']}")
            logger.info(f"    Chunk: {result['metadata']['chunk_index']}/{result['metadata']['total_chunks']}")

            if result['metadata']['tools']:
                logger.info(f"    Tools: {', '.join(result['metadata']['tools'])}")

            if result['metadata']['entities']:
                logger.info(f"    Entities: {', '.join(result['metadata']['entities'])}")

            logger.info()
    else:
        logger.info("No results found for query")


def example_custom_document_ingestion(vector_store: QdrantVectorStore):
    """Example 8: Ingest a custom document"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 8: Custom Document Ingestion")
    logger.info("=" * 80)

    # Custom document content
    document_content = """
    # Volatility Surface and Smile

    ## Introduction
    The volatility surface represents the relationship between implied volatility,
    strike price, and time to expiration. Understanding this is crucial for options traders.

    ## Volatility Smile
    The volatility smile refers to the pattern where at-the-money options have lower
    implied volatility compared to in-the-money and out-of-the-money options.

    ### Historical Context
    The volatility smile became particularly pronounced after the 1987 market crash,
    fundamentally changing how traders approach option pricing.

    ## Applications
    Traders use the volatility surface to:
    - Identify mispricings in options
    - Construct volatility arbitrage strategies
    - Hedge portfolio risks effectively
    """

    logger.info("\nIngesting custom document: 'Volatility Surface and Smile'\n")

    result = vector_store.ingest_document(
        content=document_content,
        title="Volatility Surface and Smile",
        domain="finance",
        phase="production",
        difficulty="advanced",
        tools=["Python", "NumPy", "Matplotlib", "QuantLib"],
        entities=["implied volatility", "volatility smile", "strike price", "options pricing"]
    )

    logger.info(f"✓ Document ingested with {result['chunks_ingested']} chunks")

    # Query the ingested document
    logger.info("\nQuerying the new document...\n")
    results = vector_store.query(
        query_text="What is volatility smile?",
        top_k=3
    )

    for result in results[:1]:  # Show top result
        logger.info(f"Query Result:")
        logger.info(f"  Title: {result['title']}")
        logger.info(f"  Score: {result['score']:.4f}")
        logger.info(f"  Content: {result['content'][:150]}...")


def example_performance_test(vector_store: QdrantVectorStore):
    """Example 9: Performance testing"""
    logger.info("\n" + "=" * 80)
    logger.info("Example 9: Performance Test")
    logger.info("=" * 80)

    # Test with different top_k values
    logger.info("\nLatency vs Top-K Results:\n")

    for top_k in [1, 5, 10, 20]:
        latencies = []
        for _ in range(5):
            start = time.time()
            vector_store.query("trading strategy", top_k=top_k)
            latencies.append((time.time() - start) * 1000)

        avg_latency = sum(latencies) / len(latencies)
        logger.info(f"  top_k={top_k:2d}: {avg_latency:.2f}ms average")

    # Test batch query
    logger.info("\nBatch Query Performance (10 queries):\n")

    queries = [
        "options trading",
        "risk management",
        "volatility smile",
        "delta hedging",
        "implied volatility",
        "option pricing",
        "strike price",
        "time decay",
        "Greeks in options",
        "portfolio hedging"
    ]

    start = time.time()
    for query in queries:
        vector_store.query(query, top_k=3)
    total_time = time.time() - start

    logger.info(f"  Total time: {total_time:.2f}s")
    logger.info(f"  Average per query: {total_time/len(queries)*1000:.2f}ms")
    logger.info(f"  Throughput: {len(queries)/total_time:.1f} queries/sec")


def main():
    """Run all examples"""
    try:
        # Example 1: Basic setup
        vector_store = example_basic_setup()

        # Example 2: Ingest corpus (if Qdrant is empty)
        health = vector_store.health_check()
        if health.get('document_count', 0) == 0:
            logger.info("\nVector store is empty. Ingesting corpus files...")
            example_ingest_corpus(vector_store)
        else:
            logger.info(f"\nVector store already contains {health['document_count']} documents")

        # Example 3-9: Various queries and analysis
        example_simple_query(vector_store)
        example_filtered_query(vector_store)
        example_multiple_queries(vector_store)
        example_statistics(vector_store)
        example_metadata_exploration(vector_store)
        example_custom_document_ingestion(vector_store)
        example_performance_test(vector_store)

        logger.info("\n" + "=" * 80)
        logger.info("All examples completed successfully!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
