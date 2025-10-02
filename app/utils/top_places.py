from app.common.dbConnect import db
from app.common.html_utils import extract_headings, extract_list_items
from app.common.scrapper import scrape_webpage

from app.utils.db_save import save_scrape

async def top_places_data():
    url = 'https://traveltrails.lk/top-10-destinations-to-visit-in-sri-lanka-2024/'
    existing = db["scrape"].find_one({"page": "top_places"})
    if existing:
        existing["id"] = str(existing.pop("_id"))  # convert ObjectId to string
        return existing
    soup = scrape_webpage(url)
    if not soup:
        return {"error": "Failed to fetch or parse the page."}
    content_div = soup.find("div", class_="e-con-inner")
    if not content_div:
        return {"error": "Could not find entry-content section."}
    headings = extract_headings(content_div)
    list_items = extract_list_items(content_div)
    section_html = content_div.decode_contents()
    data = {
        "url": url,
        "page": "top_places",
        "section_title": "Top Places in Sri Lanka",
        "tags": headings,
        "lists": list_items,
        "content": section_html
    }
    insert_result = save_scrape(data.copy())
    print("Insert result:", insert_result, type(insert_result))

    return data