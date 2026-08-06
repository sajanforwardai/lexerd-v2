#!/usr/bin/env python3
"""
Example usage of the Tier 2 Entity Extraction Service

Demonstrates:
1. Pattern-based extraction (fallback mode)
2. LLM-based extraction (with Claude)
3. Result serialization and analysis
"""

import json
import time
from entity_extractor import EntityExtractor, EntityType, extract_entities

# Sample trading texts from Tier 1 retrieval
SAMPLE_TEXTS = [
    {
        "name": "Greeks + Strategy",
        "text": "High gamma exposure in index options requires active delta hedging. Consider a long iron butterfly to neutralize gamma while capturing theta decay in lower volatility environments."
    },
    {
        "name": "Earnings Event Analysis",
        "text": "Earnings volatility spike 25% YoY creates significant arbitrage opportunity. In high volatility regimes, long skew strategies can capture mean reversion. FOMC meeting precedes elevated vol."
    },
    {
        "name": "Vol Surface Dynamics",
        "text": "The volatility smile shows significant curvature with negative skew. High gamma and vega exposure dominates the term structure. Backwardation indicates supply constraints."
    },
]


def example_1_fallback_extraction():
    """Example 1: Pattern-based extraction (no LLM)"""
    print("=" * 70)
    print("EXAMPLE 1: Pattern-Based Extraction (Fallback Mode)")
    print("=" * 70)

    extractor = EntityExtractor(use_llm=False)

    for sample in SAMPLE_TEXTS[:1]:
        print(f"\nInput: {sample['name']}")
        print(f"Text: {sample['text'][:100]}...")

        # Extract entities
        start = time.time()
        result = extractor.extract(sample["text"])
        elapsed = (time.time() - start) * 1000

        # Display results
        print(f"\nLatency: {elapsed:.2f}ms")
        print(f"Extraction Method: {'Fallback (patterns)' if result.used_fallback else 'LLM'}")

        # Entities
        print(f"\nExtracted {len(result.entities)} entities:")
        for entity in result.entities:
            print(
                f"  • {entity.text:30s} | Type: {entity.entity_type.value:20s} | "
                f"Confidence: {entity.confidence:.2f}"
            )

        # Relationships
        if result.relationships:
            print(f"\nInferred {len(result.relationships)} relationships:")
            for rel in result.relationships:
                print(
                    f"  • {rel.source_entity:20s} --{rel.relationship_type.value:15s}--> "
                    f"{rel.target_entity:20s} (conf: {rel.confidence:.2f})"
                )


def example_2_json_output():
    """Example 2: JSON serialization"""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: JSON Output")
    print("=" * 70)

    extractor = EntityExtractor(use_llm=False)
    result = extractor.extract(SAMPLE_TEXTS[1]["text"])

    # Serialize to JSON
    result_dict = result.to_dict()

    # Pretty print
    print("\nJSON Output (first entity + relationship):")
    print(json.dumps(result_dict, indent=2)[:800] + "\n...")


def example_3_entity_type_filtering():
    """Example 3: Filter entities by type"""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Entity Type Filtering")
    print("=" * 70)

    extractor = EntityExtractor(use_llm=False)

    for sample in SAMPLE_TEXTS:
        result = extractor.extract(sample["text"])

        print(f"\n{sample['name']}:")

        # Greek entities
        greeks = [e for e in result.entities if e.entity_type.value.startswith("Greek")]
        if greeks:
            print(f"  Greeks: {', '.join(e.text for e in greeks)}")

        # Strategies
        strategies = [e for e in result.entities if e.entity_type == EntityType.STRATEGY]
        if strategies:
            print(f"  Strategies: {', '.join(e.text for e in strategies)}")

        # Regimes
        regimes = [e for e in result.entities if e.entity_type == EntityType.MARKET_REGIME]
        if regimes:
            print(f"  Regimes: {', '.join(e.text for e in regimes)}")

        # Events
        events = [e for e in result.entities if e.entity_type == EntityType.EVENT]
        if events:
            print(f"  Events: {', '.join(e.text for e in events)}")


