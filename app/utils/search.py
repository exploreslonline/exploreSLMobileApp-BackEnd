from fastapi import FastAPI, Query
from pymongo import MongoClient
from typing import List
from collections import defaultdict
from app.common.dbConnect import db

async def search_keyword(q: str = Query(..., description="Search keyword")):
    regex = {"$regex": q, "$options": "i"}
    results = db.scrape.find({
        "$or": [
            {"tags": regex},
            {"lists": regex}
        ]
    }, {"page": 1, "section_title": 1, "tags": 1, "lists": 1, "_id": 0})

    # Group by page
    matches = []
    for item in results:
        page = item.get("page")
        section = item.get("section_title", "")
        # Find matching lines in tags and lists
        for field in ["tags", "lists"]:
            for line in item.get(field, []):
                if q.lower() in line.lower():
                    matches.append({
                        "page": page,
                        "section_title": section,
                        "field": field,
                        "matched_line": line
                    })

    return {"results": matches}

