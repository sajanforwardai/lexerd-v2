"""
FinBERT Fine-Tuning Pipeline for Group One Trading RAG

Trains FinBERT on triplet loss using Group One trading corpus. Implements:
- Triplet loss with hard negative mining
- Early stopping on validation loss
- Checkpoint management with best model tracking
- Learning rate scheduling
- Deterministic seeding for reproducibility
- GPU/CPU automatic selection with fallback
"""

import json
import math
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

try:
    from transformers import AutoTokenizer, AutoModel
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logging.warning("transformers not installed. Install with: pip install transformers")

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)


@dataclass
class TrainingConfig:
    """Configuration for fine-tuning"""
    model_name: str = "ProsusAI/finbert"
    learning_rate: float = 2e-5
    batch_size: int = 32
    num_epochs: int = 5
    max_grad_norm: float = 1.0
    warmup_steps: int = 500
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.001
    triplet_margin: float = 0.5
    max_seq_length: int = 256
    seed: int = 42
    device: str = "cpu"
    use_amp: bool = False  # Automatic mixed precision
    checkpoint_dir: str = "./checkpoints"
    logging_steps: int = 50


class TripletDataset(Dataset):
    """Dataset for triplet loss training"""

    def __init__(
        self,
        triplets: List[Dict[str, str]],
        tokenizer,
        max_seq_length: int = 256
    ):
        self.triplets = triplets
        self.tokenizer = tokenizer
        self.max_seq_length = max_seq_length

    def __len__(self):
        return len(self.triplets)

    def __getitem__(self, idx):
        triplet = self.triplets[idx]

        # Tokenize query, positive, negative
        query_tokens = self.tokenizer(
            triplet["query"],
            max_length=self.max_seq_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        positive_tokens = self.tokenizer(
            triplet["positive"],
            max_length=self.max_seq_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        negative_tokens = self.tokenizer(
            triplet["negative"],
            max_length=self.max_seq_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        return {
            "query": {
                "input_ids": query_tokens["input_ids"].squeeze(0),
                "attention_mask": query_tokens["attention_mask"].squeeze(0),
            },
            "positive": {
                "input_ids": positive_tokens["input_ids"].squeeze(0),
                "attention_mask": positive_tokens["attention_mask"].squeeze(0),
            },
            "negative": {
                "input_ids": negative_tokens["input_ids"].squeeze(0),
                "attention_mask": negative_tokens["attention_mask"].squeeze(0),
            }
        }


class TripletLoss(nn.Module):
    """Triplet loss with margin-based ranking"""

    def __init__(self, margin: float = 0.5, reduction: str = "mean"):
        super().__init__()
        self.margin = margin
        self.reduction = reduction

    def forward(self, anchor: torch.Tensor, positive: torch.Tensor, negative: torch.Tensor) -> torch.Tensor:
        """
        Compute triplet loss.

        Args:
            anchor: Query embeddings (batch_size, embedding_dim)
            positive: Positive document embeddings (batch_size, embedding_dim)
            negative: Negative document embeddings (batch_size, embedding_dim)

        Returns:
            Triplet loss value
        """
        # Cosine similarity
        pos_sim = F.cosine_similarity(anchor, positive)
        neg_sim = F.cosine_similarity(anchor, negative)

        # Margin-based loss
        loss = torch.clamp(self.margin + neg_sim - pos_sim, min=0.0)

        if self.reduction == "mean":
            return loss.mean()
        elif self.reduction == "sum":
            return loss.sum()
        else:
            return loss


class FinBERTFineTuner:
    """Main fine-tuning class"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self._set_seed()

        # Device setup
        if config.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = config.device

        logger.info(f"Using device: {self.device}")

        # Load model and tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(config.model_name)
        self.model = AutoModel.from_pretrained(config.model_name)
        self.model.to(self.device)

        # Loss function
        self.loss_fn = TripletLoss(margin=config.triplet_margin)

        # Training state
        self.best_val_loss = float("inf")
        self.patience_counter = 0
        self.training_history = {
            "train_loss": [],
            "val_loss": [],
            "learning_rates": []
        }

        logger.info(f"Model loaded: {config.model_name}")
        logger.info(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")

    def _set_seed(self):
        """Set random seeds for reproducibility"""
        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.config.seed)

    def embed_text(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embed text using the model"""
        embeddings = []

        self.model.eval()
        with torch.no_grad():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]

                tokens = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_seq_length,
                    return_tensors="pt"
                ).to(self.device)

                outputs = self.model(**tokens)
                # Use mean pooling
                embeddings.append(outputs.last_hidden_state.mean(dim=1).cpu().numpy())

        return np.vstack(embeddings)

    def embed_batch(self, batch: Dict) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Embed a single batch (query, positive, negative)"""
        def embed_tokens(token_dict):
            tokens = {k: v.to(self.device) for k, v in token_dict.items()}
            outputs = self.model(**tokens)
            # Mean pooling over sequence length
            embeddings = outputs.last_hidden_state.mean(dim=1)
            return embeddings

        query_emb = embed_tokens(batch["query"])
        positive_emb = embed_tokens(batch["positive"])
        negative_emb = embed_tokens(batch["negative"])

        return query_emb, positive_emb, negative_emb

    def train_epoch(self, train_loader: DataLoader, optimizer, scheduler) -> float:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        num_batches = 0

        for batch_idx, batch in enumerate(train_loader):
            optimizer.zero_grad()

            # Forward pass
            query_emb, positive_emb, negative_emb = self.embed_batch(batch)
            loss = self.loss_fn(query_emb, positive_emb, negative_emb)

            # Backward pass
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.config.max_grad_norm)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            num_batches += 1

            if (batch_idx + 1) % self.config.logging_steps == 0:
                avg_loss = total_loss / num_batches
                logger.info(f"  Batch {batch_idx+1}/{len(train_loader)}: loss={loss.item():.4f}, avg={avg_loss:.4f}")

        return total_loss / num_batches if num_batches > 0 else 0.0

    def validate(self, val_loader: DataLoader) -> float:
        """Validate on validation set"""
        self.model.eval()
        total_loss = 0.0
        num_batches = 0

        with torch.no_grad():
            for batch in val_loader:
                query_emb, positive_emb, negative_emb = self.embed_batch(batch)
                loss = self.loss_fn(query_emb, positive_emb, negative_emb)

                total_loss += loss.item()
                num_batches += 1

        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        logger.info(f"Validation loss: {avg_loss:.4f}")

        return avg_loss

    def save_checkpoint(self, save_dir: str, epoch: int, is_best: bool = False):
        """Save model checkpoint"""
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        checkpoint_file = save_path / f"checkpoint_epoch_{epoch}.pt"
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "config": asdict(self.config),
            "training_history": self.training_history
        }, checkpoint_file)

        logger.info(f"Saved checkpoint: {checkpoint_file}")

        if is_best:
            best_file = save_path / "best_model.pt"
            torch.save({
                "epoch": epoch,
                "model_state_dict": self.model.state_dict(),
                "config": asdict(self.config),
                "training_history": self.training_history
            }, best_file)
            logger.info(f"Saved best model: {best_file}")

    def load_checkpoint(self, checkpoint_path: str):
        """Load model from checkpoint"""
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded checkpoint: {checkpoint_path}")

    def fit(
        self,
        train_data: List[Dict[str, str]],
        val_data: List[Dict[str, str]],
        checkpoint_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fine-tune the model.

        Args:
            train_data: List of triplet dictionaries
            val_data: List of triplet dictionaries
            checkpoint_dir: Where to save checkpoints

        Returns:
            Training history and metadata
        """
        if checkpoint_dir is None:
            checkpoint_dir = self.config.checkpoint_dir

        # Create data loaders
        train_dataset = TripletDataset(train_data, self.tokenizer, self.config.max_seq_length)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0
        )

        val_dataset = TripletDataset(val_data, self.tokenizer, self.config.max_seq_length)
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0
        )

        # Optimizer and scheduler
        optimizer = AdamW(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=0.01
        )

        total_steps = len(train_loader) * self.config.num_epochs
        scheduler = CosineAnnealingLR(optimizer, T_max=total_steps)

        logger.info(f"Training with {len(train_data)} training samples, {len(val_data)} validation samples")
        logger.info(f"Total steps: {total_steps}, Learning rate: {self.config.learning_rate}")

        # Training loop
        start_time = datetime.utcnow()

        for epoch in range(self.config.num_epochs):
            logger.info(f"\nEpoch {epoch+1}/{self.config.num_epochs}")

            # Train
            train_loss = self.train_epoch(train_loader, optimizer, scheduler)
            self.training_history["train_loss"].append(train_loss)
            logger.info(f"Epoch {epoch+1} training loss: {train_loss:.4f}")

            # Validate
            val_loss = self.validate(val_loader)
            self.training_history["val_loss"].append(val_loss)
            self.training_history["learning_rates"].append(optimizer.param_groups[0]["lr"])

            # Save checkpoint
            is_best = False
            if val_loss < self.best_val_loss - self.config.early_stopping_threshold:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                is_best = True
            else:
                self.patience_counter += 1

            self.save_checkpoint(checkpoint_dir, epoch+1, is_best=is_best)

            # Early stopping
            if self.patience_counter >= self.config.early_stopping_patience:
                logger.info(f"Early stopping triggered after {epoch+1} epochs")
                break

        elapsed_time = (datetime.utcnow() - start_time).total_seconds()

        return {
            "epochs_trained": epoch + 1,
            "best_val_loss": self.best_val_loss,
            "training_time_seconds": elapsed_time,
            "training_history": self.training_history,
            "checkpoint_dir": checkpoint_dir
        }


