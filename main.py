from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Import your existing utilities
from app.common.dbConnect import db
from app.utils.broadband import broadband_data
from app.utils.cost_of_living import cost_of_living
from app.utils.historical_places import historical_places_data
from app.utils.search import search_keyword
from app.utils.top_beaches import top_beaches_data
from app.utils.visa import get_visa_data
from app.utils.transport import transport_data
from app.utils.top_places import top_places_data

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Sri Lanka Tours Mobile API",
    description="Mobile API for Sri Lanka Tours application",
    version="1.0.0"
)

# Allow mobile frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection for offers (separate from your existing db connection)
try:
    mongo_client = MongoClient(os.getenv('MONGO_URI'))
    offers_db = mongo_client[os.getenv('DB_NAME', 'customerfeedback')]
    
    # Collections for offers
    offers_collection = offers_db.offers
    businesses_collection = offers_db.businesses
    users_collection = offers_db.users
    
    print(f"✅ Connected to offers database: {offers_db.name}")
except Exception as e:
    print(f"❌ Failed to connect to offers database: {e}")
    offers_collection = None
    businesses_collection = None
    users_collection = None

def serialize_mongo_doc(doc):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if doc is None:
        return None
    
    if isinstance(doc, dict):
        # Handle ObjectId conversion
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
            del doc['_id']
        
        # Handle businessId ObjectId
        if 'businessId' in doc and isinstance(doc['businessId'], ObjectId):
            doc['businessId'] = str(doc['businessId'])
            
        # Convert datetime objects to strings
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                doc[key] = str(value)
                
    return doc

def is_offer_active(offer):
    """Check if offer is currently active based on dates and status"""
    now = datetime.now()
    
    # Must be admin approved
    if offer.get('adminStatus') != 'approved':
        return False
    
    # Must be marked as active
    if not offer.get('isActive', True):
        return False
    
    # Check start date
    start_date = offer.get('startDate')
    if start_date and isinstance(start_date, datetime) and start_date > now:
        return False
    
    # Check end date
    end_date = offer.get('endDate')
    if end_date and isinstance(end_date, datetime) and end_date < now:
        return False
    
    return True

# ------------------ ROOT ENDPOINT ------------------
@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "Sri Lanka Tours Mobile API",
        "version": "1.0.0",
        "status": "active",
        "server": "FastAPI",
        "endpoints": {
            "mobile_offers": "/api/mobile/offers",
            "offer_details": "/api/mobile/offers/{id}",
            "categories": "/api/mobile/offers/categories",
            "health_check": "/api/mobile/health",
            "test_data": "/api/mobile/test-data",
            "packages_dialog": "/api/packages/dialog",
            "packages_mobitel": "/api/packages/mobitel",
            "visa": "/api/visa",
            "transport": "/api/transport",
            "top_places": "/api/top-places",
            "historical_places": "/api/historical-places",
            "top_beaches": "/api/top-beaches",
            "living_cost": "/api/living-cost",
            "broadband": "/api/broadband"
        },
        "database_status": {
            "offers_db": "connected" if offers_collection is not None else "disconnected",
            "main_db": "connected"
        }
    }

# ------------------ MOBILE API ENDPOINTS ------------------

@app.get("/api/mobile/offers")
async def get_approved_offers(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None
):
    """Get all approved and active offers for mobile app"""
    if offers_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        print("📱 Mobile app requesting approved offers")
        
        # Build MongoDB query - ONLY approved offers
        query = {
            'adminStatus': 'approved',
            'isActive': True
        }
        
        # Add category filter
        if category:
            query['category'] = {'$regex': category, '$options': 'i'}
        
        # Add search filter
        if search:
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'discount': {'$regex': search, '$options': 'i'}},
                {'category': {'$regex': search, '$options': 'i'}}
            ]
        
        print(f"Query filters: {query}")
        
        # Calculate skip value for pagination
        skip = (page - 1) * limit
        
        # Get offers from database
        cursor = offers_collection.find(query).sort('createdAt', -1).skip(skip).limit(limit)
        offers = list(cursor)
        
        # Get total count for pagination
        total_offers = offers_collection.count_documents(query)
        
        print(f"Found {len(offers)} offers out of {total_offers} total")
        
        # Process each offer
        processed_offers = []
        for offer in offers:
            try:
                # Serialize the offer
                offer_data = serialize_mongo_doc(offer.copy())
                
                # Check if offer is currently active (considering dates)
                offer_data['isCurrentlyActive'] = is_offer_active(offer)
                
                # Add expiry warning
                end_date = offer.get('endDate')
                if end_date and isinstance(end_date, datetime):
                    days_until_expiry = (end_date - datetime.now()).days
                    offer_data['daysUntilExpiry'] = days_until_expiry
                    offer_data['isExpiringSoon'] = days_until_expiry <= 7 and days_until_expiry > 0
                
                processed_offers.append(offer_data)
                
            except Exception as e:
                print(f"Error processing offer {offer.get('_id')}: {e}")
                continue
        
        # Calculate pagination info
        has_next = (page * limit) < total_offers
        has_prev = page > 1
        total_pages = (total_offers + limit - 1) // limit  # Ceiling division
        
        response = {
            'success': True,
            'offers': processed_offers,
            'pagination': {
                'currentPage': page,
                'totalPages': total_pages,
                'totalOffers': total_offers,
                'hasNext': has_next,
                'hasPrev': has_prev,
                'limit': limit
            },
            'filters': {
                'category': category,
                'search': search
            },
            'message': f'Found {len(processed_offers)} approved offers'
        }
        
        print(f"✅ Returning {len(processed_offers)} offers to mobile app")
        return response
        
    except Exception as e:
        print(f"❌ Error fetching approved offers: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'message': 'Failed to fetch approved offers',
                'error': str(e),
                'offers': []
            }
        )

