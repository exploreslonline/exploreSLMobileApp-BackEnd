# app/common/dbConnect.py
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI')
DB_NAME = os.getenv('DB_NAME', 'customerfeedback')  # Default database name

if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is required")

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # Test the connection
    client.admin.command('ping')
    print(f"✅ Connected to MongoDB database: {DB_NAME}")
    
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    raise e

# Export collections
offers_collection = db.offers
businesses_collection = db.businesses
users_collection = db.users