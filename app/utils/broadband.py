from app.common.dbConnect import db
from app.common.scrapper import scrape_webpage
from app.common.html_utils import extract_headings, extract_list_items
from app.utils.db_save import save_scrape

async def broadband_data(force_scrape=True):
    pages = [
        {
            "url": "https://www.dialog.lk/mobile-broadband/prepaid/plan",
            "page_key": "broadband_dialog",
            "title": "Dialog Prepaid Broadband Plans",
            "selector": {"class_": "prepaid-postpaid-container addon-hbb-mbb"}
        },
        {
            "url": "https://mobitel.lk/voice-and-data-plans#Anytime%20Data%20+%20Voice%20Plans",
            "page_key": "broadband_mobitel",
            "title": "Mobitel Broadband Plans",
            "selector": {"class_": "col-md-6 col-lg-9 inner-rightcol-main"}
        }
    ]

    results = []

    for page in pages:
        print(f"\n🔍 Scraping: {page['title']}")

        # Force re-scrape by removing old data
        if force_scrape:
            db["scrape"].delete_one({"page": page["page_key"]})
            print(f"♻️ Deleted old data for {page['page_key']}")

        # Scrape and parse
        soup = scrape_webpage(page["url"])
        if not soup:
            results.append({"error": f"❌ Failed to fetch: {page['url']}"})
            continue

        # Get only the section you want
        section = soup.find("div", **page["selector"])
        if not section:
            results.append({"error": f"❌ Selector not found: {page['selector']}"})
            continue

        # Optional: Extract only relevant content inside the section
        tags = section.find_all(["h1", "h2", "h3", "table","td","tr", "p","img"])
        section_html = "".join(str(tag) for tag in tags) if tags else section.decode_contents()

        # Build object
        data = {
            "url": page["url"],
            "page": page["page_key"],
            "section_title": page["title"],
            "tags": extract_headings(section),
            "lists": extract_list_items(section),
            "content": section_html
        }

        # Save to DB
        insert_result = save_scrape(data.copy())
        print(f"✅ Saved {page['page_key']} | Insert result: {insert_result}")
        results.append(data)

    return results
