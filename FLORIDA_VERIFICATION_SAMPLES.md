# Florida Property Verification - Sample Properties

This guide shows what you're looking for when verifying addresses. Use these as examples for the other properties.

## Sample 1: Clubside Apartments (Sarasota County, Venice)

**What you'll find:**

1. **Google Maps Search** → Shows property location with street address
   - Look for: Street address, apartment complex name, exact location on map
   - Example: "Clubside Apartments, 123 Clubside Lane, Venice, FL 34292"

2. **Apartments.com** → Official property listing with full address
   - Best source for complete street address
   - Shows: Property details, amenities, contact info, reviews
   - Address format: "Street Address, City, State ZIP"

3. **Zillow** → Property details page
   - Shows: Address, property type, owner info, tax records
   - Confirm: This is the same property

4. **County Assessor** (Sarasota County)
   - Owner name, parcel number, tax records
   - Confirms: Property ownership + address match

**Record in CSV:**
```
Property Name: Clubside Apartments
City: Venice
County: Sarasota
Address: 123 Clubside Lane, Venice, FL 34292
Source: apartments.com
Confidence: 1.0
```

---

## Sample 2: Beach Bluff Apartments (Duval County, Jacksonville)

**What you'll find:**

1. **Google Maps** → Multiple results for Jacksonville area
   - Look for: "Beach Bluff Apartments" specifically
   - Street address should be in Jacksonville (or nearby)

2. **Apartments.com** → Property page
   - Full address: "456 Beach Bluff Ave, Jacksonville, FL 32210"
   - Or similar address in Jacksonville area

3. **Zillow** → Confirm address & property type
   - Should match Apartments.com address

4. **County Assessor** (Duval County)
   - Verify owner/property records match

**Record in CSV:**
```
Property Name: Beach Bluff Apartments
City: Jacksonville
County: Duval
Address: 456 Beach Bluff Ave, Jacksonville, FL 32210
Source: apartments.com
Confidence: 1.0
```

---

## Sample 3: Innovo at Sunrise (Broward County, Sunrise)

**What you'll find:**

1. **Google Maps** → Search "Innovo at Sunrise Broward"
   - Shows location in Sunrise, FL (western Fort Lauderdale area)
   - Street address visible on map

2. **Apartments.com** → Property listing
   - Full address: "789 Innovo Boulevard, Sunrise, FL 33323"
   - Shows: Amenities, floor plans, pricing, reviews

3. **Zillow** → Property details
   - Confirms address and property information

4. **County Assessor** (Broward County)
   - Owner & tax records should match property

**Record in CSV:**
```
Property Name: Innovo at Sunrise
City: Sunrise
County: Broward
Address: 789 Innovo Boulevard, Sunrise, FL 33323
Source: apartments.com
Confidence: 1.0
```

---

## Verification Workflow by Property Type

### Large Apartment Complexes (Most Common)
✅ **Best sources:** Apartments.com, Zillow, Google Maps
- These properties usually have official property pages
- Address is publicly listed for leasing purposes
- Time per property: 2-3 minutes

**What to expect:**
- Property name exactly matches
- Street address clearly shown
- City, state, ZIP included
- Multiple sources confirm same address

### Smaller Residential Properties
✅ **Best sources:** Google Maps, County Assessor, Zillow
- Smaller complexes may not be on Apartments.com
- Use County Assessor for official address
- Google Maps shows exact location

**What to expect:**
- May need to verify via owner name + property address
- County records are authoritative
- Time per property: 3-5 minutes

### Historic or Specialty Properties
✅ **Best sources:** Google Search, County Assessor, Zillow
- Some historic/specialty properties harder to find online
- Use Google Search to find news articles, press releases
- County records are always reliable source

**What to expect:**
- May take longer to verify (5-10 minutes)
- Multiple sources may confirm same address
- County Assessor is fallback if Apartments.com/Zillow don't work

---

## Common Issues & Solutions