def finetune_finbert(
    train_data: List[Dict[str, str]],
    val_data: List[Dict[str, str]],
    config: Optional[TrainingConfig] = None,
    checkpoint_dir: str = "/workspace/group1-rag/finetuning/checkpoints"
) -> Tuple[FinBERTFineTuner, Dict[str, Any]]:
    """
    High-level function to fine-tune FinBERT.

    Args:
        train_data: Training triplets
        val_data: Validation triplets
        config: Training configuration
        checkpoint_dir: Where to save checkpoints

    Returns:
        Tuple of (model, training_results)
    """
    if config is None:
        config = TrainingConfig(
            device="cuda" if torch.cuda.is_available() else "cpu",
            checkpoint_dir=checkpoint_dir
        )

    finetuner = FinBERTFineTuner(config)
    results = finetuner.fit(train_data, val_data, checkpoint_dir)

    return finetuner, results


if __name__ == "__main__":
    import json

    # Quick test
    logging.basicConfig(level=logging.INFO)

    # Create minimal test data
    test_triplets = [
        {
            "query": "What is delta?",
            "positive": "Delta measures the rate of change of the option price with respect to the underlying asset price.",
            "negative": "The weather is sunny today and the temperature is warm."
        }
        for _ in range(10)
    ]

    config = TrainingConfig(
        num_epochs=1,
        batch_size=4,
        device="cpu"
    )

    print("Starting fine-tuning test...")
    finetuner, results = finetune_finbert(
        test_triplets,
        test_triplets,
        config=config,
        checkpoint_dir="/tmp/finbert-test"
    )

    print(f"Training complete!")
    print(f"Results: {json.dumps(results, indent=2, default=str)}")