@app.get("/api/mobile/offers/{offer_id}")
async def get_offer_details(offer_id: str):
    """Get detailed information about a specific offer"""
    if offers_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        print(f"📱 Mobile app requesting offer details for: {offer_id}")
        
        # Validate ObjectId format
        try:
            obj_id = ObjectId(offer_id)
        except:
            raise HTTPException(
                status_code=400,
                detail={'success': False, 'message': 'Invalid offer ID format'}
            )
        
        # Get offer from database
        offer = offers_collection.find_one({'_id': obj_id})
        
        if not offer:
            raise HTTPException(
                status_code=404,
                detail={'success': False, 'message': 'Offer not found'}
            )
        
        # Check if offer is approved
        if offer.get('adminStatus') != 'approved':
            raise HTTPException(
                status_code=403,
                detail={'success': False, 'message': 'Offer is not available'}
            )
        
        # Serialize the offer
        offer_data = serialize_mongo_doc(offer.copy())
        
        # Add status information
        offer_data['isCurrentlyActive'] = is_offer_active(offer)
        
        # Add expiry information
        end_date = offer.get('endDate')
        if end_date and isinstance(end_date, datetime):
            days_until_expiry = (end_date - datetime.now()).days
            offer_data['daysUntilExpiry'] = days_until_expiry
            offer_data['isExpiringSoon'] = days_until_expiry <= 7 and days_until_expiry > 0
            offer_data['isExpired'] = days_until_expiry < 0
        
        print(f"✅ Returning offer details for: {offer_data.get('title')}")
        
        return {
            'success': True,
            'offer': offer_data,
            'message': 'Offer details retrieved successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching offer details: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'message': 'Failed to fetch offer details',
                'error': str(e)
            }
        )

@app.get("/api/mobile/health")
async def mobile_health_check():
    """Health check endpoint for mobile API"""
    try:
        # Test database connection
        db_status = "disconnected"
        collections_info = {}
        
        if offers_collection is not None:
            # Test the connection by running a simple query
            offers_collection.find_one()
            db_status = "connected"
            
            # Get collection counts
            collections_info = {
                'offers': offers_collection.count_documents({}),
                'businesses': businesses_collection.count_documents({}) if businesses_collection is not None else 0,
                'users': users_collection.count_documents({}) if users_collection is not None else 0
            }
        
        return {
            'success': True,
            'message': 'Mobile API is healthy',
            'timestamp': datetime.now().isoformat(),
            'database': db_status,
            'collections': collections_info,
            'mongodb_uri_configured': bool(os.getenv('MONGO_URI')),
            'db_name': os.getenv('DB_NAME', 'customerfeedback')
        }
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return {
            'success': False,
            'message': 'Mobile API health check failed',
            'error': str(e),
            'database': 'disconnected',
            'mongodb_uri_configured': bool(os.getenv('MONGO_URI')),
            'db_name': os.getenv('DB_NAME', 'customerfeedback')
        }

