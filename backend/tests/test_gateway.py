"""
Tests for the distributed gateway component of the collaboration system.
"""
import unittest
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime

from backend.distributed.gateway import DistributedGateway
from backend.distributed.server import DistributedServer
from backend.database.db_interface import User, Document

class TestDistributedGateway(unittest.TestCase):
    """Test cases for the DistributedGateway class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock server
        self.server = MagicMock(spec=DistributedServer)
        
        # Create a patch for the DistributedServer constructor
        self.server_patch = patch('backend.distributed.gateway.DistributedServer', return_value=self.server)
        self.mock_server_constructor = self.server_patch.start()
        
        # Create the gateway with mocked server
        self.server_id = "test_server_1"
        self.port = 50051
        self.peer_addresses = ["localhost:50052", "localhost:50053"]
        self.db_path = "test_db_path"
        
        self.gateway = DistributedGateway(
            server_id=self.server_id,
            port=self.port,
            peer_addresses=self.peer_addresses,
            db_path=self.db_path
        )
        
        # Set up common test data
        self.test_username = "testuser"
        self.test_password = "testpassword"
        self.test_document_id = str(uuid.uuid4())
        self.test_title = "Test Document"
        self.test_content = "Test content"
        self.test_base_content = "Base content"
        
        # Create a test user
        self.test_user = User(
            username=self.test_username,
            password=self.test_password,
            documents=[]
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
        # Stop the patch
        self.server_patch.stop()
    
    def test_init(self):
        """Test gateway initialization."""
        # Assertions
        self.mock_server_constructor.assert_called_once_with(
            self.server_id, self.port, self.peer_addresses, self.db_path
        )
        self.server.start.assert_called_once()
    
    def test_stop(self):
        """Test gateway stop method."""
        # Call the method
        self.gateway.stop()
        
        # Assertions
        self.server.stop.assert_called_once()
    
    def test_register_user(self):
        """Test register_user method."""
        # Configure the mock
        expected_result = (True, "User registered successfully.")
        self.server.register_user.return_value = expected_result
        
        # Call the method
        result = self.gateway.register_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.register_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_authenticate_user(self):
        """Test authenticate_user method."""
        # Configure the mock
        expected_result = (True, "Authentication successful.")
        self.server.authenticate_user.return_value = expected_result
        
        # Call the method
        result = self.gateway.authenticate_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.authenticate_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_create_document(self):
        """Test create_document method."""
        # Configure the mock
        expected_result = (True, "Document created successfully.", self.test_document_id)
        self.server.create_document.return_value = expected_result
        
        # Call the method
        result = self.gateway.create_document(self.test_title, self.test_username)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.create_document.assert_called_once_with(self.test_title, self.test_username)
    
    def test_get_document(self):
        """Test get_document method."""
        # Configure the mock
        expected_result = (True, "Document retrieved successfully.", self.test_document)
        self.server.get_document.return_value = expected_result
        
        # Call the method
        result = self.gateway.get_document(self.test_document_id, self.test_username)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.get_document.assert_called_once_with(self.test_document_id, self.test_username)
    
    def test_update_document_title(self):
        """Test update_document_title method."""
        # Configure the mock
        expected_result = (True, "Document title updated successfully.")
        self.server.update_document_title.return_value = expected_result
        
        # Call the method
        result = self.gateway.update_document_title(self.test_document_id, self.test_title, self.test_username)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.update_document_title.assert_called_once_with(
            self.test_document_id, self.test_title, self.test_username
        )
    
    def test_update_document_content(self):
        """Test update_document_content method."""
        # Configure the mock
        expected_result = (True, "Document content updated successfully.")
        self.server.update_document_content.return_value = expected_result
        
        # Call the method
        result = self.gateway.update_document_content(
            self.test_document_id, self.test_content, self.test_username, self.test_base_content
        )
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.update_document_content.assert_called_once_with(
            self.test_document_id, self.test_content, self.test_base_content, self.test_username
        )
    
    def test_get_user_documents(self):
        """Test get_user_documents method."""
        # Configure the mock
        expected_result = (True, "Documents retrieved successfully.", [self.test_document])
        self.server.get_user_documents.return_value = expected_result
        
        # Call the method
        result = self.gateway.get_user_documents(self.test_username)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.get_user_documents.assert_called_once_with(self.test_username)
    
    def test_delete_document(self):
        """Test delete_document method."""
        # Configure the mock
        expected_result = (True, "Document deleted successfully.")
        self.server.delete_document.return_value = expected_result
        
        # Call the method
        result = self.gateway.delete_document(self.test_document_id, self.test_username)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.delete_document.assert_called_once_with(self.test_document_id, self.test_username)
    
    def test_add_user_to_document(self):
        """Test add_user_to_document method."""
        # Configure the mock
        expected_result = (True, "User added to document successfully.")
        self.server.add_user_to_document.return_value = expected_result
        added_by = "admin_user"
        
        # Call the method
        result = self.gateway.add_user_to_document(self.test_document_id, self.test_username, added_by)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.add_user_to_document.assert_called_once_with(
            self.test_document_id, self.test_username, added_by
        )
    
    def test_remove_user_from_document(self):
        """Test remove_user_from_document method."""
        # Configure the mock
        expected_result = (True, "User removed from document successfully.")
        self.server.remove_user_from_document.return_value = expected_result
        removed_by = "admin_user"
        
        # Call the method
        result = self.gateway.remove_user_from_document(self.test_document_id, self.test_username, removed_by)
        
        # Assertions
        self.assertEqual(result, expected_result)
        self.server.remove_user_from_document.assert_called_once_with(
            self.test_document_id, self.test_username, removed_by
        )
    
    def test_get_server_status(self):
        """Test get_server_status method."""
        # Configure the mock
        self.server.server_id = self.server_id
        self.server.state = "leader"
        self.server.current_term = 5
        self.server.leader_id = self.server_id
        self.server.commit_index = 10
        self.server.last_applied = 10
        self.server.log = [1, 2, 3, 4, 5]  # Dummy log entries
        
        # Call the method
        result = self.gateway.get_server_status()
        
        # Assertions
        expected_status = {
            'server_id': self.server_id,
            'state': "leader",
            'current_term': 5,
            'leader_id': self.server_id,
            'commit_index': 10,
            'last_applied': 10,
            'log_length': 5
        }
        self.assertEqual(result, expected_status)

if __name__ == '__main__':
    unittest.main()
