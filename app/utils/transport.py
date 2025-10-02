from app.common.dbConnect import db
from app.common.html_utils import extract_headings, extract_list_items
from app.common.scrapper import scrape_webpage

from app.utils.db_save import save_scrape


async def transport_data():
    url = "https://www.srilanka.travel/transport"

    existing = db["scrape"].find_one({"page": "transport"})
    if existing:
        existing["id"] = str(existing.pop("_id"))  # convert ObjectId to string
        return existing

    soup = scrape_webpage(url)

    content_div = soup.find("div", class_="content-inner")
    
    if not content_div:
        return {"error": "Could not find content-inner section."}

    headings = extract_headings(content_div)

    list_items = extract_list_items(content_div)

    section_html = content_div.decode_contents()
    section_html = section_html.replace("https://www.busbooking.lk/", "https://busseat.lk/")
    section_html = section_html.replace("https://sltb.express.lk/", "https://sltb.eseat.lk/")

    data = {
        "url": url,
        "page": "transport",
        "section_title": "Transport Information",
        "tags": headings,
        "lists": list_items,
        "content": section_html
    }
    insert_result = save_scrape(data.copy())
    print("Insert result:", insert_result, type(insert_result))

    if not soup:
        return {"error": "Failed to fetch or parse the page."}

    # Return the HTML content as a string
    return data