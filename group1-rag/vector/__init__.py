"""
Qdrant Vector Database Client for Group One RAG

Production-grade vector database client for retrieval-augmented generation
on financial trading data.

Main Classes:
    - QdrantVectorStore: Main vector database client
    - DocumentChunker: Hierarchical document chunking
    - EmbeddingModel: Embedding model wrapper with fallback support
    - DocumentMetadata: Metadata structure for indexed documents
"""

from vector_client import (
    QdrantVectorStore,
    DocumentChunker,
    EmbeddingModel,
    DocumentMetadata,
)

__version__ = "1.0.0"
__author__ = "Group One Finance"
__all__ = [
    "QdrantVectorStore",
    "DocumentChunker",
    "EmbeddingModel",
    "DocumentMetadata",
]
