"""
IB School Scraper — Diploma Programme (DP) Schools in the USA
=============================================================
This script scrapes the IB school finder at ibo.org to get a list of
all US schools authorized to offer the IB Diploma Programme (DP).

Output: ib_dp_schools_usa.csv

Instructions:
1. Run this script: python ib_school_scraper.py
2. It will save results to ib_dp_schools_usa.csv
3. If the IB site blocks requests, see the Alternative approach below.

Note: Be respectful — add delays between requests (already built in).
"""

import requests
import pandas as pd
import time
import json

# -----------------------------------------------------------------------
# APPROACH 1: Try the IB's internal API endpoint
# The school finder uses a search API — we try to hit it directly
# -----------------------------------------------------------------------

def scrape_via_api():
    """Try to get IB school data via their internal API."""
    
    # IB school finder API endpoint (may need to be updated if IB changes it)
    # Found by inspecting network requests on ibo.org/programmes/find-an-ib-school/
    base_url = "https://www.ibo.org/programmes/find-an-ib-school/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.ibo.org/programmes/find-an-ib-school/"
    }
    
    # Parameters to filter for USA + Diploma Programme
    params = {
        "SearchFields.CountryCode": "US",
        "SearchFields.ProgrammeCode": "DP",  # Diploma Programme
        "SearchFields.LanguageCode": "",
        "page": 1,
        "pageSize": 100
    }
    
    all_schools = []
    page = 1
    
    print("Attempting to scrape IB school data...")
    
    while True:
        params["page"] = page
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=15)
            print(f"Page {page}: Status {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed on page {page}. Status: {response.status_code}")
                break
                
            # Try to parse as JSON
            try:
                data = response.json()
                schools = data.get("schools", data.get("results", []))
                if not schools:
                    print(f"No more schools found on page {page}")
                    break
                all_schools.extend(schools)
                print(f"  Found {len(schools)} schools (total: {len(all_schools)})")
                page += 1
                time.sleep(2)  # Be respectful - wait 2 seconds between requests
                
            except json.JSONDecodeError:
                print("Response is not JSON — site may require browser interaction")
                print("Try Approach 2 below")
                break
                
        except requests.RequestException as e:
            print(f"Request error: {e}")
            break
    
    return all_schools


# -----------------------------------------------------------------------
# APPROACH 2: Manual CSV from IB's public data
# If the API doesn't work, use this pre-built list approach
# -----------------------------------------------------------------------

def get_via_public_data():
    """
    Alternative: Pull from a known public source that lists IB DP schools.
    The NCES has a 'magnet school' flag that sometimes captures IB schools.
    
    For now, this function returns instructions for manual download.
    """
    print("""
    ALTERNATIVE APPROACH:
    =====================
    If the API scraper doesn't work, try these alternatives:
    
    1. NCES Common Core of Data — search for IB in school characteristics
       URL: https://nces.ed.gov/ccd/elsi/tableGenerator.aspx
       
    2. State-by-state IB lists — many state education departments publish these
       Example: Florida DOE publishes IB school lists annually
       
    3. Contact IB directly — equity@ibo.org or info@ibo.org
       Ask for a public list of US Diploma Programme schools
       
    4. Use the IB school finder manually:
       URL: https://www.ibo.org/programmes/find-an-ib-school/
       Filter: Country = USA, Programme = DP
       Copy results to CSV manually (925 schools — manageable)
    """)


# -----------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("IB Diploma Programme School Scraper — USA")
    print("=" * 60)
    
    # Try API first
    schools = scrape_via_api()
    
    if schools:
        # Save to CSV
        df = pd.DataFrame(schools)
        output_file = "ib_dp_schools_usa.csv"
        df.to_csv(output_file, index=False)
        print(f"\nSuccess! Saved {len(df)} schools to {output_file}")
        print(f"Columns: {list(df.columns)}")
    else:
        print("\nAPI approach didn't work.")
        get_via_public_data()
        
        # Create a template CSV for manual data entry
        template = pd.DataFrame(columns=[
            "school_name",
            "address",
            "city", 
            "state",
            "zip",
            "country",
            "programme",  # DP, MYP, PYP, CP
            "school_type",  # public/private
            "ib_school_id",
            "website",
            "data_source",
            "data_year"
        ])
        template.to_csv("ib_dp_schools_usa_template.csv", index=False)
        print("\nCreated empty template: ib_dp_schools_usa_template.csv")
        print("You can fill this manually or use it as a target schema for scraping.")