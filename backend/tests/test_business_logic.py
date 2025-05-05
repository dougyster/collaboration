"""
Tests for the business logic component of the collaboration system.
"""
import unittest
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime

from backend.interactor.business_logic import BusinessLogic
from backend.database.db_interface import DatabaseInterface, User, Document

class TestBusinessLogic(unittest.TestCase):
    """Test cases for the BusinessLogic class."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a mock database interface
        self.db_interface = MagicMock(spec=DatabaseInterface)
        
        # Create the business logic with the mock database
        self.business_logic = BusinessLogic(self.db_interface)
        
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

    def test_register_user_success(self):
        """Test successful user registration."""
        # Configure the mock
        self.db_interface.get_user.return_value = None  # User doesn't exist yet
        self.db_interface.create_user.return_value = True  # User creation succeeds
        
        # Call the method
        success, message = self.business_logic.register_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "User registered successfully.")
        self.db_interface.get_user.assert_called_once_with(self.test_username)
        self.db_interface.create_user.assert_called_once()

    def test_register_user_already_exists(self):
        """Test user registration when the username already exists."""
        # Configure the mock
        self.db_interface.get_user.return_value = self.test_user  # User already exists
        
        # Call the method
        success, message = self.business_logic.register_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "Username already exists.")
        self.db_interface.get_user.assert_called_once_with(self.test_username)
        self.db_interface.create_user.assert_not_called()

    def test_authenticate_user_success(self):
        """Test successful user authentication."""
        # Configure the mock
        self.db_interface.get_user.return_value = self.test_user
        
        # Call the method
        success, message = self.business_logic.authenticate_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Authentication successful.")
        self.db_interface.get_user.assert_called_once_with(self.test_username)

    def test_authenticate_user_invalid_password(self):
        """Test user authentication with invalid password."""
        # Configure the mock
        self.db_interface.get_user.return_value = self.test_user
        
        # Call the method
        success, message = self.business_logic.authenticate_user(self.test_username, "wrongpassword")
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "Invalid password.")
        self.db_interface.get_user.assert_called_once_with(self.test_username)

    def test_authenticate_user_not_found(self):
        """Test user authentication when user doesn't exist."""
        # Configure the mock
        self.db_interface.get_user.return_value = None
        
        # Call the method
        success, message = self.business_logic.authenticate_user(self.test_username, self.test_password)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "User not found.")
        self.db_interface.get_user.assert_called_once_with(self.test_username)

    def test_create_document_success(self):
        """Test successful document creation."""
        # Configure the mock
        self.db_interface.get_user.return_value = self.test_user
        self.db_interface.create_document.return_value = True
        self.db_interface.update_user.return_value = True
        
        # Mock uuid4 to return a predictable value
        with patch('uuid.uuid4', return_value=uuid.UUID(self.test_document_id)):
            # Call the method
            success, message, document_id = self.business_logic.create_document(self.test_title, self.test_username)
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Document created successfully.")
        self.assertEqual(document_id, self.test_document_id)
        self.db_interface.get_user.assert_called_once_with(self.test_username)
        self.db_interface.create_document.assert_called_once()
        self.db_interface.update_user.assert_called_once()

    def test_create_document_user_not_found(self):
        """Test document creation when user doesn't exist."""
        # Configure the mock
        self.db_interface.get_user.return_value = None
        
        # Call the method
        success, message, document_id = self.business_logic.create_document(self.test_title, self.test_username)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "User not found.")
        self.assertIsNone(document_id)
        self.db_interface.get_user.assert_called_once_with(self.test_username)
        self.db_interface.create_document.assert_not_called()

    def test_get_document_success(self):
        """Test successful document retrieval."""
        # Configure the mock
        self.db_interface.get_document.return_value = self.test_document
        
        # Call the method
        success, message, document = self.business_logic.get_document(self.test_document_id, self.test_username)
        
        # Assertions
        self.assertTrue(success)
        self.assertEqual(message, "Document retrieved successfully.")
        self.assertEqual(document, self.test_document)
        self.db_interface.get_document.assert_called_once_with(self.test_document_id)

    def test_get_document_not_found(self):
        """Test document retrieval when document doesn't exist."""
        # Configure the mock
        self.db_interface.get_document.return_value = None
        
        # Call the method
        success, message, document = self.business_logic.get_document(self.test_document_id, self.test_username)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "Document not found.")
        self.assertIsNone(document)
        self.db_interface.get_document.assert_called_once_with(self.test_document_id)

    def test_get_document_no_access(self):
        """Test document retrieval when user doesn't have access."""
        # Create a document that the test user doesn't have access to
        document = Document(
            id=self.test_document_id,
            title=self.test_title,
            data="Test content",
            last_edited=datetime.now(),
            users=["otheruser"]  # Different user
        )
        
        # Configure the mock
        self.db_interface.get_document.return_value = document
        
        # Call the method
        success, message, result = self.business_logic.get_document(self.test_document_id, self.test_username)
        
        # Assertions
        self.assertFalse(success)
        self.assertEqual(message, "User does not have access to this document.")
        self.assertIsNone(result)
        self.db_interface.get_document.assert_called_once_with(self.test_document_id)

if __name__ == '__main__':
    unittest.main()
