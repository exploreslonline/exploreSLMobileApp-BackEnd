from app.common.dbConnect import db
from app.common.scrapper import scrape_webpage
from app.common.html_utils import extract_headings, extract_list_items

from app.utils.db_save import save_scrape # type: ignore

async def get_visa_data(title="General Information"):
    url = "https://www.immigration.gov.lk/pages_e.php?id=14"

    existing = db["scrape"].find_one({"page": "visa", "section_title": title})
    if existing:
        existing["id"] = str(existing.pop("_id"))  # convert ObjectId to string
        return existing
    
    soup = scrape_webpage(url)
    if not soup:
        return {"error": "Failed to fetch or parse the page."}

    # Extract all headings (h1-h6)
    headings = extract_headings(soup)

    # Extract all list items
    list_items = extract_list_items(soup)

    # Extract specific visa content section based on title (e.g., "General Information")
    section_html = None
    inner_divs = soup.find_all('div', class_='inner')
    for div in inner_divs:
        h4 = div.find('h4', string=lambda t: t and title in t)
        if h4:
            section_html = div.decode_contents()
            break
    
    
    data = {
        "url": url,
        "page": "visa",
        "section_title": title,
        "tags": headings,
        "lists": list_items,
        "content": section_html or f"Section '{title}' not found."
    }

    insert_result = save_scrape(data.copy())
    print("Insert result:", insert_result, type(insert_result))
    return data

