from app.common.dbConnect import db
from app.common.html_utils import extract_headings, extract_list_items
from app.common.scrapper import scrape_webpage

from app.utils.db_save import save_scrape

async def top_beaches_data():
    print("Fetching top beaches data...")
    url = 'https://fromsunrisetosunset.com/best-beach-sri-lanka/'
    existing = db["scrape"].find_one({"page": "top_beaches"})
    if existing:
        existing["id"] = str(existing.pop("_id"))
        return existing
    soup = scrape_webpage(url)
    if not soup:
        return {"error": "Failed to fetch or parse the page."}
    content_div = soup.find("div", class_="elementor-column elementor-col-50 elementor-top-column elementor-element elementor-element-45564425")
    if not content_div:
        return {"error": "Could not find entry-content section."}
    headings = extract_headings(content_div)
    list_items = extract_list_items(content_div)
    section_html = content_div.decode_contents()
    data = {
        "url": url,
        "page": "top_beaches",
        "section_title": "top beaches in Sri Lanka",
        "tags": headings,
        "lists": list_items,
        "content": section_html
    }
    insert_result = save_scrape(data.copy())
    print("Insert result:", insert_result, type(insert_result))

    return data