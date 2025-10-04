from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import traceback

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

# MongoDB connection - USE THE SAME DATABASE NAME FROM .env
mongo_client = None
db_name = None
offers_collection = None
businesses_collection = None
users_collection = None
scrape_collection = None
dialog_collection = None
mobitel_collection = None

try:
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI not found in environment variables")
    
    mongo_client = MongoClient(mongo_uri)
    db_name = os.getenv('DB_NAME', 'test')
    main_db = mongo_client[db_name]
    
    # Test connection
    mongo_client.admin.command('ping')
    
    # Collections
    offers_collection = main_db.offers
    businesses_collection = main_db.businesses
    users_collection = main_db.users
    scrape_collection = main_db.scrape
    dialog_collection = main_db.dialog
    mobitel_collection = main_db.mobitel
    
    print(f"✅ Connected to database: {db_name}")
    print(f"✅ Scrape collection documents: {scrape_collection.count_documents({})}")
    
except Exception as e:
    print(f"❌ Failed to connect to database: {e}")
    traceback.print_exc()

def serialize_mongo_doc(doc):
    """Convert MongoDB ObjectId to string for JSON serialization"""
    if doc is None:
        return None
    
    if isinstance(doc, dict):
        if '_id' in doc:
            doc['id'] = str(doc['_id'])
            del doc['_id']
        
        if 'businessId' in doc and isinstance(doc['businessId'], ObjectId):
            doc['businessId'] = str(doc['businessId'])
            
        for key, value in doc.items():
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
            elif isinstance(value, ObjectId):
                doc[key] = str(value)
                
    return doc

def is_offer_active(offer):
    """Check if offer is currently active based on dates and status"""
    now = datetime.now()
    
    if offer.get('adminStatus') != 'approved':
        return False
    
    if not offer.get('isActive', True):
        return False
    
    start_date = offer.get('startDate')
    if start_date and isinstance(start_date, datetime) and start_date > now:
        return False
    
    end_date = offer.get('endDate')
    if end_date and isinstance(end_date, datetime) and end_date < now:
        return False
    
    return True

# ------------------ ROOT ENDPOINT ------------------
@app.get("/")
async def root():
    """Root endpoint - API information"""
    db_connected = scrape_collection is not None
    
    return {
        "message": "Sri Lanka Tours Mobile API",
        "version": "1.0.0",
        "status": "active",
        "server": "FastAPI",
        "endpoints": {
            # Mobile offer endpoints
            "mobile_offers": "/api/mobile/offers",
            "offer_details": "/api/mobile/offers/{id}",
            
            # Scraped data endpoints (NEW)
            "all_scraped_pages": "/api/mobile/scraped",
            "scraped_page_detail": "/api/mobile/scraped/{page_name}",
            "refresh_scrape": "/api/mobile/scraped/refresh/{page_name}",
            
            # Utility endpoints
            "health_check": "/api/mobile/health",
            "test_data": "/api/mobile/test-data",
            
            # Package endpoints
            "packages_dialog": "/api/packages/dialog",
            "packages_mobitel": "/api/packages/mobitel",
            
            # Original scraping endpoints
            "visa": "/api/visa",
            "transport": "/api/transport",
            "top_places": "/api/top-places",
            "historical_places": "/api/historical-places",
            "top_beaches": "/api/top-beaches",
            "living_cost": "/api/living-cost",
            "broadband": "/api/broadband",
            "search": "/search"
        },
        "database_status": {
            "database_name": db_name,
            "connected": db_connected
        }
    }

# ------------------ SCRAPED DATA ENDPOINTS (NEW) ------------------

@app.get("/api/mobile/scraped")
async def get_all_scraped_pages():
    """Get list of all available scraped pages"""
    if scrape_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        print("Fetching all scraped pages...")
        
        # Get all scraped pages
        scraped_pages = list(scrape_collection.find())
        
        # Serialize and return summary
        result = []
        for page in scraped_pages:
            page_data = serialize_mongo_doc(page.copy())
            result.append({
                'id': page_data.get('id'),
                'page': page_data.get('page'),
                'title': page_data.get('section_title'),
                'url': page_data.get('url'),
                'tags_count': len(page_data.get('tags', [])),
                'lists_count': len(page_data.get('lists', []))
            })
        
        return {
            'success': True,
            'pages': result,
            'total': len(result),
            'message': f'Found {len(result)} scraped pages'
        }
        
    except Exception as e:
        print(f"Error fetching scraped data: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'message': 'Failed to fetch scraped data',
                'error': str(e)
            }
        )

@app.get("/api/mobile/scraped/{page_name}")
async def get_scraped_page(page_name: str):
    """Get specific scraped page data by page name"""
    if scrape_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        print(f"Mobile app requesting scraped page: {page_name}")
        
        # Find the page in database
        page_data = scrape_collection.find_one({'page': page_name})
        
        if not page_data:
            raise HTTPException(
                status_code=404,
                detail={
                    'success': False,
                    'message': f'Page "{page_name}" not found',
                    'available_pages': ['top_beaches', 'historical_places', 'livingCost', 'visa', 'transport', 'top_places', 'broadband']
                }
            )
        
        # Serialize and return
        result = serialize_mongo_doc(page_data.copy())
        
        return {
            'success': True,
            'data': result,
            'message': f'Successfully retrieved {page_name} data'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching scraped page: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'message': f'Failed to fetch page {page_name}',
                'error': str(e)
            }
        )

