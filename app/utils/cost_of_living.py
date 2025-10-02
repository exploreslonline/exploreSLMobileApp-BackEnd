from app.common.dbConnect import db
from app.common.html_utils import extract_headings, extract_list_items
from app.common.scrapper import scrape_webpage
from app.utils.db_save import save_scrape

async def cost_of_living(force_scrape=False):
    url = "https://www.numbeo.com/cost-of-living/country_result.jsp?country=Sri+Lanka&displayCurrency=USD"
    page_key = "livingCost"

    # ⚠️ Step 1: Check cache (MongoDB) first unless force_scrape
    if not force_scrape:
        cached = db["scrape"].find_one({"page": page_key})
        if cached:
            cached["id"] = str(cached.pop("_id"))
            print("📦 Returning cached data")
            return cached

    print("🌐 Scraping new data from:", url)
    
    soup = scrape_webpage(url)
    if not soup:
        return {"error": "Failed to fetch or parse the page."}

    # Step 2: Locate target table
    content = soup.find("table", class_="data_wide_table new_bar_table")
    if not content:
        return {"error": "Could not find the expected content section."}

    # Step 3: Cleanup unnecessary elements
    for tag in content.find_all(["i", "svg", "img"]):
        tag.decompose()

    for a in content.find_all("a"):
        if "edit" in a.get("class", []) or "edit" in a.get_text(strip=True).lower():
            a.decompose()

    for row in content.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if cells:
            cells[-1].decompose()  # Remove last column

    # Step 4: Extract useful structured data
    headings = extract_headings(content)
    list_items = extract_list_items(content)
    section_html = content.decode_contents()

    data = {
        "url": url,
        "page": page_key,
        "section_title": "Cost of living Sri Lanka",
        "tags": headings,
        "lists": list_items,
        "content": section_html
    }

    # Step 5: Store or replace in DB
    db["scrape"].replace_one({"page": page_key}, data, upsert=True)
    print("✅ Data scraped and saved to MongoDB.")

    return data