def example_4_confidence_analysis():
    """Example 4: Analyze confidence scores"""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Confidence Analysis")
    print("=" * 70)

    extractor = EntityExtractor(use_llm=False)

    all_results = []
    for sample in SAMPLE_TEXTS:
        result = extractor.extract(sample["text"])
        all_results.append(result)

    # Aggregate statistics
    all_entities = [e for r in all_results for e in r.entities]
    all_relationships = [r for result in all_results for r in result.relationships]

    print(f"\nEntity Statistics:")
    print(f"  Total entities: {len(all_entities)}")
    print(f"  Avg confidence: {sum(e.confidence for e in all_entities) / len(all_entities):.3f}")
    print(f"  Min/Max: {min(e.confidence for e in all_entities):.3f} / {max(e.confidence for e in all_entities):.3f}")

    print(f"\nRelationship Statistics:")
    if all_relationships:
        print(f"  Total relationships: {len(all_relationships)}")
        print(f"  Avg confidence: {sum(r.confidence for r in all_relationships) / len(all_relationships):.3f}")
    else:
        print(f"  No relationships inferred")

    # By entity type
    print(f"\nConfidence by Entity Type:")
    entity_types = {}
    for entity in all_entities:
        type_name = entity.entity_type.value
        if type_name not in entity_types:
            entity_types[type_name] = []
        entity_types[type_name].append(entity.confidence)

    for type_name in sorted(entity_types.keys()):
        confidences = entity_types[type_name]
        print(
            f"  {type_name:20s}: avg={sum(confidences)/len(confidences):.3f}, "
            f"count={len(confidences)}"
        )


def example_5_convenience_function():
    """Example 5: Using convenience function"""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Convenience Function")
    print("=" * 70)

    text = "Gamma scalping in mean-reverting markets captures alpha through delta rebalancing."

    # Direct usage
    result_dict = extract_entities(text)

    print(f"\nInput: {text}")
    print(f"\nResult Summary:")
    print(f"  Entities: {result_dict['summary']['entity_count']}")
    print(f"  Relationships: {result_dict['summary']['relationship_count']}")
    print(f"  Avg Entity Confidence: {result_dict['summary']['avg_entity_confidence']:.3f}")
    print(f"  Latency: {result_dict['latency_ms']:.2f}ms")


def example_6_llm_usage():
    """Example 6: Using with LLM (Claude)

    This example shows how to use with Claude, but requires API key.
    Set ANTHROPIC_API_KEY environment variable.
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 6: LLM-Based Extraction (With Claude)")
    print("=" * 70)

    try:
        from anthropic import Anthropic

        client = Anthropic()
        extractor = EntityExtractor(llm_client=client, use_llm=True)

        text = SAMPLE_TEXTS[0]["text"]
        print(f"\nInput: {text[:100]}...")
        print("\nNote: First call will use LLM (300-400ms). Subsequent calls fallback to patterns if LLM unavailable.")

        result = extractor.extract(text)

        print(f"\nExtraction Method: {'LLM' if not result.used_fallback else 'Fallback'}")
        print(f"Entities Found: {len(result.entities)}")
        print(f"Relationships Found: {len(result.relationships)}")
        print(f"Latency: {result.latency_ms:.2f}ms")

        if result.entities:
            print(f"\nSample Entity:")
            e = result.entities[0]
            print(f"  Text: {e.text}")
            print(f"  Type: {e.entity_type.value}")
            print(f"  Confidence: {e.confidence:.3f}")

    except ImportError:
        print("\nAnthropicAPI client not available. Install with: pip install anthropic")
    except Exception as e:
        print(f"\nLLM example skipped: {e}")


def main():
    """Run all examples"""
    print("\n" + "#" * 70)
    print("# TIER 2 ENTITY EXTRACTION SERVICE - USAGE EXAMPLES")
    print("#" * 70)

    example_1_fallback_extraction()
    example_2_json_output()
    example_3_entity_type_filtering()
    example_4_confidence_analysis()
    example_5_convenience_function()
    example_6_llm_usage()

    print("\n" + "#" * 70)
    print("# END OF EXAMPLES")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    main()
