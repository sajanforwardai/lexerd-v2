#!/usr/bin/env python3
"""
Example Usage of Group One RAG Knowledge Graph
==============================================

Demonstrates:
1. Client initialization (mock mode)
2. Corpus ingestion
3. Query execution
4. Statistics and export
"""

import logging
from kg_client import KGClient
from corpus_ingestion import ingest_corpus_files, export_ingestion_report

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def print_header(title):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def example_1_initialize_client():
    """Example 1: Initialize the KG client."""
    print_header("Example 1: Initialize KG Client")

    client = KGClient(use_mock=True)
    print(f"✓ Created client in mock mode (no Neo4j required)")
    print(f"  - Nodes cached: {len(client.node_cache)}")
    print(f"  - Relationships: {len(client.rel_cache)}")

    return client


def example_2_manual_node_creation(client):
    """Example 2: Manually create nodes and relationships."""
    print_header("Example 2: Manual Node Creation")

    # Create nodes
    strategy = client.add_node(
        entity_type="Strategy",
        name="Delta Hedging",
        attributes={
            "description": "Continuous rebalancing to maintain delta-neutral exposure",
            "risk_level": "medium",
            "capital_requirement": "high",
            "time_horizon": "1-30 days"
        }
    )
    print(f"✓ Created Strategy node: {strategy.name} (id={strategy.id[:8]}...)")

    regime = client.add_node(
        entity_type="MarketRegime",
        name="High-Vol Market",
        attributes={
            "characteristics": "Elevated implied volatility, wide bid-ask spreads",
            "volatility_level": "high",
            "risk_profile": "aggressive"
        }
    )
    print(f"✓ Created MarketRegime node: {regime.name} (id={regime.id[:8]}...)")

    greek = client.add_node(
        entity_type="Greeks",
        name="Delta",
        attributes={
            "definition": "Rate of change of option price w.r.t. underlying price",
            "formula": "∂C/∂S",
            "interpretation": "Directional exposure",
            "risk_factor": "Stock price movement"
        }
    )
    print(f"✓ Created Greeks node: {greek.name} (id={greek.id[:8]}...)")

    # Create relationships
    rel1 = client.add_relationship(
        strategy.id,
        "applies_to",
        regime.id,
        confidence=0.85,
        evidence="Delta hedging is highly effective in high-volatility environments"
    )
    print(f"✓ Created relationship: {strategy.name} -[applies_to:0.85]-> {regime.name}")

    rel2 = client.add_relationship(
        strategy.id,
        "requires",
        greek.id,
        confidence=0.95,
        evidence="Delta is fundamental to delta hedging mechanics"
    )
    print(f"✓ Created relationship: {strategy.name} -[requires:0.95]-> {greek.name}")

    return client


def example_3_corpus_ingestion(client):
    """Example 3: Ingest financial corpus."""
    print_header("Example 3: Corpus Ingestion")

    print("Ingesting corpus files from /workspace/corpus/finance/...")
    stats = ingest_corpus_files(client)

    print(f"\n✓ Ingestion Complete")
    print(f"  Files processed: {stats['files_processed']}")
    print(f"  Nodes created: {stats['nodes_created']}")
    print(f"  Relationships created: {stats['relationships_created']}")

    if stats['errors']:
        print(f"  Errors: {len(stats['errors'])}")

    print(f"\nEntities by type:")
    for entity_type, count in sorted(stats['entities_by_type'].items()):
        if count > 0:
            print(f"  - {entity_type}: {count}")

    return client


def example_4_query_strategies_by_regime(client):
    """Example 4: Query strategies by market regime."""
    print_header("Example 4: Query Strategies by Regime")

    regime_name = "High-Vol Market"
    print(f"Finding strategies for regime: '{regime_name}'...")
    results = client.query_strategies_by_regime(regime_name)

    if results:
        print(f"\nFound {len(results)} strategies:")
        for i, result in enumerate(results[:5], 1):
            print(f"\n  {i}. {result['strategy_name']}")
            print(f"     Confidence: {result['confidence']:.2f}")
            if result['description']:
                print(f"     Description: {result['description'][:60]}...")
            print(f"     Evidence: {result['evidence']}")
    else:
        print(f"No strategies found for {regime_name}")

    return results


def example_5_query_greeks_by_event(client):
    """Example 5: Query Greeks affected by an event."""
    print_header("Example 5: Query Greeks by Event")

    event_name = "Earnings Announcement"
    print(f"Finding Greeks affected by: '{event_name}'...")
    results = client.query_greeks_by_event(event_name)

    if results:
        print(f"\nFound {len(results)} Greeks affected:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. {result['greek']}")
            print(f"     Interpretation: {result['interpretation']}")
            if result['opportunities']:
                print(f"     Opportunities: {', '.join(result['opportunities'])}")
    else:
        print(f"No Greeks found for {event_name}")

    return results


def example_6_query_opportunities(client):
    """Example 6: Query trading opportunities from order flow."""
    print_header("Example 6: Query Trading Opportunities")

    print("Finding high-confidence trading opportunities...")
    results = client.query_opportunities_from_misalignments()

    if results:
        print(f"\nFound {len(results)} opportunities:")
        for i, result in enumerate(results[:5], 1):
            print(f"\n  {i}. {result['opportunity']}")
            print(f"     Confidence: {result['confidence']:.2f}")
            print(f"     Pattern: {result['order_flow_pattern']}")
            if result['description']:
                print(f"     Description: {result['description'][:60]}...")
    else:
        print("No opportunities found")

    return results


