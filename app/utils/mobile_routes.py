# routes/mobile_routes.py
from flask import Blueprint, jsonify, request
from bson import ObjectId
from datetime import datetime, timedelta
import logging
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create blueprint
mobile_bp = Blueprint('mobile', __name__, url_prefix='/api/mobile')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
try:
    client = MongoClient(os.getenv('MONGO_URI'))
    db = client[os.getenv('DB_NAME', 'sriLanka')]
    
    # Collections
    offers_collection = db.offers
    businesses_collection = db.businesses
    users_collection = db.users
    
    logger.info(f"✅ Connected to MongoDB database: {db.name}")
except Exception as e:
    logger.error(f"❌ Failed to connect to MongoDB: {e}")
    raise

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

def get_business_details(business_id):
    """Get business details by ID"""
    try:
        if isinstance(business_id, str):
            business_id = ObjectId(business_id)
            
        business = businesses_collection.find_one({'_id': business_id})
        return serialize_mongo_doc(business) if business else None
    except Exception as e:
        logger.error(f"Error fetching business {business_id}: {e}")
        return None

def get_user_details(user_id):
    """Get user details by userId"""
    try:
        # Try to find user by userId field (number)
        user = users_collection.find_one({'userId': int(user_id)})
        if not user:
            # Fallback: try string version
            user = users_collection.find_one({'userId': str(user_id)})
            
        return serialize_mongo_doc(user) if user else None
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None

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

@mobile_bp.route('/offers', methods=['GET'])
def get_approved_offers():
    """Get all approved and active offers for mobile app"""
    try:
        logger.info("📱 Mobile app requesting approved offers")
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        category = request.args.get('category')
        search = request.args.get('search')
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if limit > 100:  # Prevent excessive requests
            limit = 100
        
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
                {'description': {'$regex': search, '$options': 'i'}},
                {'discount': {'$regex': search, '$options': 'i'}}
            ]
        
        logger.info(f"Query filters: {query}")
        
        # Calculate skip value for pagination
        skip = (page - 1) * limit
        
        # Get offers from database
        cursor = offers_collection.find(query).sort('createdAt', -1).skip(skip).limit(limit)
        offers = list(cursor)
        
        # Get total count for pagination
        total_offers = offers_collection.count_documents(query)
        
        logger.info(f"Found {len(offers)} offers out of {total_offers} total")
        
        # Process each offer
        processed_offers = []
        for offer in offers:
            try:
                # Serialize the offer
                offer_data = serialize_mongo_doc(offer.copy())
                
                # Get business details
                if offer_data.get('businessId'):
                    business = get_business_details(offer_data['businessId'])
                    offer_data['business'] = business
                
                # Get user details
                if offer_data.get('userId'):
                    user = get_user_details(offer_data['userId'])
                    offer_data['user'] = user
                
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
                logger.error(f"Error processing offer {offer.get('_id')}: {e}")
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
        
        logger.info(f"✅ Returning {len(processed_offers)} offers to mobile app")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"❌ Error fetching approved offers: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch approved offers',
            'error': str(e),
            'offers': []
        }), 500

