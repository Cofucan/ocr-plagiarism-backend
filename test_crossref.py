"""
Test script for the Crossref external analysis endpoint.
Demonstrates two-phase plagiarism detection: local + external sources.
"""

import asyncio
import json
from app.services.crossref import fetch_crossref_matches


async def test_crossref():
    """Test the Crossref API integration with sample text."""

    # Sample academic text about machine learning
    sample_text = """
    Machine learning is a subset of artificial intelligence that enables
    systems to learn and improve from experience without being explicitly
    programmed. Deep learning neural networks have revolutionized computer
    vision and natural language processing. Convolutional neural networks
    are particularly effective for image recognition tasks. The backpropagation
    algorithm is fundamental to training deep neural networks by computing
    gradients efficiently.
    """

    print("=" * 70)
    print("Testing Crossref Integration")
    print("=" * 70)
    print(f"\nInput text ({len(sample_text)} chars):")
    print(sample_text.strip())
    print("\n" + "-" * 70)

    try:
        keywords, results, latency = await fetch_crossref_matches(sample_text)

        print(f"\nExtracted Keywords ({len(keywords)}):")
        print(", ".join(keywords))
        print(f"\nQuery Time: {latency:.3f} seconds")
        print(f"Results Found: {len(results)}")
        print("\n" + "=" * 70)

        for idx, result in enumerate(results, 1):
            print(f"\nResult {idx}:")
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  DOI: {result.get('doi', 'N/A')}")
            print(f"  Year: {result.get('year', 'N/A')}")
            print(f"  Authors: {', '.join(result.get('authors', [])[:3])}")
            print(f"  Publisher: {result.get('publisher', 'N/A')}")
            print(f"  Score: {result.get('score', 'N/A')}")

            snippet = result.get('abstract_snippet')
            if snippet:
                print(f"  Abstract: {snippet[:150]}...")
            else:
                print("  Abstract: Not available")

            print(f"  URL: {result.get('url', 'N/A')}")
            print("-" * 70)

        # Test caching by running the same query again
        print("\n\nTesting cache (running same query again)...")
        keywords2, results2, latency2 = await fetch_crossref_matches(sample_text)
        print(f"Query Time (cached): {latency2:.3f} seconds")
        print(f"Results Found: {len(results2)}")

        if latency2 < latency:
            print("✓ Cache is working! Second query was faster.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nNote: Make sure to set a valid CROSSREF_MAILTO email in app/config.py")
        raise


if __name__ == "__main__":
    asyncio.run(test_crossref())
