# app.py
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging

# Import the mobile routes blueprint
from routes.mobile_routes import mobile_bp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    
    # Enable CORS for all routes
    CORS(app, 
         origins=['*'],  # In production, specify your mobile app's domain
         allow_headers=['Content-Type', 'Authorization', 'Accept'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
    
    # Register blueprints
    app.register_blueprint(mobile_bp)
    
    # Root endpoint
    @app.route('/')
    def root():
        return jsonify({
            'message': 'Sri Lanka Tours Mobile API',
            'version': '1.0.0',
            'status': 'active',
            'endpoints': {
                'approved_offers': '/api/mobile/offers',
                'offer_details': '/api/mobile/offers/<id>',
                'categories': '/api/mobile/offers/categories',
                'health_check': '/api/mobile/health',
                'test_data': '/api/mobile/test-data'
            }
        })
    
    # Additional root endpoint for mobile API info
    @app.route('/api')
    def api_info():
        return jsonify({
            'api': 'Sri Lanka Tours Mobile API',
            'version': '1.0.0',
            'documentation': {
                'base_url': '/api/mobile',
                'endpoints': [
                    {
                        'path': '/offers',
                        'method': 'GET',
                        'description': 'Get all approved offers',
                        'parameters': {
                            'page': 'int (default: 1)',
                            'limit': 'int (default: 20, max: 100)',
                            'category': 'string (optional)',
                            'search': 'string (optional)'
                        }
                    },
                    {
                        'path': '/offers/<id>',
                        'method': 'GET',
                        'description': 'Get specific offer details'
                    },
                    {
                        'path': '/offers/categories',
                        'method': 'GET',
                        'description': 'Get all available categories'
                    },
                    {
                        'path': '/health',
                        'method': 'GET',
                        'description': 'Health check and database status'
                    },
                    {
                        'path': '/test-data',
                        'method': 'GET',
                        'description': 'Get sample data for testing'
                    }
                ]
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'message': 'Endpoint not found',
            'error': 'Not Found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'error': 'Internal Server Error'
        }), 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            'success': False,
            'message': 'Bad request',
            'error': 'Bad Request'
        }), 400
    
    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            'success': False,
            'message': 'Access forbidden',
            'error': 'Forbidden'
        }), 403
    
    # Handle CORS preflight requests
    @app.before_request
    def handle_preflight():
        from flask import request
        if request.method == "OPTIONS":
            response = jsonify({'status': 'OK'})
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add('Access-Control-Allow-Headers', "*")
            response.headers.add('Access-Control-Allow-Methods', "*")
            return response
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting Sri Lanka Tours Mobile API on {host}:{port}")
    
    # Run the app
    app.run(
        host=host,
        port=port,
        debug=True  # Set to False in production
    )