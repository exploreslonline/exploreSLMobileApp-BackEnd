
from app.common.dbConnect import db


def save_scrape(data: any):
    if not data or "error" in data:
        print("No valid data to save.")
        return None

    collection = db["scrape"]
    result = collection.insert_one(data)
    print(f"Visa data saved to 'scrape' collection with ID: {result.inserted_id}")
    return {
        "message": "Data saved successfully",
        "id": str(result.inserted_id)
    }
