"""
Controller for the collaboration system.
Defines Flask routes to handle API requests.
"""
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import json
from datetime import datetime

from backend.interactor.business_logic import BusinessLogic
from backend.database.db_interface import DatabaseInterface, User, Document
from backend.distributed.gateway import DistributedGateway

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')  # For session management

# Configure CORS to allow requests from any origin with credentials
CORS(app, 
     supports_credentials=True,
     origins=["*"],  # Allow all origins
     allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
     expose_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# Initialize distributed gateway
default_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'data.json')
db_path = os.environ.get('DB_PATH', default_db_path)
server_id = os.environ.get('SERVER_ID')
if not server_id:
    raise ValueError("SERVER_ID environment variable must be set")
    
port = int(os.environ.get('GRPC_PORT', '50051'))
peer_addresses = os.environ.get('PEER_ADDRESSES', '').split(',') if os.environ.get('PEER_ADDRESSES') else []

print(f"Initializing distributed gateway with server_id={server_id}, port={port}, db_path={db_path}")
distributed_gateway = DistributedGateway(server_id, port, peer_addresses, db_path)

# For backward compatibility and direct database access
db_interface = distributed_gateway.server.db_interface

# User routes
@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all users except the current user."""
    # First try to get username from query parameter
    username = request.args.get('username')
    
    # If not provided in query, fall back to session
    if not username:
        username = session.get('username')
        
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in or username not provided.'}), 401
    
    # Get all users from the database
    db = db_interface._read_db()
    users = []
    
    for user_name, user_data in db["users"].items():
        if user_name != username:  # Exclude the current user
            users.append({
                'username': user_name
            })
    
    return jsonify({
        'success': True,
        'users': users
    }), 200

# Authentication routes
@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    success, message = distributed_gateway.register_user(username, password)
    
    if success:
        return jsonify({'success': True, 'message': message}), 201
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/login', methods=['POST'])
def login():
    """Login a user."""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    success, message = distributed_gateway.authenticate_user(username, password)
    
    if success:
        session['username'] = username
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout a user."""
    session.pop('username', None)
    return jsonify({'success': True, 'message': 'Logged out successfully.'}), 200

@app.route('/api/user', methods=['GET'])
def get_user():
    """Get the current user."""
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    user = db_interface.get_user(username)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'}), 404
    
    return jsonify({
        'success': True,
        'user': {
            'username': user.username,
            'documents': user.documents
        }
    }), 200

# Document routes
@app.route('/api/documents', methods=['GET'])
def get_documents():
    """Get all documents for the current user."""
    # First try to get username from query parameter
    username = request.args.get('username')
    
    # If not provided in query, fall back to session
    if not username:
        username = session.get('username')
        
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in or username not provided.'}), 401
    
    success, message, documents = distributed_gateway.get_user_documents(username)
    
    if success:
        return jsonify({
            'success': True,
            'documents': [
                {
                    'id': doc.id,
                    'title': doc.title,
                    'last_edited': doc.last_edited.isoformat(),
                    'users': doc.users
                } for doc in documents
            ]
        }), 200
    else:
        return jsonify({'success': False, 'message': message}), 404

@app.route('/api/documents', methods=['POST'])
def create_document():
    """Create a new document."""
    data = request.json
    
    # First try to get username from request body
    username = data.get('username')
    
    # If not provided in body, fall back to session
    if not username:
        username = session.get('username')
        
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in or username not provided.'}), 401
    
    title = data.get('title', 'Untitled Document')
    
    success, message, document_id = distributed_gateway.create_document(title, username)
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'document_id': document_id
        }), 201
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>', methods=['GET'])
def get_document(document_id):
    """Get a document by ID."""
    # First try to get username from query parameter
    username = request.args.get('username')
    
    # If not provided in query, fall back to session
    if not username:
        username = session.get('username')
        
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in or username not provided.'}), 401
    
    success, message, document = distributed_gateway.get_document(document_id, username)
    
    if success:
        return jsonify({
            'success': True,
            'document': {
                'id': document.id,
                'title': document.title,
                'data': document.data,
                'last_edited': document.last_edited.isoformat(),
                'users': document.users
            }
        }), 200
    else:
        return jsonify({'success': False, 'message': message}), 404