def example_7_query_position_constraints(client):
    """Example 7: Query position risk constraints."""
    print_header("Example 7: Query Position Constraints")

    # First, add a position to the graph
    position = client.add_node(
        entity_type="Position",
        name="Long 100 XYZ Calls",
        attributes={
            "type": "Long Call",
            "size": 100,
            "entry_price": 2.50,
            "current_value": 3.75
        }
    )

    # Add risk constraints
    vega_risk = client.add_node(
        entity_type="RiskMetric",
        name="Vega Risk",
        attributes={
            "definition": "Sensitivity to implied volatility changes",
            "measurement": "P&L per 1% volatility change",
            "mitigation": "Volatility hedging"
        }
    )

    gamma_risk = client.add_node(
        entity_type="RiskMetric",
        name="Gamma Risk",
        attributes={
            "definition": "Convexity risk from delta changes",
            "measurement": "P&L per 1% underlying move",
            "mitigation": "Frequent rebalancing"
        }
    )

    client.add_relationship(position.id, "exposed_to", vega_risk.id, confidence=0.90)
    client.add_relationship(position.id, "exposed_to", gamma_risk.id, confidence=0.85)

    print(f"Created position: {position.name}")
    print(f"\nQuerying risk constraints...")
    results = client.query_position_constraints(position.name)

    if results:
        print(f"\nFound {len(results)} risk constraints:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. {result['risk_metric']}")
            print(f"     Definition: {result['definition']}")
            print(f"     Measurement: {result['measurement']}")
            print(f"     Confidence: {result['confidence']:.2f}")
    else:
        print("No constraints found")

    return results


def example_8_get_statistics(client):
    """Example 8: Get knowledge graph statistics."""
    print_header("Example 8: Knowledge Graph Statistics")

    stats = client.get_statistics()

    print(f"Total Nodes: {stats['total_nodes']}")
    print(f"Total Relationships: {stats['total_relationships']}")
    print(f"Average Relationship Confidence: {stats['average_confidence']:.2f}")
    print(f"Query Cache Size: {stats['cache_size']}")

    print(f"\nNodes by Entity Type:")
    for entity_type in sorted(stats['entities_by_type'].keys()):
        count = stats['entities_by_type'][entity_type]
        if count > 0:
            print(f"  - {entity_type}: {count}")

    print(f"\nRelationships by Type:")
    for rel_type in sorted(stats['relationships_by_type'].keys()):
        count = stats['relationships_by_type'][rel_type]
        if count > 0:
            print(f"  - {rel_type}: {count}")

    return stats


def example_9_export_and_import(client):
    """Example 9: Export and import the knowledge graph."""
    print_header("Example 9: Export/Import Knowledge Graph")

    export_path = "/tmp/kg_export.json"

    # Export
    print(f"Exporting knowledge graph to {export_path}...")
    client.export_graph(export_path)
    print(f"✓ Export complete")

    # Import
    print(f"\nImporting knowledge graph from {export_path}...")
    client2 = KGClient(use_mock=True)
    client2.import_graph(export_path)
    print(f"✓ Import complete")

    stats1 = client.get_statistics()
    stats2 = client2.get_statistics()

    print(f"\nVerification:")
    print(f"  Original nodes: {stats1['total_nodes']} → Imported: {stats2['total_nodes']}")
    print(f"  Original rels:  {stats1['total_relationships']} → Imported: {stats2['total_relationships']}")

    match = stats1['total_nodes'] == stats2['total_nodes'] and \
            stats1['total_relationships'] == stats2['total_relationships']
    print(f"  Match: {'✓ YES' if match else '✗ NO'}")

    return client2


def example_10_performance_test(client):
    """Example 10: Performance testing."""
    print_header("Example 10: Performance Testing")

    import time

    queries = [
        ("strategies_by_regime", lambda: client.query_strategies_by_regime("High-Vol Market")),
        ("greeks_by_event", lambda: client.query_greeks_by_event("Earnings Announcement")),
        ("opportunities", lambda: client.query_opportunities_from_misalignments()),
    ]

    print(f"Running {len(queries)} query performance tests...\n")

    times = {}
    for name, query_func in queries:
        start = time.time()
        results = query_func()
        elapsed = (time.time() - start) * 1000  # Convert to ms

        times[name] = elapsed
        status = "✓" if elapsed < 50 else "⚠"
        print(f"{status} {name:30s} {elapsed:6.2f}ms  ({len(results)} results)")

    avg_time = sum(times.values()) / len(times)
    print(f"\nAverage query time: {avg_time:.2f}ms")
    print(f"Target performance: ≤50ms {'✓ MET' if avg_time <= 50 else '⚠ EXCEEDED'}")

    return times


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("  Group One RAG Knowledge Graph - Example Usage")
    print("="*70)

    # Example 1: Initialize
    client = example_1_initialize_client()

    # Example 2: Manual creation
    example_2_manual_node_creation(client)

    # Example 3: Corpus ingestion
    example_3_corpus_ingestion(client)

    # Example 4-6: Queries
    example_4_query_strategies_by_regime(client)
    example_5_query_greeks_by_event(client)
    example_6_query_opportunities(client)

    # Example 7: Position constraints
    example_7_query_position_constraints(client)

    # Example 8: Statistics
    example_8_get_statistics(client)

    # Example 9: Export/Import
    example_9_export_and_import(client)

    # Example 10: Performance
    example_10_performance_test(client)

    # Final summary
    print_header("Summary")
    final_stats = client.get_statistics()
    print(f"✓ Successfully demonstrated Group One RAG Knowledge Graph")
    print(f"✓ Final graph contains {final_stats['total_nodes']} nodes and "
          f"{final_stats['total_relationships']} relationships")
    print(f"✓ Average relationship confidence: {final_stats['average_confidence']:.2f}")

    print("\n" + "="*70)
    print("  Examples Complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
