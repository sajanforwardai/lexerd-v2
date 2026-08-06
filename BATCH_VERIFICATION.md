# Batch Address Verification for Dashboard

Verify street addresses for all 280+ unique properties displayed in the Maturity Radar dashboard using Google Maps Places API.

## Quick Start

```bash
# 1. Set your Google Maps API key
export GOOGLE_MAPS_API_KEY="your-api-key-here"

# 2. Run the batch verification script
python3 verify_dashboard_addresses.py
```

## What It Does

- Loads all 603 properties from the watchlist
- Identifies 280+ unique properties (by name, city, state)
- Searches Google Maps for each property
- Caches verified addresses locally
- Displays progress and summary

## Expected Output

```
🔍 Batch Address Verification for Lexerd Dashboard

============================================================

📊 Loading properties...
   Loaded 603 total properties
   Unique properties: 280

🔗 Verifying addresses with Google Maps...
============================================================
[  1/280]   0.4% | EVERGREEN AT SOUTHWOOD            | Tallahassee    FL | ✓ (cached)
[  2/280]   0.7% | BRAES HOLLOW APARTMENTS          | Houston        TX | ✓ 8701 S Braeswood Blvd, Houston, TX 77031
[  3/280]   1.1% | The Retreat By Watermark         | Corpus Christi TX | ✓ 5721 Timbergate Drive, Corpus Christi, TX 78414
  ...
[280/280] 100.0% | THE LINKS APARTMENTS             | Marysville     OH | ✗ Not found

============================================================
📈 VERIFICATION COMPLETE

Total properties checked:  280
  ✓ Newly verified:        ~210-240
  ✓ Already cached:        ~10-20
  ✗ Not found/failed:      ~30-50
  Coverage:                ~80-90%

💰 API Cost Estimate:
  Calls made: ~210-240
  Estimated cost: $1.50-1.70
```

## Cost

- **Per query**: $0.007 (Google Places Text Search API)
- **For 280 properties**: ~$1.50-$1.75
- **Within free tier**: Yes (1,000 queries/month free)

## Getting the API Key

See `ADDRESS_VERIFICATION_SETUP.md` for detailed instructions:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Places API
3. Create API Key
4. Set environment variable: `export GOOGLE_MAPS_API_KEY="your-key"`

## Caching

Results are stored in:
```
calibration/.cache/address_verification_cache.json
```

Once verified, properties are never re-queried (instant lookups).

## Integration with Dashboard

After running the batch verification:

1. Verified addresses are **automatically cached**
2. When users click "🔍 Verify Address" on a property, results are **instant** (no new API calls)
3. Dashboard shows:
   - Verified street address
   - Confidence score
   - Phone number (if available)
   - Website (if available)
   - Map link

## Troubleshooting

**"API key required" error**
- Ensure `GOOGLE_MAPS_API_KEY` environment variable is set
- Check it's valid in Google Cloud Console

**"No module named 'maturity_radar'"**
- Run from `/workspace/lexerd2/` directory:
  ```bash
  cd /workspace/lexerd2
  python3 verify_dashboard_addresses.py
  ```

**Script crashes mid-run**
- It's safe to restart - already cached properties won't be re-queried
- Check logs for which property failed
- Can manually verify that one in the dashboard

## Output Files

- **Cache file**: `calibration/.cache/address_verification_cache.json`
- **No output file** (results only stored in cache)

## What Gets Verified

For each unique property, the script:

✓ Searches Google Maps by: `"{property_name} apartments {city} {state}"`
✓ Confirms it's in the correct market
✓ Extracts street address, coordinates, phone, website
✓ Calculates confidence score (name similarity)
✓ Stores result in local cache

## Next Steps

1. **Get Google Maps API key** (5 min)
2. **Run batch verification** (5-10 min)
3. **Users can now click "Verify Address"** on dashboard (instant results)
4. **Dashboard shows verified addresses** with phone/website links

---

**Cost**: ~$1.50 (one-time)  
**Time**: ~5-10 minutes  
**Result**: 280+ properties with verified addresses, cached for instant dashboard lookups
