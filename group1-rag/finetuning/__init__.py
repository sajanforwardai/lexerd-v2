"""
FinBERT Fine-Tuning Pipeline for Group One Trading RAG

This package provides end-to-end fine-tuning of FinBERT on Group One trading corpus
to improve retrieval accuracy by 10-30%.

Key Components:
- dataset_builder: Create training triplets from golden queries
- finbert_finetuning: Train FinBERT with triplet loss
- validator: Measure nDCG@10 improvement vs baseline
- inference_wrapper: Production-ready model loading with fallback

Quick Start:
    from dataset_builder import build_quickstart_dataset
    from finbert_finetuning import finetune_finbert
    from inference_wrapper import create_inference_wrapper

    # Build dataset
    file_paths = build_quickstart_dataset()

    # Train model
    finetuner, results = finetune_finbert(train_data, val_data)

    # Use in production
    wrapper = create_inference_wrapper(checkpoint_dir="./checkpoints")
    embeddings = wrapper.embed(queries)
"""

__version__ = "1.0.0"
__author__ = "Group One Trading RAG Team"

from dataset_builder import (
    DatasetBuilder,
    SyntheticCorpusGenerator,
    TripletSample,
    build_quickstart_dataset
)

from finbert_finetuning import (
    TrainingConfig,
    FinBERTFineTuner,
    TripletLoss,
    finetune_finbert
)

from validator import (
    Validator,
    RetrievalMetrics,
    QueryDocumentMatcher
)

from inference_wrapper import (
    FinBERTInferenceWrapper,
    FinetuningAwareEmbeddingModel,
    create_inference_wrapper
)

__all__ = [
    # Dataset
    "DatasetBuilder",
    "SyntheticCorpusGenerator",
    "TripletSample",
    "build_quickstart_dataset",
    # Training
    "TrainingConfig",
    "FinBERTFineTuner",
    "TripletLoss",
    "finetune_finbert",
    # Validation
    "Validator",
    "RetrievalMetrics",
    "QueryDocumentMatcher",
    # Inference
    "FinBERTInferenceWrapper",
    "FinetuningAwareEmbeddingModel",
    "create_inference_wrapper",
]
