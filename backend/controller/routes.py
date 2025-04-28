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
CORS(app, supports_credentials=True)  # Enable CORS for cross-origin requests

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
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    success, message = distributed_gateway.delete_document(document_id, username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>/users', methods=['POST'])
def add_user_to_document(document_id):
    """Add a user to a document."""
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    data = request.json
    user_to_add = data.get('username')
    
    success, message = distributed_gateway.add_user_to_document(document_id, user_to_add, username)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/documents/<document_id>/users/<username_to_remove>', methods=['DELETE'])
def remove_user_from_document(document_id, username_to_remove):
    """Remove a user from a document."""
    username = session.get('username')
    if not username:
        return jsonify({'success': False, 'message': 'Not logged in.'}), 401
    
    success, message = distributed_gateway.remove_user_from_document(document_id, username_to_remove, username)
    
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
