"""
Tests for the distributed server component of the collaboration system.
"""
import unittest
from unittest.mock import MagicMock, patch
import uuid
import time
import threading
import grpc
from datetime import datetime

from backend.distributed.server import DistributedServer, FOLLOWER, CANDIDATE, LEADER
from backend.distributed import distributed_server_pb2 as ds_pb2
from backend.database.db_interface import DatabaseInterface, User, Document
from backend.interactor.business_logic import BusinessLogic

class TestDistributedServer(unittest.TestCase):
    """Test cases for the DistributedServer class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock database interface
        self.db_interface = MagicMock(spec=DatabaseInterface)
        
        # Create a mock business logic
        self.business_logic = MagicMock(spec=BusinessLogic)
        
        # Create a server ID
        self.server_id = "test_server_1"
        self.port = 50051
        self.peer_addresses = ["localhost:50052", "localhost:50053"]
        
        # Create a patch for the DatabaseInterface constructor
        self.db_patch = patch('backend.distributed.server.DatabaseInterface', return_value=self.db_interface)
        self.mock_db_constructor = self.db_patch.start()
        
        # Create a patch for the BusinessLogic constructor
        self.bl_patch = patch('backend.distributed.server.BusinessLogic', return_value=self.business_logic)
        self.mock_bl_constructor = self.bl_patch.start()
        
        # Create the server with mocked dependencies
        self.server = DistributedServer(
            server_id=self.server_id,
            port=self.port,
            peer_addresses=self.peer_addresses,
            db_path="test_db_path"
        )
        
        # Replace the server's start method to prevent actual server startup
        self.original_start = self.server.start
        self.server.start = MagicMock()
        
        # Set up common test data
        self.test_username = "testuser"
        self.test_password = "testpassword"
        self.test_document_id = str(uuid.uuid4())
        self.test_title = "Test Document"
        
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
            data="Test content",
            last_edited=datetime.now(),
            users=[self.test_username]
        )
    
    def tearDown(self):
        """Clean up after each test method."""
        # Stop the patches
        self.db_patch.stop()
        self.bl_patch.stop()
        
        # Restore the original start method
        self.server.start = self.original_start
        
        # Stop the server if it's running
        if self.server.running:
            self.server.stop()
    
    def test_init(self):
        """Test server initialization."""
        # Assertions
        self.assertEqual(self.server.server_id, self.server_id)
        self.assertEqual(self.server.port, self.port)
        self.assertEqual(self.server.peer_addresses, self.peer_addresses)
        self.assertEqual(self.server.state, FOLLOWER)
        self.assertEqual(self.server.current_term, 0)
        self.assertIsNone(self.server.voted_for)
        self.assertIsNone(self.server.leader_id)
        self.assertEqual(self.server.votes_received, 0)
        self.assertEqual(self.server.log, [])
        self.assertEqual(self.server.commit_index, -1)
        self.assertEqual(self.server.last_applied, -1)
        self.assertEqual(self.server.db_interface, self.db_interface)
        self.assertEqual(self.server.business_logic, self.business_logic)
        self.assertFalse(self.server.running)
    
    def test_register_user(self):
        """Test register_user method."""
        # Configure the mock
        expected_result = (True, "User registered successfully.")
        self.business_logic.register_user.return_value = expected_result
        
        # Call the method
        request = ds_pb2.UserRequest(username=self.test_username, password=self.test_password)
        context = MagicMock()
        
        # Execute the method
        response = self.server.RegisterUser(request, context)
        
        # Assertions
        self.assertEqual(response.success, expected_result[0])
        self.assertEqual(response.message, expected_result[1])
        self.business_logic.register_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_authenticate_user(self):
        """Test authenticate_user method."""
        # Configure the mock
        expected_result = (True, "Authentication successful.")
        self.business_logic.authenticate_user.return_value = expected_result
        
        # Call the method
        request = ds_pb2.UserRequest(username=self.test_username, password=self.test_password)
        context = MagicMock()
        
        # Execute the method
        response = self.server.AuthenticateUser(request, context)
        
        # Assertions
        self.assertEqual(response.success, expected_result[0])
        self.assertEqual(response.message, expected_result[1])
        self.business_logic.authenticate_user.assert_called_once_with(self.test_username, self.test_password)
    
    def test_create_document(self):
        """Test create_document method."""
        # Configure the mock
        expected_result = (True, "Document created successfully.", self.test_document_id)
        self.business_logic.create_document.return_value = expected_result
        
        # Call the method
        request = ds_pb2.CreateDocumentRequest(title=self.test_title, username=self.test_username)
        context = MagicMock()
        
        # Execute the method
        response = self.server.CreateDocument(request, context)
        
        # Assertions
        self.assertEqual(response.success, expected_result[0])
        self.assertEqual(response.message, expected_result[1])
        self.assertEqual(response.document_id, expected_result[2])
        self.business_logic.create_document.assert_called_once_with(self.test_title, self.test_username)
    
    def test_get_document(self):
        """Test get_document method."""
        # Configure the mock
        expected_result = (True, "Document retrieved successfully.", self.test_document)
        self.business_logic.get_document.return_value = expected_result
        
        # Call the method
        request = ds_pb2.GetDocumentRequest(document_id=self.test_document_id, username=self.test_username)
        context = MagicMock()
        
        # Execute the method
        response = self.server.GetDocument(request, context)
        
        # Assertions
        self.assertEqual(response.success, expected_result[0])
        self.assertEqual(response.message, expected_result[1])
        self.assertEqual(response.document.id, self.test_document.id)
        self.assertEqual(response.document.title, self.test_document.title)
        self.assertEqual(response.document.data, self.test_document.data)
        self.business_logic.get_document.assert_called_once_with(self.test_document_id, self.test_username)
    
    def test_append_entries_heartbeat(self):
        """Test AppendEntries RPC for heartbeat."""
        # Create a request
        request = ds_pb2.AppendEntriesRequest(
            term=1,
            leader_id="leader_server",
            prev_log_index=-1,
            prev_log_term=0,
            entries=[],  # Empty for heartbeat
            leader_commit=-1
        )
        context = MagicMock()
        
        # Execute the method
        response = self.server.AppendEntries(request, context)
        
        # Assertions
        self.assertTrue(response.success)
        self.assertEqual(response.term, 1)
        self.assertEqual(self.server.current_term, 1)
        self.assertEqual(self.server.leader_id, "leader_server")
        self.assertEqual(self.server.state, FOLLOWER)
    
    def test_request_vote(self):
        """Test RequestVote RPC."""
        # Create a request
        request = ds_pb2.RequestVoteRequest(
            term=1,
            candidate_id="candidate_server",
            last_log_index=-1,
            last_log_term=0
        )
        context = MagicMock()
        
        # Execute the method
        response = self.server.RequestVote(request, context)
        
        # Assertions
        self.assertTrue(response.vote_granted)
        self.assertEqual(response.term, 1)
        self.assertEqual(self.server.current_term, 1)
        self.assertEqual(self.server.voted_for, "candidate_server")

if __name__ == '__main__':
    unittest.main()
