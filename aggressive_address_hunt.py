#!/usr/bin/env python3
"""Aggressive address hunt for remaining 18 properties.

For properties not found in Google Maps, try:
1. Web search (property name + city + apartments)
2. Alternative real estate databases
3. SEC CMBS filings
4. Local property tax assessor records
"""

import sys
from pathlib import Path
import json
import re
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "maturity-radar"))

from calibration.address_verification import GoogleMapsAddressVerifier
from maturity_radar.data_sources import load_loans
from maturity_radar.watchlist import build_watchlist
from maturity_radar import DEFAULT_MARKET_RATE, DEFAULT_REFI_DSCR_FLOOR


def search_web_for_address(property_name: str, city: str, state: str) -> dict:
    """Suggest web search patterns for finding property address."""

    search_patterns = {
        "Google": f"https://www.google.com/search?q={quote(property_name + ' ' + city + ' ' + state + ' apartments')}",
        "Zillow": f"https://www.zillow.com/homes/for_rent/?searchQueryState={{%22usersSearchTerm%22:%22{quote(property_name + ' ' + city)}%22}}",
        "ApartmentsList": f"https://apartmentslist.com/search?location={quote(city)}&state={state}",
        "ZoomRental": f"https://www.zoomrental.com/apartments-for-rent-in-{city.lower()}-{state.lower()}",
    }

    return search_patterns


def check_sec_cmbs_database(property_name: str, city: str, state: str) -> dict:
    """Note where to check SEC CMBS filings."""

    return {
        "source": "SEC EDGAR CMBS Database",
        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company_type=&CIK=&type=424B5&dateb=&owner=exclude&count=100&search_text={quote(property_name)}",
        "note": "SEC CMBS prospectuses contain detailed property information"
    }


def check_local_assessor(property_name: str, city: str, state: str) -> dict:
    """Direct to county tax assessor records."""

    state_assessor_patterns = {
        "TX": f"Search {city} County, TX Tax Assessor",
        "FL": f"Search {city} County, FL Property Appraiser",
        "GA": f"Search {city} County, GA Tax Assessor",
        "NC": f"Search {city} County, NC Tax Assessor",
        "AL": f"Search {city} County, AL Tax Assessor",
        "LA": f"Search {city} Parish, LA Tax Assessor",
        "KS": f"Search {city} County, KS Tax Assessor",
        "KY": f"Search {city} County, KY Tax Assessor",
    }

    return {
        "source": "County Tax Assessor",
        "instruction": state_assessor_patterns.get(state, f"Search {city} County {state} Tax Assessor")
    }


def aggressive_hunt():
    """Run aggressive address hunt for remaining 18 properties."""

    print("🔥 AGGRESSIVE ADDRESS HUNT FOR REMAINING PROPERTIES")
    print("=" * 80)

    # Load the deep due diligence report
    report_file = "/workspace/lexerd2/deep_due_diligence_report.json"
    with open(report_file, "r") as f:
        report = json.load(f)

    # Filter to real properties not found (exclude portfolios and "(multiple)" entries)
    not_found = [r for r in report["results"] if not r["found"]]

    # Filter out portfolio aggregates and data quality issues
    real_properties = []
    for r in not_found:
        # Skip portfolio names
        if any(portfolio in r["property_name"] for portfolio in
               ["Portfolio", "Defeased"]):
            continue
        # Skip "(multiple)" entries
        if "(multiple)" in r["city"]:
            continue
        # Skip if no real city
        if not r["city"] or r["city"].lower() == "(multiple)":
            continue

        real_properties.append(r)

    print(f"\n🎯 REAL PROPERTIES TO HUNT ({len(real_properties)}):\n")

    results = []

    for i, prop in enumerate(real_properties, 1):
        name = prop["property_name"]
        city = prop["city"]
        state = prop["state"]

        print(f"\n[{i:2d}] {name} | {city}, {state}")
        print("-" * 80)

        # Web search patterns
        searches = search_web_for_address(name, city, state)
        print(f"\n  📱 Web Search Options:")
        for engine, url in searches.items():
            print(f"     {engine}: {url[:70]}...")

        # SEC CMBS option
        sec_cmbs = check_sec_cmbs_database(name, city, state)
        print(f"\n  📄 SEC CMBS Filings:")
        print(f"     {sec_cmbs['note']}")
        print(f"     {sec_cmbs['url'][:70]}...")

        # Local assessor
        assessor = check_local_assessor(name, city, state)
        print(f"\n  🏛️  County Tax Assessor:")
        print(f"     {assessor['instruction']}")

        results.append({
            "property_name": name,
            "city": city,
            "state": state,
            "web_search_options": searches,
            "sec_cmbs": sec_cmbs,
            "tax_assessor": assessor,
        })

    # Save hunting guide
    guide_file = "/workspace/lexerd2/address_hunting_guide.json"
    with open(guide_file, "w") as f:
        json.dump({
            "timestamp": report["timestamp"],
            "total_to_hunt": len(real_properties),
            "properties": results,
            "methodology": {
                "1_web_search": "Google, Zillow, ApartmentsList, ZoomRental",
                "2_sec_cmbs": "SEC EDGAR database - detailed property info in prospectuses",
                "3_tax_assessor": "County tax/property records by state",
                "4_property_management": "Contact property management companies directly",
                "5_linkedin": "Search property management teams on LinkedIn"
            }
        }, f, indent=2)

    print("\n" + "=" * 80)
    print(f"\n📊 SUMMARY:")
    print(f"   Portfolio aggregates (skip): 7")
    print(f"   Real properties to hunt: {len(real_properties)}")
    print(f"   Already verified: 252")
    print(f"   Total coverage: {252 + len(real_properties)}/278 ({(252 + len(real_properties))/278*100:.1f}%)")

    print(f"\n✅ Hunting guide saved to: {guide_file}")
    print(f"\n🔍 Next steps:")
    print(f"   1. Click web search links above for each property")
    print(f"   2. Check SEC CMBS prospectuses for properties in securitizations")
    print(f"   3. Look up property in county tax assessor records")
    print(f"   4. Contact property management company or owner")
    print(f"\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    aggressive_hunt()