@mobile_bp.route('/offers/<offer_id>', methods=['GET'])
def get_offer_details(offer_id):
    """Get detailed information about a specific offer"""
    try:
        logger.info(f"📱 Mobile app requesting offer details for: {offer_id}")
        
        # Validate ObjectId format
        try:
            obj_id = ObjectId(offer_id)
        except:
            return jsonify({
                'success': False,
                'message': 'Invalid offer ID format'
            }), 400
        
        # Get offer from database
        offer = offers_collection.find_one({'_id': obj_id})
        
        if not offer:
            return jsonify({
                'success': False,
                'message': 'Offer not found'
            }), 404
        
        # Check if offer is approved
        if offer.get('adminStatus') != 'approved':
            return jsonify({
                'success': False,
                'message': 'Offer is not available'
            }), 403
        
        # Serialize the offer
        offer_data = serialize_mongo_doc(offer.copy())
        
        # Get business details
        if offer_data.get('businessId'):
            business = get_business_details(offer_data['businessId'])
            offer_data['business'] = business
        
        # Get user details
        if offer_data.get('userId'):
            user = get_user_details(offer_data['userId'])
            offer_data['user'] = user
        
        # Add status information
        offer_data['isCurrentlyActive'] = is_offer_active(offer)
        
        # Add expiry information
        end_date = offer.get('endDate')
        if end_date and isinstance(end_date, datetime):
            days_until_expiry = (end_date - datetime.now()).days
            offer_data['daysUntilExpiry'] = days_until_expiry
            offer_data['isExpiringSoon'] = days_until_expiry <= 7 and days_until_expiry > 0
            offer_data['isExpired'] = days_until_expiry < 0
        
        logger.info(f"✅ Returning offer details for: {offer_data.get('title')}")
        
        return jsonify({
            'success': True,
            'offer': offer_data,
            'message': 'Offer details retrieved successfully'
        })
        
    except Exception as e:
        logger.error(f"❌ Error fetching offer details: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch offer details',
            'error': str(e)
        }), 500

@mobile_bp.route('/offers/categories', methods=['GET'])
def get_offer_categories():
    """Get all unique categories from approved offers"""
    try:
        logger.info("📱 Mobile app requesting offer categories")
        
        # Get unique categories from approved offers
        categories = offers_collection.distinct('category', {
            'adminStatus': 'approved',
            'isActive': True,
            'category': {'$ne': '', '$exists': True, '$ne': None}
        })
        
        # Filter out None values and sort
        categories = [cat for cat in categories if cat is not None and cat.strip()]
        categories.sort()
        
        logger.info(f"✅ Found {len(categories)} categories")
        
        return jsonify({
            'success': True,
            'categories': categories,
            'count': len(categories),
            'message': f'Found {len(categories)} categories'
        })
        
    except Exception as e:
        logger.error(f"❌ Error fetching categories: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch categories',
            'error': str(e),
            'categories': []
        }), 500

@mobile_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for mobile API"""
    try:
        # Test database connection
        offers_collection.find_one()
        
        return jsonify({
            'success': True,
            'message': 'Mobile API is healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'collections': {
                'offers': offers_collection.count_documents({}),
                'businesses': businesses_collection.count_documents({}),
                'users': users_collection.count_documents({})
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({
            'success': False,
            'message': 'Mobile API health check failed',
            'error': str(e),
            'database': 'disconnected'
        }), 500

@mobile_bp.route('/test-data', methods=['GET'])
def get_test_data():
    """Test endpoint to check database contents"""
    try:
        # Get sample data from each collection
        offers_sample = list(offers_collection.find().limit(2))
        businesses_sample = list(businesses_collection.find().limit(2))
        users_sample = list(users_collection.find().limit(2))
        
        # Serialize the data
        offers_sample = [serialize_mongo_doc(offer.copy()) for offer in offers_sample]
        businesses_sample = [serialize_mongo_doc(business.copy()) for business in businesses_sample]
        users_sample = [serialize_mongo_doc(user.copy()) for user in users_sample]
        
        return jsonify({
            'success': True,
            'message': 'Test data retrieved',
            'data': {
                'offers': offers_sample,
                'businesses': businesses_sample, 
                'users': users_sample
            },
            'counts': {
                'total_offers': offers_collection.count_documents({}),
                'approved_offers': offers_collection.count_documents({'adminStatus': 'approved'}),
                'active_offers': offers_collection.count_documents({'adminStatus': 'approved', 'isActive': True})
            }
        })
        
    except Exception as e:
        logger.error(f"❌ Error fetching test data: {e}")
        return jsonify({
            'success': False,
            'message': 'Failed to fetch test data',
            'error': str(e)
        }), 500