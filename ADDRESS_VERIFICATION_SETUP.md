# Address Verification Setup

Address verification uses Google Maps Places API to verify property names and find accurate street addresses.

## Features

- **Property search**: Search for properties by name and market
- **Address verification**: Match results to confirm correct property
- **Address details**: Extract phone, website, coordinates
- **Caching**: Store results locally to minimize API calls
- **Confidence scoring**: Rank matches by name similarity

## Setup

### 1. Get Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable these APIs:
   - Places API
   - Maps JavaScript API
4. Create API credentials (API Key type)
5. Restrict key to:
   - Application restrictions: None (or HTTP referrer)
   - API restrictions: Places API, Maps JavaScript API

### 2. Set Environment Variable

```bash
export GOOGLE_MAPS_API_KEY="your-api-key-here"
```

Or add to `.streamlit/secrets.toml`:
```toml
GOOGLE_MAPS_API_KEY = "your-api-key-here"
```

Or add to your shell profile:
```bash
echo 'export GOOGLE_MAPS_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Verify Setup

```bash
python3 -c "from calibration.address_verification import GoogleMapsAddressVerifier; v = GoogleMapsAddressVerifier(); print('✓ API key loaded')"
```

## Usage

### In Python

```python
from calibration.address_verification import verify_address

# Verify a property
result = verify_address(
    property_name="Oak Ridge Apartments",
    city="Jacksonville",
    state="FL"
)

if result:
    print(f"Address: {result.address}")
    print(f"Lat/Lon: {result.lat}, {result.lon}")
    print(f"Confidence: {result.confidence_score:.0%}")
    if result.phone:
        print(f"Phone: {result.phone}")
    if result.website:
        print(f"Website: {result.website}")
```

### In Streamlit Dashboard

Click the **"🔍 Verify Address"** button on any property in the Maturity Radar dashboard.

Results are cached locally, so repeated lookups are instant.

## Caching

Verified addresses are cached in:
```
/workspace/lexerd2/calibration/.cache/address_verification_cache.json
```

To clear cache:
```python
from calibration.address_verification import AddressVerificationCache
cache = AddressVerificationCache()
cache.clear()
```

## API Costs

- **Cost**: ~$0.007 per query (Text Search API)
- **Free tier**: 1,000 queries/month before costs apply
- **Typical usage**: ~50-200 queries/month (depends on watchlist size)

At typical usage (~100 queries/month), this costs <$1/month.

## Troubleshooting

### "API key required" error
- Ensure `GOOGLE_MAPS_API_KEY` environment variable is set
- Verify API key is valid in [Google Cloud Console](https://console.cloud.google.com/)
- Ensure Places API is enabled

### "Address not found" 
- Property may not be listed publicly on Google Maps
- Try searching manually on [Google Maps](https://maps.google.com)
- Verify property name spelling and location

### Slow responses
- First search for a property takes ~2-3 seconds (API call)
- Subsequent searches are instant (cached)
- Cache is persistent across dashboard restarts

### High API usage
- Check `address_verification_cache.json` for stored results
- Clear cache if needed and searches will be re-done
- Monitor Google Cloud Console for usage

## Related Files

- **Module**: `calibration/address_verification.py`
- **Tests**: `calibration/tests/test_address_verification.py`
- **Dashboard**: `maturity-radar/app.py` (search for "Verify Address")
- **Cache**: `.cache/address_verification_cache.json`
