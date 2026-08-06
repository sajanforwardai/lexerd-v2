"""
Dataset Builder for FinBERT Fine-Tuning Pipeline

Creates training triplets (query, positive_doc, negative_doc) from Group One corpus
and golden query set. Generates synthetic trading documents for triplet loss training.

Features:
- Load golden queries from test data
- Create synthetic corpus from trading domains
- Generate triplet pairs (query, relevant_doc, irrelevant_doc)
- Split into train/val/test with reproducible seeding
- Export to formats compatible with triplet loss training
"""

import json
import random
import hashlib
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np


@dataclass
class TripletSample:
    """Single triplet training sample (query, positive, negative)"""
    query: str
    positive: str
    negative: str
    query_id: int
    domain: str
    difficulty: str


@dataclass
class DatasetSplit:
    """Dataset split with triplets and metadata"""
    name: str  # train, val, test
    triplets: List[TripletSample]
    metadata: Dict[str, Any]


class SyntheticCorpusGenerator:
    """Generates synthetic trading documents for negative samples"""

    # Trading domain templates
    DOMAINS = {
        "greeks_options": {
            "templates": [
                "Understanding {greek}: {greek} measures the {metric} of your {position}. "
                "Calculate {greek} using {method}. Apply {greek} to {strategy}.",
                "{greek} Greeks in Options: {greek} is a key {greek} greek that affects {position}. "
                "When {condition}, {greek} {action}. Risk management for {greek}.",
                "Advanced {greek} Trading: Master {greek} calculation. Hedge {greek} exposure. "
                "Portfolio {greek} management. Strategies for {greek}.",
            ],
            "greeks": ["delta", "gamma", "vega", "theta", "rho"],
            "metrics": ["rate of change", "acceleration", "volatility sensitivity", "time decay", "interest rate sensitivity"],
            "strategies": ["hedging", "speculation", "arbitrage", "calendar spreads", "ratio spreads"],
            "methods": ["black-scholes", "binomial tree", "monte carlo", "finite differences", "analytical formula"]
        },
        "hedging_strategies": {
            "templates": [
                "Hedging {risk}: Protect against {risk} using {instrument}. "
                "{strategy} hedge {exposure}. Monitor {metric}.",
                "{strategy} Strategies: Learn {strategy} for {purpose}. Execute {strategy} using {method}. "
                "Manage {strategy} risk.",
                "Protective Strategies: Use {instrument} to hedge {risk}. Calculate {metric}. "
                "Adjust {strategy} for {condition}.",
            ],
            "strategies": ["put protection", "collar", "straddle", "strangle", "spread", "ratio hedge"],
            "risks": ["downside risk", "volatility", "directional move", "tail risk", "correlation risk"],
            "instruments": ["puts", "calls", "futures", "swaps", "options"],
            "methods": ["static hedge", "dynamic hedge", "rebalancing", "cross-asset hedge", "tail hedge"]
        },
        "risk_management": {
            "templates": [
                "Risk Measurement: Calculate {metric} for your portfolio. {metric} shows {interpretation}. "
                "Implement {metric} limits.",
                "{metric} Management: Monitor {metric} daily. Use {technique} to control {metric}. "
                "Stress test {metric}.",
                "Portfolio Risk: Diversify to reduce {metric}. Measure {metric} accurately. "
                "{strategy} risk management.",
            ],
            "metrics": ["VaR", "CVaR", "stress loss", "concentration risk", "liquidity risk"],
            "techniques": ["scenario analysis", "historical simulation", "monte carlo", "parametric", "correlation models"],
            "strategies": ["position limits", "concentration limits", "loss limits", "stop-loss", "rebalancing"]
        },
        "products": {
            "templates": [
                "{product} Basics: {product} are {definition}. Price {product} using {method}. "
                "Trade {product} in {market}.",
                "Advanced {product}: {product} convexity and duration. {product} carry strategies. "
                "{product} arbitrage.",
                "{product} Analysis: Evaluate {product} fundamentals. Compare {product} across {dimension}. "
                "{product} valuation.",
            ],
            "products": ["bonds", "futures", "swaps", "options", "structured notes", "ETFs", "index products"],
            "definitions": ["fixed income instruments", "derivatives", "interest rate swaps", "leverage instruments", "passive vehicles"],
            "methods": ["present value", "black-scholes", "binomial", "DCF", "relative value"]
        }
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def generate_document(self, domain: str, query_keywords: List[str]) -> str:
        """Generate synthetic trading document for a domain"""
        if domain not in self.DOMAINS:
            domain = random.choice(list(self.DOMAINS.keys()))

        domain_config = self.DOMAINS[domain]
        template = random.choice(domain_config["templates"])

        # Get placeholders from template
        placeholders = {
            "greek": lambda: random.choice(domain_config.get("greeks", ["delta", "gamma"])),
            "metric": lambda: random.choice(domain_config.get("metrics", ["rate of change"])),
            "position": lambda: random.choice(["call option", "put option", "portfolio", "hedge"]),
            "strategy": lambda: random.choice(domain_config.get("strategies", ["hedging"])),
            "method": lambda: random.choice(domain_config.get("methods", ["black-scholes"])),
            "action": lambda: random.choice(["increases", "decreases", "accelerates", "decelerates"]),
            "condition": lambda: random.choice(["price rises", "volatility increases", "time passes", "correlation changes"]),
            "risk": lambda: random.choice(domain_config.get("risks", ["downside risk"])),
            "instrument": lambda: random.choice(domain_config.get("instruments", ["puts"])),
            "exposure": lambda: random.choice(["directional", "volatility", "tail", "correlation"]),
            "purpose": lambda: random.choice(["protection", "income", "arbitrage", "speculation"]),
            "product": lambda: random.choice(domain_config.get("products", ["bonds"])),
            "definition": lambda: random.choice(domain_config.get("definitions", ["fixed income instruments"])),
            "market": lambda: random.choice(["OTC", "exchange", "dealer", "electronic"]),
            "technique": lambda: random.choice(domain_config.get("techniques", ["scenario analysis"])),
            "interpretation": lambda: random.choice(["measures potential loss", "quantifies risk", "estimates worst case", "bounds loss"]),
            "dimension": lambda: random.choice(["maturity", "coupon", "credit quality", "liquidity"]),
            "convexity": lambda: random.choice(["positive", "negative", "near zero"]),
        }

        # Fill template
        doc = template
        for _ in range(50):  # Avoid infinite loop
            for key, func in placeholders.items():
                placeholder = "{" + key + "}"
                if placeholder in doc:
                    doc = doc.replace(placeholder, func(), 1)

        # Add query keywords naturally
        if query_keywords:
            keywords_str = ", ".join(query_keywords[:2])
            doc = f"{doc} Key terms: {keywords_str}."

        return doc

    def generate_negative_samples(self, n_samples: int, exclude_domain: Optional[str] = None) -> List[str]:
        """Generate negative (irrelevant) documents"""
        negatives = []
        domains = [d for d in self.DOMAINS.keys() if d != exclude_domain]

        for _ in range(n_samples):
            domain = random.choice(domains)
            doc = self.generate_document(domain, [])
            negatives.append(doc)

        return negatives


class DatasetBuilder:
    """Build training dataset for FinBERT fine-tuning"""

    def __init__(
        self,
        golden_queries_path: Optional[str] = None,
        seed: int = 42,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
    ):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = 1.0 - train_ratio - val_ratio

        self.golden_queries_path = golden_queries_path
        self.corpus_generator = SyntheticCorpusGenerator(seed=seed)

        self.queries: List[Dict[str, Any]] = []
        self.corpus: List[str] = []
        self.triplets: List[TripletSample] = []

    def load_golden_queries(self, path: str) -> int:
        """Load golden queries from JSON file"""
        with open(path, 'r') as f:
            data = json.load(f)

        self.queries = data.get("queries", [])
        print(f"Loaded {len(self.queries)} golden queries from {path}")
        return len(self.queries)

    def build_corpus(self, min_docs_per_domain: int = 50) -> int:
        """Build synthetic corpus from query domains"""
        domain_docs = {}

        # Extract domains from queries
        domains = set()
        for query in self.queries:
            domain = query.get("category", "products")
            domains.add(domain)

        # Generate documents per domain
        for domain in domains:
            domain_docs[domain] = []
            for _ in range(min_docs_per_domain):
                keywords = []
                doc = self.corpus_generator.generate_document(domain, keywords)
                domain_docs[domain].append(doc)

        # Flatten corpus
        self.corpus = []
        for docs in domain_docs.values():
            self.corpus.extend(docs)

        print(f"Generated {len(self.corpus)} synthetic corpus documents")
        return len(self.corpus)

    def create_triplets(self, triplets_per_query: int = 2) -> int:
        """Create triplet (query, positive, negative) samples"""
        triplets = []

        for query_data in self.queries:
            query_text = query_data.get("query", "")
            query_id = query_data.get("id", 0)
            domain = query_data.get("category", "products")
            difficulty = query_data.get("difficulty", "intermediate")

            if not query_text:
                continue

            # Generate positive documents (relevant to query)
            keywords = query_data.get("ground_truth_keywords", [])
            for _ in range(triplets_per_query):
                positive = self.corpus_generator.generate_document(domain, keywords)

                # Generate negatives (irrelevant documents)
                negatives = self.corpus_generator.generate_negative_samples(
                    n_samples=1,
                    exclude_domain=domain
                )
                negative = negatives[0] if negatives else "Irrelevant document"

                triplet = TripletSample(
                    query=query_text,
                    positive=positive,
                    negative=negative,
                    query_id=query_id,
                    domain=domain,
                    difficulty=difficulty
                )
                triplets.append(triplet)

        self.triplets = triplets
        print(f"Created {len(triplets)} triplet samples")
        return len(triplets)

    def split_dataset(self) -> Tuple[DatasetSplit, DatasetSplit, DatasetSplit]:
        """Split triplets into train/val/test"""
        if not self.triplets:
            raise ValueError("No triplets created. Call create_triplets() first.")

        # Shuffle deterministically
        triplets_copy = self.triplets.copy()
        random.shuffle(triplets_copy)

        n_total = len(triplets_copy)
        n_train = int(n_total * self.train_ratio)
        n_val = int(n_total * self.val_ratio)

        train_triplets = triplets_copy[:n_train]
        val_triplets = triplets_copy[n_train:n_train + n_val]
        test_triplets = triplets_copy[n_train + n_val:]

        # Compute domain distribution for each split
        def domain_distribution(triplets):
            dist = {}
            for t in triplets:
                dist[t.domain] = dist.get(t.domain, 0) + 1
            return dist

        train_split = DatasetSplit(
            name="train",
            triplets=train_triplets,
            metadata={
                "size": len(train_triplets),
                "domain_distribution": domain_distribution(train_triplets),
            }
        )

        val_split = DatasetSplit(
            name="val",
            triplets=val_triplets,
            metadata={
                "size": len(val_triplets),
                "domain_distribution": domain_distribution(val_triplets),
            }
        )

        test_split = DatasetSplit(
            name="test",
            triplets=test_triplets,
            metadata={
                "size": len(test_triplets),
                "domain_distribution": domain_distribution(test_triplets),
            }
        )

        print(f"Dataset split: {len(train_triplets)} train, {len(val_triplets)} val, {len(test_triplets)} test")

        return train_split, val_split, test_split

    def export_to_jsonl(
        self,
        splits: Tuple[DatasetSplit, DatasetSplit, DatasetSplit],
        output_dir: str
    ) -> Dict[str, str]:
        """Export splits to JSONL format"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        file_paths = {}

        for split in splits:
            output_file = output_path / f"{split.name}_triplets.jsonl"

            with open(output_file, 'w') as f:
                for triplet in split.triplets:
                    record = {
                        "query": triplet.query,
                        "positive": triplet.positive,
                        "negative": triplet.negative,
                        "query_id": triplet.query_id,
                        "domain": triplet.domain,
                        "difficulty": triplet.difficulty,
                    }
                    f.write(json.dumps(record) + "\n")

            file_paths[split.name] = str(output_file)
            print(f"Exported {split.name} split to {output_file}")

        return file_paths

    def export_to_dict(self, splits: Tuple[DatasetSplit, DatasetSplit, DatasetSplit]) -> Dict[str, List[Dict]]:
        """Export splits to dictionary format (for in-memory usage)"""
        result = {}

        for split in splits:
            result[split.name] = [
                {
                    "query": t.query,
                    "positive": t.positive,
                    "negative": t.negative,
                    "query_id": t.query_id,
                    "domain": t.domain,
                    "difficulty": t.difficulty,
                }
                for t in split.triplets
            ]

        return result

    @staticmethod
    def create_benchmark_queries() -> List[Dict[str, Any]]:
        """Create minimal benchmark query set for quick validation"""
        queries = [
            {
                "id": 1,
                "query": "What is delta?",
                "category": "greeks_options",
                "difficulty": "easy",
                "ground_truth_keywords": ["delta", "hedge ratio", "directional exposure"]
            },
            {
                "id": 2,
                "query": "How do I hedge gamma?",
                "category": "hedging_strategies",
                "difficulty": "intermediate",
                "ground_truth_keywords": ["gamma", "rehedge", "convexity", "acceleration"]
            },
            {
                "id": 3,
                "query": "What is Value at Risk?",
                "category": "risk_management",
                "difficulty": "intermediate",
                "ground_truth_keywords": ["VaR", "loss", "percentile", "risk"]
            },
            {
                "id": 4,
                "query": "How do I trade volatility?",
                "category": "hedging_strategies",
                "difficulty": "advanced",
                "ground_truth_keywords": ["volatility", "vega", "implied vol", "straddle"]
            },
            {
                "id": 5,
                "query": "What is convexity in bonds?",
                "category": "products",
                "difficulty": "intermediate",
                "ground_truth_keywords": ["convexity", "bond", "duration", "interest rate"]
            },
        ]
        return queries


def build_quickstart_dataset(
    output_dir: str = "/workspace/group1-rag/finetuning/data",
    golden_queries_path: Optional[str] = None,
    n_queries: int = 100,
    triplets_per_query: int = 2,
) -> Dict[str, str]:
    """
    Quick-start function to build complete dataset.

    Args:
        output_dir: Where to save JSONL files
        golden_queries_path: Path to golden queries JSON
        n_queries: Number of queries to use (None for all)
        triplets_per_query: Triplets to generate per query

    Returns:
        Dictionary mapping split names to file paths
    """
    builder = DatasetBuilder(seed=42)

    # Load queries
    if golden_queries_path and Path(golden_queries_path).exists():
        builder.load_golden_queries(golden_queries_path)
        if n_queries:
            builder.queries = builder.queries[:n_queries]
    else:
        # Use benchmark queries
        builder.queries = DatasetBuilder.create_benchmark_queries()

    # Build corpus and triplets
    builder.build_corpus(min_docs_per_domain=30)
    builder.create_triplets(triplets_per_query=triplets_per_query)

    # Split and export
    train, val, test = builder.split_dataset()
    file_paths = builder.export_to_jsonl((train, val, test), output_dir)

    print(f"\nDataset complete:")
    print(f"  Training: {len(train.triplets)} triplets")
    print(f"  Validation: {len(val.triplets)} triplets")
    print(f"  Test: {len(test.triplets)} triplets")

    return file_paths


if __name__ == "__main__":
    import sys

    # Quick test
    builder = DatasetBuilder(seed=42)
    builder.queries = DatasetBuilder.create_benchmark_queries()
    builder.build_corpus(min_docs_per_domain=5)
    builder.create_triplets(triplets_per_query=2)
    train, val, test = builder.split_dataset()

    print("\n" + "="*70)
    print("Sample training triplet:")
    print("="*70)
    if train.triplets:
        sample = train.triplets[0]
        print(f"Query: {sample.query}")
        print(f"Positive: {sample.positive[:150]}...")
        print(f"Negative: {sample.negative[:150]}...")
