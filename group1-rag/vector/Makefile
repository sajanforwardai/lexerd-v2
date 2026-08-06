.PHONY: install test test-verbose test-coverage run-example clean lint format help

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	python -m pytest test_vector.py -v --tb=short

# Run tests with verbose output
test-verbose:
	python -m pytest test_vector.py -vv --tb=long --capture=no

# Run tests with coverage report
test-coverage:
	python -m pytest test_vector.py --cov=vector_client --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

# Run specific test class
test-chunker:
	python -m pytest test_vector.py::TestDocumentChunker -v

test-embedding:
	python -m pytest test_vector.py::TestEmbeddingModel -v

test-store:
	python -m pytest test_vector.py::TestQdrantVectorStore -v

test-latency:
	python -m pytest test_vector.py::TestQueryLatencyBenchmark -v

# Run example usage script
run-example:
	@echo "Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
	python example_usage.py

# Lint code
lint:
	python -m pylint vector_client.py test_vector.py --disable=line-too-long,missing-docstring || true

# Format code
format:
	python -m black vector_client.py test_vector.py example_usage.py

# Check syntax
check:
	python -m py_compile vector_client.py test_vector.py example_usage.py
	@echo "✓ All files have valid Python syntax"

# Clean up
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov *.pyc
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Help
help:
	@echo "Group One RAG Vector Client - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make install           - Install dependencies"
	@echo "  make test              - Run all tests"
	@echo "  make test-verbose      - Run tests with verbose output"
	@echo "  make test-coverage     - Generate coverage report"
	@echo "  make test-chunker      - Test document chunking"
	@echo "  make test-embedding    - Test embedding models"
	@echo "  make test-store        - Test vector store"
	@echo "  make test-latency      - Test query latency"
	@echo "  make run-example       - Run example usage script"
	@echo "  make lint              - Lint code"
	@echo "  make format            - Format code with black"
	@echo "  make check             - Check Python syntax"
	@echo "  make clean             - Remove generated files"
	@echo "  make help              - Show this help message"