@app.post("/api/mobile/scraped/refresh/{page_name}")
async def refresh_scraped_data(page_name: str):
    """Force re-scrape a specific page"""
    try:
        print(f"Force refreshing scraped data for: {page_name}")
        
        # Map page names to scraping functions
        scrape_functions = {
            'top_beaches': top_beaches_data,
            'historical_places': historical_places_data,
            'livingCost': lambda: cost_of_living(force_scrape=True),
            'visa': get_visa_data,
            'transport': transport_data,
            'top_places': top_places_data,
            'broadband': broadband_data
        }
        
        if page_name not in scrape_functions:
            raise HTTPException(
                status_code=400,
                detail={
                    'success': False,
                    'message': f'Unknown page: {page_name}',
                    'available_pages': list(scrape_functions.keys())
                }
            )
        
        # Execute scraping function
        result = await scrape_functions[page_name]()
        
        return {
            'success': True,
            'message': f'Successfully refreshed {page_name}',
            'data': result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error refreshing scraped data: {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                'success': False,
                'message': f'Failed to refresh {page_name}',
                'error': str(e)
            }
        )

# ------------------ MOBILE OFFERS ENDPOINTS ------------------

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
        print("Mobile app requesting approved offers")
        
        query = {
            'adminStatus': 'approved',
            'isActive': True
        }
        
        if category:
            query['category'] = {'$regex': category, '$options': 'i'}
        
        if search:
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'discount': {'$regex': search, '$options': 'i'}},
                {'category': {'$regex': search, '$options': 'i'}}
            ]
        
        skip = (page - 1) * limit
        cursor = offers_collection.find(query).sort('createdAt', -1).skip(skip).limit(limit)
        offers = list(cursor)
        total_offers = offers_collection.count_documents(query)
        
        processed_offers = []
        for offer in offers:
            try:
                offer_data = serialize_mongo_doc(offer.copy())
                offer_data['isCurrentlyActive'] = is_offer_active(offer)
                
                end_date = offer.get('endDate')
                if end_date and isinstance(end_date, datetime):
                    days_until_expiry = (end_date - datetime.now()).days
                    offer_data['daysUntilExpiry'] = days_until_expiry
                    offer_data['isExpiringSoon'] = days_until_expiry <= 7 and days_until_expiry > 0
                
                processed_offers.append(offer_data)
            except Exception as e:
                print(f"Error processing offer {offer.get('_id')}: {e}")
                continue
        
        has_next = (page * limit) < total_offers
        has_prev = page > 1
        total_pages = (total_offers + limit - 1) // limit
        
        return {
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
        
    except Exception as e:
        print(f"Error fetching approved offers: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mobile/offers/{offer_id}")
async def get_offer_details(offer_id: str):
    """Get detailed information about a specific offer"""
    if offers_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        try:
            obj_id = ObjectId(offer_id)
        except:
            raise HTTPException(status_code=400, detail="Invalid offer ID format")
        
        offer = offers_collection.find_one({'_id': obj_id})
        
        if not offer:
            raise HTTPException(status_code=404, detail="Offer not found")
        
        if offer.get('adminStatus') != 'approved':
            raise HTTPException(status_code=403, detail="Offer is not available")
        
        offer_data = serialize_mongo_doc(offer.copy())
        offer_data['isCurrentlyActive'] = is_offer_active(offer)
        
        end_date = offer.get('endDate')
        if end_date and isinstance(end_date, datetime):
            days_until_expiry = (end_date - datetime.now()).days
            offer_data['daysUntilExpiry'] = days_until_expiry
            offer_data['isExpiringSoon'] = days_until_expiry <= 7 and days_until_expiry > 0
            offer_data['isExpired'] = days_until_expiry < 0
        
        return {
            'success': True,
            'offer': offer_data,
            'message': 'Offer details retrieved successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching offer details: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ------------------ HEALTH & TEST ENDPOINTS ------------------

@app.get("/api/mobile/health")
async def mobile_health_check():
    """Health check endpoint for mobile API"""
    db_status = "disconnected"
    collections_info = {}
    
    try:
        # Check if collections are initialized
        if scrape_collection is None:
            db_status = "not_initialized"
        else:
            try:
                # Test the connection
                mongo_client.admin.command('ping')
                db_status = "connected"
                
                # Count documents safely
                collections_info = {
                    'offers': offers_collection.count_documents({}) if offers_collection is not None else 0,
                    'businesses': businesses_collection.count_documents({}) if businesses_collection is not None else 0,
                    'users': users_collection.count_documents({}) if users_collection is not None else 0,
                    'scrape': scrape_collection.count_documents({}) if scrape_collection is not None else 0,
                    'dialog': dialog_collection.count_documents({}) if dialog_collection is not None else 0,
                    'mobitel': mobitel_collection.count_documents({}) if mobitel_collection is not None else 0
                }
            except Exception as conn_error:
                print(f"Connection test failed: {conn_error}")
                traceback.print_exc()
                db_status = "connection_failed"
        
        return {
            'success': True,
            'message': 'Mobile API is healthy',
            'timestamp': datetime.now().isoformat(),
            'database': db_status,
            'collections': collections_info,
            'mongodb_uri_configured': bool(os.getenv('MONGO_URI')),
            'db_name': db_name if db_name else 'not_set'
        }
        
    except Exception as e:
        print(f"Health check error: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Health check encountered an error',
            'error': str(e),
            'database': db_status
        }

@app.get("/api/mobile/test-data")
async def get_test_data():
    """Test endpoint to check database contents"""
    if scrape_collection is None:
        return {
            'success': False,
            'message': 'Database not connected',
            'error': 'MongoDB connection failed'
        }
    
    try:
        offers_sample = list(offers_collection.find().limit(2)) if offers_collection is not None else []
        businesses_sample = list(businesses_collection.find().limit(2)) if businesses_collection is not None else []
        users_sample = list(users_collection.find().limit(2)) if users_collection is not None else []
        scrape_sample = list(scrape_collection.find().limit(5)) if scrape_collection is not None else []
        
        offers_sample = [serialize_mongo_doc(o.copy()) for o in offers_sample]
        businesses_sample = [serialize_mongo_doc(b.copy()) for b in businesses_sample]
        users_sample = [serialize_mongo_doc(u.copy()) for u in users_sample]
        scrape_sample = [serialize_mongo_doc(s.copy()) for s in scrape_sample]
        
        return {
            'success': True,
            'message': 'Test data retrieved',
            'data': {
                'offers': offers_sample,
                'businesses': businesses_sample,
                'users': users_sample,
                'scraped_pages': scrape_sample
            },
            'counts': {
                'total_offers': offers_collection.count_documents({}) if offers_collection is not None else 0,
                'approved_offers': offers_collection.count_documents({'adminStatus': 'approved'}) if offers_collection is not None else 0,
                'active_offers': offers_collection.count_documents({'adminStatus': 'approved', 'isActive': True}) if offers_collection is not None else 0,
                'scraped_pages': scrape_collection.count_documents({}) if scrape_collection is not None else 0
            },
            'database_info': {
                'db_name': db_name,
                'collections_available': {
                    'offers': offers_collection is not None,
                    'businesses': businesses_collection is not None,
                    'users': users_collection is not None,
                    'scrape': scrape_collection is not None
                }
            }
        }
        
    except Exception as e:
        print(f"Error in test-data: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'message': 'Failed to fetch test data',
            'error': str(e)
        }

# ------------------ PACKAGE ENDPOINTS ------------------

class Detail(BaseModel):
    description: str
    days: str
    price: int

@app.post("/api/packages/dialog")
async def save_dialog_packages(details: List[Detail]):
    if dialog_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    dialog_collection.insert_many([detail.dict() for detail in details])
    return {"message": "Dialog packages saved successfully"}

@app.get("/api/packages/dialog")
async def get_dialog_packages():
    if dialog_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    packages = list(dialog_collection.find())
    for pkg in packages:
        pkg["id"] = str(pkg.pop("_id"))
    return packages

@app.put("/api/packages/dialog/{id}")
async def update_dialog_package(id: str, detail: Detail):
    if dialog_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = dialog_collection.update_one({"_id": ObjectId(id)}, {"$set": detail.dict()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Dialog package updated successfully"}

@app.delete("/api/packages/dialog/{id}")
async def delete_dialog_package(id: str):
    if dialog_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = dialog_collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Dialog package deleted successfully"}

@app.post("/api/packages/mobitel")
async def save_mobitel_packages(details: List[Detail]):
    if mobitel_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    mobitel_collection.insert_many([detail.dict() for detail in details])
    return {"message": "Mobitel packages saved successfully"}

@app.get("/api/packages/mobitel")
async def get_mobitel_packages():
    if mobitel_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    packages = list(mobitel_collection.find())
    for pkg in packages:
        pkg["id"] = str(pkg.pop("_id"))
    return packages

@app.put("/api/packages/mobitel/{id}")
async def update_mobitel_package(id: str, detail: Detail):
    if mobitel_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = mobitel_collection.update_one({"_id": ObjectId(id)}, {"$set": detail.dict()})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Mobitel package updated successfully"}

@app.delete("/api/packages/mobitel/{id}")
async def delete_mobitel_package(id: str):
    if mobitel_collection is None:
        raise HTTPException(status_code=503, detail="Database not connected")
    result = mobitel_collection.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Package not found")
    return {"message": "Mobitel package deleted successfully"}

# ------------------ ORIGINAL SCRAPING ENDPOINTS ------------------

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