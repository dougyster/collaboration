"""
Tests for the routes component of the collaboration system.
"""
import unittest
from unittest.mock import MagicMock, patch
import json
import uuid
from datetime import datetime
from flask import session

from backend.controller.routes import app
from backend.distributed.gateway import DistributedGateway
from backend.database.db_interface import DatabaseInterface, User, Document

class TestRoutes(unittest.TestCase):
    """Test cases for the Flask routes."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Configure Flask app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = app.test_client()
        
        # Create a mock distributed gateway
        self.distributed_gateway = MagicMock(spec=DistributedGateway)
        
        # Create a mock database interface
        self.db_interface = MagicMock(spec=DatabaseInterface)
        
        # Create patches
        self.gateway_patch = patch('backend.controller.routes.distributed_gateway', self.distributed_gateway)
        self.db_patch = patch('backend.controller.routes.db_interface', self.db_interface)
        
        # Start patches
        self.mock_gateway = self.gateway_patch.start()
        self.mock_db = self.db_patch.start()
        
        # Set up common test data
        self.test_username = "testuser"
        self.test_password = "testpassword"
        self.test_document_id = str(uuid.uuid4())
        self.test_title = "Test Document"
        self.test_content = "Test content"
        
        # Create a test user
        self.test_user = User(
            username=self.test_username,
            password=self.test_password,
            documents=[self.test_document_id]
        )
        
        # Create a test document
        self.test_document = Document(
            id=self.test_document_id,
            title=self.test_title,
            data=self.test_content,
            last_edited=datetime.now(),
            users=[self.test_username]
        )
    
    def tearDown(self):
        """Clean up after each test method."""
        # Stop patches
        self.gateway_patch.stop()
        self.db_patch.stop()
    
    def test_register(self):
        """Test user registration route."""
        # Configure the mock
        self.distributed_gateway.register_user.return_value = (True, "User registered successfully.")
        
        # Make the request
        response = self.client.post(
            '/api/register',
            json={'username': self.test_username, 'password': self.test_password}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "User registered successfully.")
        self.distributed_gateway.register_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_register_failure(self):
        """Test user registration route with failure."""
        # Configure the mock
        self.distributed_gateway.register_user.return_value = (False, "Username already exists.")
        
        # Make the request
        response = self.client.post(
            '/api/register',
            json={'username': self.test_username, 'password': self.test_password}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 400)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], "Username already exists.")
        self.distributed_gateway.register_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_login(self):
        """Test user login route."""
        # Configure the mock
        self.distributed_gateway.authenticate_user.return_value = (True, "Authentication successful.")
        
        # Make the request
        response = self.client.post(
            '/api/login',
            json={'username': self.test_username, 'password': self.test_password}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "Authentication successful.")
        self.distributed_gateway.authenticate_user.assert_called_once_with(self.test_username, self.test_password)
        
        # Check that the session was set
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['username'], self.test_username)
    
    def test_login_failure(self):
        """Test user login route with failure."""
        # Configure the mock
        self.distributed_gateway.authenticate_user.return_value = (False, "Invalid password.")
        
        # Make the request
        response = self.client.post(
            '/api/login',
            json={'username': self.test_username, 'password': 'wrong_password'}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 401)
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], "Invalid password.")
        self.distributed_gateway.authenticate_user.assert_called_once_with(self.test_username, 'wrong_password')
    
    def test_logout(self):
        """Test user logout route."""
        # Set up a session
        with self.client.session_transaction() as sess:
            sess['username'] = self.test_username
        
        # Make the request
        response = self.client.post('/api/logout')
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "Logged out successfully.")
        
        # Check that the session was cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn('username', sess)
    
    def test_get_documents(self):
        """Test get documents route."""
        # Configure the mock
        self.distributed_gateway.get_user_documents.return_value = (
            True, "Documents retrieved successfully.", [self.test_document]
        )
        
        # Set up a session
        with self.client.session_transaction() as sess:
            sess['username'] = self.test_username
        
        # Make the request
        response = self.client.get('/api/documents')
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['documents']), 1)
        self.assertEqual(data['documents'][0]['id'], self.test_document_id)
        self.assertEqual(data['documents'][0]['title'], self.test_title)
        self.distributed_gateway.get_user_documents.assert_called_once_with(self.test_username)
    
    def test_get_documents_with_query_param(self):
        """Test get documents route with username in query parameter."""
        # Configure the mock
        self.distributed_gateway.get_user_documents.return_value = (
            True, "Documents retrieved successfully.", [self.test_document]
        )
        
        # Make the request with username in query parameter
        response = self.client.get(f'/api/documents?username={self.test_username}')
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['documents']), 1)
        self.assertEqual(data['documents'][0]['id'], self.test_document_id)
        self.assertEqual(data['documents'][0]['title'], self.test_title)
        self.distributed_gateway.get_user_documents.assert_called_once_with(self.test_username)
    
    def test_create_document(self):
        """Test create document route."""
        # Configure the mock
        self.distributed_gateway.create_document.return_value = (
            True, "Document created successfully.", self.test_document_id
        )
        
        # Set up a session
        with self.client.session_transaction() as sess:
            sess['username'] = self.test_username
        
        # Make the request
        response = self.client.post(
            '/api/documents',
            json={'title': self.test_title}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "Document created successfully.")
        self.assertEqual(data['document_id'], self.test_document_id)
        self.distributed_gateway.create_document.assert_called_once_with(self.test_title, self.test_username)
    
    def test_create_document_with_username_in_body(self):
        """Test create document route with username in request body."""
        # Configure the mock
        self.distributed_gateway.create_document.return_value = (
            True, "Document created successfully.", self.test_document_id
        )
        
        # Make the request with username in body
        response = self.client.post(
            '/api/documents',
            json={'title': self.test_title, 'username': self.test_username}
        )
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 201)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], "Document created successfully.")
        self.assertEqual(data['document_id'], self.test_document_id)
        self.distributed_gateway.create_document.assert_called_once_with(self.test_title, self.test_username)
    
    def test_get_document(self):
        """Test get document route."""
        # Configure the mock
        self.distributed_gateway.get_document.return_value = (
            True, "Document retrieved successfully.", self.test_document
        )
        
        # Set up a session
        with self.client.session_transaction() as sess:
            sess['username'] = self.test_username
        
        # Make the request
        response = self.client.get(f'/api/documents/{self.test_document_id}')
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['document']['id'], self.test_document_id)
        self.assertEqual(data['document']['title'], self.test_title)
        self.assertEqual(data['document']['data'], self.test_content)
        self.distributed_gateway.get_document.assert_called_once_with(self.test_document_id, self.test_username)
    
    def test_get_document_with_query_param(self):
        """Test get document route with username in query parameter."""
        # Configure the mock
        self.distributed_gateway.get_document.return_value = (
            True, "Document retrieved successfully.", self.test_document
        )
        
        # Make the request with username in query parameter
        response = self.client.get(f'/api/documents/{self.test_document_id}?username={self.test_username}')
        
        # Parse the response
        data = json.loads(response.data)
        
        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['document']['id'], self.test_document_id)
        self.assertEqual(data['document']['title'], self.test_title)
        self.assertEqual(data['document']['data'], self.test_content)
        self.distributed_gateway.get_document.assert_called_once_with(self.test_document_id, self.test_username)

if __name__ == '__main__':
    unittest.main()