### Issue 1: Property Not Found on Apartments.com
**Solution:** Use Zillow or Google Maps instead
- Apartments.com focuses on rental listings
- Some properties may be owner-occupied or managed privately
- Google Maps usually has complete address
- County Assessor always has the address (it's public record)

### Issue 2: Multiple Addresses for Same Property
**Solution:** Use most complete address (with ZIP code)
- Some properties may have multiple addresses listed
- Use: Street Address, City, State, ZIP (most complete)
- Ignore: P.O. boxes or general city addresses
- Verify: County Assessor confirms which is primary address

### Issue 3: Property Name Variations (e.g., "CLUBSIDE APARTMENTS" vs "Clubside Apartments")
**Solution:** Address should be identical regardless of name capitalization
- Match on address, not name format
- "CLUBSIDE APARTMENTS" and "Clubside Apartments" = same property
- Record the actual street address (primary identifier)

### Issue 4: Old or Outdated Listings
**Solution:** Cross-reference with multiple sources
- Google Maps shows current location
- Apartments.com shows if property is currently listed
- County Assessor shows current owner/parcel info
- If 2+ sources agree, address is correct

---

## Expected Address Formats

### Standard Florida Address Format
```
[Street Number] [Street Name] [Street Type], [City], FL [ZIP]
```

**Examples:**
- `123 Main Street, Tampa, FL 33602`
- `456 Beach Boulevard, Jacksonville, FL 32210`
- `789 Park Avenue North, St. Petersburg, FL 33701`
- `1000 Miracle Mile, Coral Gables, FL 33134`

### What NOT to Record
❌ P.O. boxes (not street addresses)
❌ Just city name without street
❌ "Downtown [City]" without specific address
❌ URLs or website addresses
❌ Phone numbers

### Format to Use in CSV
- **Address:** `123 Main Street, Tampa, FL 33602`
- **Source:** `apartments.com` or `zillow` or `county_assessor` or `google_maps`
- **Confidence:** `1.0` (for manual verification)

---

## Batch Processing Tips

### Organize by County
Group verification by county for faster processing:
1. Sarasota County (2 properties)
2. Duval County (5 properties)
3. Hillsborough County (3 properties)
... etc.

**Advantage:** County Assessor links stay open in one tab

### Use Multiple Browser Tabs
- Tab 1: fl_property_lookup.html (property list)
- Tab 2: Google Maps
- Tab 3: Apartments.com
- Tab 4: County Assessor
- Tab 5: Zillow

**Workflow:** Click link in Tab 1 → search in Tab 2 → confirm in Tab 3 → record address

### Track Progress in CSV
- Open CSV in spreadsheet (Google Sheets recommended for cloud sync)
- Check off each row as completed
- Color-code verified properties
- Save frequently

### Estimated Timeline
- **Fast (2 min per property):** Google Maps → Apartments.com = ~1 hour
- **Thorough (5 min per property):** All 5 sources verified = ~2-3 hours
- **Very thorough (10 min per property):** With research + verification = 5-6 hours

---

## After Verification: Import to Database

Once you've verified 5-10 properties in CSV:

```bash
python scripts/update_fl_addresses_from_csv.py fl_property_lookup.csv 1.0 manual_verification
```

This will:
1. Read your CSV file
2. Match properties to database records
3. Update addresses with confidence=1.0 (fully verified)
4. Create audit trail (timestamp, source, confidence)
5. Show results: "Updated: X loans"

**Check results:**
```bash
python scripts/audit_florida_discovery.py
```

---

## Key Reminders

✅ **DO:**
- Use multiple sources to confirm address
- Record exact street address with ZIP code
- Note which source you used
- Include confidence level (1.0 for manual verification)
- Keep audit trail of sources

❌ **DON'T:**
- Guess or assume address (always verify)
- Use incomplete addresses (must have street + city + state + ZIP)
- Mix up similar property names (verify address matches)
- Forget to update confidence level
- Lose track of which source you used

---

## Questions? Hints:

**Q: What if I can't find the property anywhere?**
A: It may have been renamed, merged, or demolished. Try:
1. County Assessor search (most reliable)
2. Google Search with property name + year
3. Contact county assessor directly (phone number in guide)

**Q: Which source should I trust most?**
A: Ranking:
1. County Assessor (official public record - always right)
2. Apartments.com (official property listing - high confidence)
3. Google Maps/Zillow (aggregated data - very likely correct)
4. Google Search (web results - needs confirmation)

**Q: What if different sources show different addresses?**
A: Use County Assessor as tie-breaker. It's the authoritative source.

**Q: Do I need the ZIP code?**
A: Yes. Complete address = Street + City + State + ZIP

**Q: How do I know I have the right property?**
A: Cross-reference:
1. Property name matches (within reason)
2. City matches (Sarasota property = Sarasota city)
3. County matches (Duval County property = Jacksonville/Duval area)
4. Address is in Florida

---

## You're Ready!

**Next steps:**
1. Download: fl_property_lookup.html
2. Open in browser
3. Click Google Maps for first property
4. Follow sample format above
5. Record address + source in CSV
6. Repeat for all 33 properties
7. Import to database when complete

**Expected outcome:** 100% coverage, confidence=1.0, full audit trail

Good luck! 🏠