@app.get("/api/mobile/test-data")
async def get_test_data():
    """Test endpoint to check database contents"""
    if offers_collection is None:
        return {
            'success': False,
            'message': 'Database not connected - offers_collection is None',
            'error': 'MongoDB connection failed'
        }
    
    try:
        # Get sample data from each collection
        offers_sample = list(offers_collection.find().limit(2))
        
        # Check if businesses and users collections exist
        businesses_sample = []
        users_sample = []
        
        if businesses_collection is not None:
            businesses_sample = list(businesses_collection.find().limit(2))
        
        if users_collection is not None:
            users_sample = list(users_collection.find().limit(2))
        
        # Serialize the data
        offers_sample = [serialize_mongo_doc(offer.copy()) for offer in offers_sample]
        businesses_sample = [serialize_mongo_doc(business.copy()) for business in businesses_sample]
        users_sample = [serialize_mongo_doc(user.copy()) for user in users_sample]
        
        # Get counts
        total_offers = offers_collection.count_documents({})
        approved_offers = offers_collection.count_documents({'adminStatus': 'approved'})
        active_offers = offers_collection.count_documents({'adminStatus': 'approved', 'isActive': True})
        
        return {
            'success': True,
            'message': 'Test data retrieved',
            'data': {
                'offers': offers_sample,
                'businesses': businesses_sample, 
                'users': users_sample
            },
            'counts': {
                'total_offers': total_offers,
                'approved_offers': approved_offers,
                'active_offers': active_offers
            },
            'database_info': {
                'db_name': offers_db.name if offers_db else 'Unknown',
                'collections_available': {
                    'offers': offers_collection is not None,
                    'businesses': businesses_collection is not None,
                    'users': users_collection is not None
                }
            }
        }
        
    except Exception as e:
        print(f"❌ Error fetching test data: {e}")
        return {
            'success': False,
            'message': 'Failed to fetch test data',
            'error': str(e),
            'debug_info': {
                'offers_collection_exists': offers_collection is not None,
                'db_name': offers_db.name if offers_db else 'Unknown'
            }
        }

# ------------------ Models for existing endpoints ------------------
class Detail(BaseModel):
    description: str
    days: str
    price: int

# ------------------ Your existing endpoints ------------------
@app.post("/api/packages/dialog")
async def save_dialog_packages(details: List[Detail]):
    db.dialog.insert_many([detail.dict() for detail in details])
    return {"message": "Dialog packages saved successfully"}

@app.get("/api/packages/dialog")
async def get_dialog_packages():
    packages = list(db.dialog.find())
    for pkg in packages:
        pkg["id"] = str(pkg.pop("_id"))
    return packages

@app.put("/api/packages/dialog/{id}")
async def update_dialog_package(id: str, detail: Detail):
    result = db.dialog.update_one({"_id": ObjectId(id)}, {"$set": detail.dict()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Dialog package updated successfully"}

@app.delete("/api/packages/dialog/{id}")
async def delete_dialog_package(id: str):
    result = db.dialog.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Dialog package deleted successfully"}

@app.post("/api/packages/mobitel")
async def save_mobitel_packages(details: List[Detail]):
    db.mobitel.insert_many([detail.dict() for detail in details])
    return {"message": "Mobitel packages saved successfully"}

@app.get("/api/packages/mobitel")
async def get_mobitel_packages():
    packages = list(db.mobitel.find())
    for pkg in packages:
        pkg["id"] = str(pkg.pop("_id"))
    return packages

@app.put("/api/packages/mobitel/{id}")
async def update_mobitel_package(id: str, detail: Detail):
    result = db.mobitel.update_one({"_id": ObjectId(id)}, {"$set": detail.dict()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Mobitel package updated successfully"}

@app.delete("/api/packages/mobitel/{id}")
async def delete_mobitel_package(id: str):
    result = db.mobitel.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Mobitel package deleted successfully"}

@app.get("/api/visa")
async def scrape():
    result = await get_visa_data()
    return result

@app.get("/search")
async def search(q: str):
    result = await search_keyword(q)
    if not result:
        return {"message": "No results found"}
    return result

@app.get("/api/transport")
async def transport():
    result = await transport_data()
    if not result:
        return {"message": "No results found"}
    return result

@app.get("/api/top-places")
async def top_places():
    result = await top_places_data()
    if not result:
        return {"message": "No results found"}
    return result

@app.get("/api/historical-places")
async def historical_places():
   result = await historical_places_data()
   if not result:
       return {"message": "No results found"}
   return result

@app.get("/api/top-beaches")
async def top_beaches():
    result = await top_beaches_data()
    if not result:
        return {"message": "No results found"}
    return result

@app.get("/api/living-cost")
async def living_cost():
    result = await cost_of_living()
    if not result:
        return {"message": "No results found"}
    return result

@app.get("/api/broadband")
async def broadband():
    result = await broadband_data()
    if not result:
        return {"message": "No results found"}
    return result