#!/usr/bin/env python3
"""Exhaustive address search with aggressive name variations and alternative strategies."""

import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "maturity-radar"))

from calibration.address_verification import GoogleMapsAddressVerifier
from maturity_radar.data_sources import load_loans

# Initialize verifier
try:
    verifier = GoogleMapsAddressVerifier(api_key="AIzaSyBB6qR5ULIDKWTv2s4c3e_Dlak3riHG9BU")
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)

# Properties to search
remaining = [
    ("Wimberley Hill Country", "Wimberley", "TX"),
    ("Clear Lake Park", "Clear Lake", "TX"),
    ("Palm Beach Gardens", "West Palm Beach", "FL"),
    ("Walden Brook Apartments", "Lithonia", "GA"),
    ("Lubbock Tech Campus", "Lubbock", "TX"),
    ("Edinburg Central Park", "Edinburg", "TX"),
    ("Magnolia Springs", "Magnolia", "TX"),
    ("Southern Garden", "Valparaiso", "FL"),
    ("Huntsville Tech Park", "Huntsville", "AL"),
    ("Topeka Heights Residential", "Topeka", "KS"),
    ("Villas at Traditions", "Bryan", "TX"),
    ("Charlotte Corporate Park", "Charlotte", "NC"),
    ("BROOKSTONE CROSSING", "Atlanta", "GA"),
    ("Sugar Land Technology", "Sugar Land", "TX"),
    ("Fort Worth Midtown", "Fort Worth", "TX"),
    ("The Club at Crystal Lake", "Deerfield Beach", "FL"),
    ("MEADOWS PLACE SENIORS VILLAGE", "Stafford", "TX"),
    ("Magnolia Flats Apartments", "Balcones Heights", "TX"),
    ("THE BLUFFS", "Junction City", "KS"),
]

def generate_aggressive_variations(name: str, city: str) -> list:
    """Generate aggressive name variations for searching."""
    variations = []

    # Original
    variations.append(name)

    # Remove articles
    clean = re.sub(r"^(the|a|an)\s+", "", name, flags=re.IGNORECASE).strip()
    if clean != name:
        variations.append(clean)

    # Remove "apartments", "apts", "complex", etc.
    for suffix in ["apartments", "apts", "apt", "complex", "community", "residences",
                    "residence", "towers", "tower", "lofts", "loft", "village", "senior",
                    "seniors", "residential", "place", "park", "gardens", "garden",
                    "hills", "hill", "springs", "spring", "crossing", "bluffs", "bluff"]:
        if suffix in clean.lower():
            variant = re.sub(r"\b" + suffix + r"\b", "", clean, flags=re.IGNORECASE).strip()
            if variant and variant not in variations:
                variations.append(variant)

    # Try just the key words
    words = clean.split()
    if len(words) > 1:
        for word in words:
            if len(word) > 3 and word.lower() not in ["the", "and", "or", "at"]:
                if word not in variations:
                    variations.append(word)

    # City-specific: maybe property is just known by the development name + city
    variations.append(f"{name} {city}")

    # Swap word order variations
    if " " in clean:
        words = clean.split()
        if len(words) == 2:
            variations.append(f"{words[1]} {words[0]}")

    return list(set(variations))[:10]  # Unique, limit to 10


print("🔥 EXHAUSTIVE SEARCH FOR 19 REMAINING PROPERTIES")
print("=" * 80)

found = 0
not_found_names = []

for i, (name, city, state) in enumerate(remaining, 1):
    print(f"\n[{i:2d}/{len(remaining)}] {name} | {city}, {state}")
    print("-" * 80)

    # Try original and variations
    variations = generate_aggressive_variations(name, city)

    result = None
    tried = 0

    for variant in variations:
        tried += 1
        print(f"   Attempt {tried}: Searching for '{variant}'...", end=" ", flush=True)

        verified = verifier.verify(variant, city, state)
        if verified:
            print(f"✓ FOUND!")
            print(f"      → {verified.address}")
            if verified.phone:
                print(f"      📞 {verified.phone}")
            print(f"      (Confidence: {verified.confidence_score:.0%})")
            result = verified
            found += 1
            break
        else:
            print("✗")

    if not result:
        print(f"   ✗ NOT FOUND after {tried} attempts")
        not_found_names.append(name)

print("\n" + "=" * 80)
print(f"\n📊 RESULTS:")
print(f"   Found: {found}/19")
print(f"   Still missing: {len(not_found_names)}/19")

if not_found_names:
    print(f"\nProperties still missing addresses:")
    for name in not_found_names:
        print(f"   - {name}")

print(f"\n" + "=" * 80)
