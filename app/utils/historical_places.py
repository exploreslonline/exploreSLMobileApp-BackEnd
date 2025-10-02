from app.common.dbConnect import db
from app.common.html_utils import extract_headings, extract_list_items
from app.common.scrapper import scrape_webpage
from app.utils.db_save import save_scrape


async def historical_places_data():
    url = "https://sleepingelephantresort.com/blog/top-10-must-see-historical-sites-in-sri-lanka/"
    
    existing = db["scrape"].find_one({"page": "historical_places"})
    if existing:
        existing["id"] = str(existing.pop("_id"))
        return existing
    
    soup =  scrape_webpage(url)
    if not soup:
        return {"error": "Failed to fetch or parse the page."}
    content_div = soup.find("article", class_="page pdt-60 pdb-80")
    if not content_div:
        return {"error": "Could not find content-inner section."}
    
    headings = extract_headings(content_div)
    
    list_items = extract_list_items(content_div)
    
    section_html = content_div.decode_contents()
    
    data = {
        "url": url,
        "page": "historical_places",
        "section_title": "Historical Places in Sri Lanka",
        "tags": headings,
        "lists": list_items,
        "content": section_html
    }

    insert_result = save_scrape(data.copy())

    print("Insert result:", insert_result, type(insert_result))

    return data