"""
Gateway for the distributed server architecture.
Provides an interface between the Flask REST API and the distributed server.
"""
import os
import sys
import logging
from typing import Dict, List, Optional, Tuple, Any

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import distributed server
from backend.distributed.server import DistributedServer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DistributedGateway:
    """
    Gateway that provides an interface between the Flask REST API and the distributed server.
    """
    
    def __init__(self, server_id=None, port=50051, peer_addresses=None, db_path=None):
        """Initialize the distributed gateway."""
        self.server = DistributedServer(server_id, port, peer_addresses, db_path)
        self.server.start()
        logger.info(f"Distributed gateway initialized with server {self.server.server_id}")
    
    def stop(self):
        """Stop the distributed gateway."""
        self.server.stop()
        logger.info("Distributed gateway stopped")
    
    # User management methods
    def register_user(self, username, password):
        """Register a new user."""
        return self.server.register_user(username, password)
    
    def authenticate_user(self, username, password):
        """Authenticate a user."""
        return self.server.authenticate_user(username, password)
    
    # Document management methods
    def create_document(self, title, username):
        """Create a new document."""
        return self.server.create_document(title, username)
    
    def get_document(self, document_id, username):
        """Get a document by ID."""
        return self.server.get_document(document_id, username)
    
    def update_document_title(self, document_id, title, username):
        """Update a document's title."""
        return self.server.update_document_title(document_id, title, username)
    
    def update_document_content(self, document_id, content, username, base_content=None):
        """Update a document's content."""
        return self.server.update_document_content(document_id, content, base_content, username)
    
    def get_user_documents(self, username):
        """Get all documents for a user."""
        return self.server.get_user_documents(username)
    
    def delete_document(self, document_id, username):
        """Delete a document."""
        return self.server.delete_document(document_id, username)
    
    def add_user_to_document(self, document_id, username, added_by):
        """Add a user to a document."""
        return self.server.add_user_to_document(document_id, username, added_by)
    
    def remove_user_from_document(self, document_id, username, removed_by):
        """Remove a user from a document."""
        return self.server.remove_user_from_document(document_id, username, removed_by)
    
    # Server status methods
    def get_server_status(self):
        """Get the status of the server."""
        return {
            'server_id': self.server.server_id,
            'state': self.server.state,
            'current_term': self.server.current_term,
            'leader_id': self.server.leader_id,
            'commit_index': self.server.commit_index,
            'last_applied': self.server.last_applied,
            'log_length': len(self.server.log)
        }
    
    def get_cluster_status(self):
        """Get the status of the cluster."""
        # In a real implementation, this would query all servers in the cluster
        # For now, just return the status of this server
        return [self.get_server_status()]