@app.route('/api/documents/<document_id>/title', methods=['PUT'])
def update_document_title(document_id):
    """Update a document's title."""
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    data = request.json
    title = data.get('title')
    
    success, message = distributed_gateway.update_document_title(document_id, title, username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>/content', methods=['PUT'])
def update_document_content(document_id):
    """Update a document's content."""
    data = request.json
    
    # First try to get username from request body
    username = data.get('username')
    
    # If not provided in body, fall back to session
    if not username:
        username = session.get('username')
        
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in or username not provided.'}), 401
    
    content = data.get('content')
    base_content = data.get('base_content')
    
    # If base_content is provided, use merge strategy
    if base_content is not None:
        success, message, updated_content = distributed_gateway.update_document_content(
            document_id, content, username, base_content
        )
    else:
        # Otherwise use simple last-write-wins
        success, message, updated_content = distributed_gateway.update_document_content(
            document_id, content, username
        )
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'content': updated_content
        }), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>', methods=['DELETE'])
def delete_document(document_id):
    """Delete a document."""
    # Get username from query parameters - explicit username passing
    username = request.args.get('username')
    
    # Require explicit username in the request
    if not username:
        app.logger.error(f"Document deletion failed: No username provided in request")
        return jsonify({'success': False, 'message': 'Username must be explicitly provided in the request.'}), 401
    
    app.logger.info(f"User '{username}' attempting to delete document '{document_id}'")
    success, message = distributed_gateway.delete_document(document_id, username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>/users', methods=['POST'])
def add_user_to_document(document_id):
    """Add a user to a document."""
    data = request.json
    
    # ONLY use explicit username from request body - no session fallback
    owner_username = data.get('owner_username')  # The user who owns/is sharing the document
    
    # Require explicit owner_username in the request
    if not owner_username:
        app.logger.error(f"Document sharing failed: No owner_username provided in request")
        return jsonify({
            'success': False, 
            'message': 'Owner username must be explicitly provided in the request.'
        }), 401
    
    # Get the username of the user to add
    user_to_add = data.get('username')
    
    if not user_to_add:
        app.logger.error(f"Document sharing failed: No username to add provided in request")
        return jsonify({'success': False, 'message': 'No user specified to add to document.'}), 400
    
    # Log the sharing attempt for debugging
    app.logger.info(f"User '{owner_username}' attempting to share document '{document_id}' with user '{user_to_add}'")
    
    success, message = distributed_gateway.add_user_to_document(document_id, user_to_add, owner_username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>/users/<username_to_remove>', methods=['DELETE'])
def remove_user_from_document(document_id, username_to_remove):
    """Remove a user from a document."""
    # Get owner username from query parameters - explicit username passing
    owner_username = request.args.get('owner_username')
    
    # Require explicit owner_username in the request
    if not owner_username:
        app.logger.error(f"Document user removal failed: No owner_username provided in request")
        return jsonify({
            'success': False, 
            'message': 'Owner username must be explicitly provided in the request.'
        }), 401
    
    app.logger.info(f"User '{owner_username}' attempting to remove user '{username_to_remove}' from document '{document_id}'")
    
    success, message = distributed_gateway.remove_user_from_document(document_id, username_to_remove, owner_username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

# Server status routes
@app.route('/api/server/status', methods=['GET'])
def get_server_status():
    """Get the status of the distributed server."""
    status = distributed_gateway.get_server_status()
    return jsonify({
        'success': True,
        'status': status
    }), 200

@app.route('/api/cluster/status', methods=['GET'])
def get_cluster_status():
    """Get the status of the distributed cluster."""
    status = distributed_gateway.get_cluster_status()
    return jsonify({
        'success': True,
        'status': status
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
