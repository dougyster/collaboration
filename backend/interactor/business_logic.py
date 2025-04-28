"""
Business logic for the collaboration system.
Implements the interface from the database and handles concurrent edits.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import difflib

from backend.database.db_interface import DatabaseInterface, User, Document

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BusinessLogic:
    """Business logic for the collaboration system."""
    
    def __init__(self, db_interface: DatabaseInterface):
        self.db = db_interface
        self.document_locks = {}  # Track locks for each document
    
    # User operations
    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Register a new user."""
        logger.info(f"Registering user: {username}")
        
        if not username or not password:
            return False, "Username and password are required."
        
        existing_user = self.db.get_user(username)
        if existing_user:
            return False, "Username already exists."
        
        user = User(username=username, password=password)
        success = self.db.create_user(user)
        
        if success:
            return True, "User registered successfully."
        else:
            return False, "Failed to register user."
    
    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Authenticate a user."""
        logger.info(f"Authenticating user: {username}")
        
        user = self.db.get_user(username)
        if not user:
            return False, "User not found."
        
        if user.password != password:  # In a real app, use proper password hashing
            return False, "Invalid password."
        
        return True, "Authentication successful."
    
    # Document operations
    def create_document(self, title: str, username: str) -> Tuple[bool, str, Optional[str]]:
        """Create a new document."""
        logger.info(f"Creating document '{title}' for user: {username}")
        
        user = self.db.get_user(username)
        if not user:
            return False, "User not found.", None
        
        document_id = str(uuid.uuid4())
        document = Document(
            id=document_id,
            title=title,
            data="",  # Empty document initially
            last_edited=datetime.now(),
            users=[username]
        )
        
        success = self.db.create_document(document)
        
        if success:
            # Update user's document list
            user.documents.append(document_id)
            self.db.update_user(user)
            return True, "Document created successfully.", document_id
        else:
            return False, "Failed to create document.", None
    
    def get_document(self, document_id: str, username: str) -> Tuple[bool, str, Optional[Document]]:
        """Get a document by ID."""
        logger.info(f"Getting document {document_id} for user: {username}")
        
        document = self.db.get_document(document_id)
        if not document:
            return False, "Document not found.", None
        
        if username not in document.users:
            return False, "User does not have access to this document.", None
        
        return True, "Document retrieved successfully.", document
    
    def update_document_title(self, document_id: str, title: str, username: str) -> Tuple[bool, str]:
        """Update a document's title."""
        logger.info(f"Updating title of document {document_id} to '{title}' by user: {username}")
        
        success, message, document = self.get_document(document_id, username)
        if not success:
            return False, message
        
        document.title = title
        document.last_edited = datetime.now()
        
        success = self.db.update_document(document)
        if success:
            return True, "Document title updated successfully."
        else:
            return False, "Failed to update document title."
    
    def delete_document(self, document_id: str, username: str) -> Tuple[bool, str]:
        """Delete a document."""
        logger.info(f"Deleting document {document_id} by user: {username}")
        
        success, message, document = self.get_document(document_id, username)
        if not success:
            return False, message
        
        success = self.db.delete_document(document_id)
        if success:
            return True, "Document deleted successfully."
        else:
            return False, "Failed to delete document."
    
    def get_user_documents(self, username: str) -> Tuple[bool, str, List[Document]]:
        """Get all documents for a user."""
        logger.info(f"Getting documents for user: {username}")
        
        user = self.db.get_user(username)
        if not user:
            return False, "User not found.", []
        
        documents = self.db.get_user_documents(username)
        return True, "Documents retrieved successfully.", documents
    
    def add_user_to_document(self, document_id: str, username: str, added_by: str) -> Tuple[bool, str]:
        """Add a user to a document."""
        logger.info(f"Adding user {username} to document {document_id} by user: {added_by}")
        
        # Check if the adding user has access
        success, message, document = self.get_document(document_id, added_by)
        if not success:
            return False, message
        
        # Check if the user to be added exists
        user_to_add = self.db.get_user(username)
        if not user_to_add:
            return False, "User to add not found."
        
        # Check if user is already in the document
        if username in document.users:
            return False, "User already has access to this document."
        
        # Add user to document
        document.users.append(username)
        success = self.db.update_document(document)
        
        if success:
            # Add document to user's list
            if document_id not in user_to_add.documents:
                user_to_add.documents.append(document_id)
                self.db.update_user(user_to_add)
            
            logger.info(f"Successfully shared document {document_id} with user {username}")
            return True, "User added to document successfully."
        else:
            return False, "Failed to add user to document."
    
    def remove_user_from_document(self, document_id: str, username: str, removed_by: str) -> Tuple[bool, str]:
        """Remove a user from a document."""
        logger.info(f"Removing user {username} from document {document_id} by user: {removed_by}")
        
        # Check if the removing user has access
        success, message, document = self.get_document(document_id, removed_by)
        if not success:
            return False, message
        
        # Check if the user to be removed exists and has access
        if username not in document.users:
            return False, "User does not have access to this document."
        
        # Remove user from document
        document.users.remove(username)
        success = self.db.update_document(document)
        
        if success:
            # Remove document from user's list
            user_to_remove = self.db.get_user(username)
            if user_to_remove and document_id in user_to_remove.documents:
                user_to_remove.documents.remove(document_id)
                self.db.update_user(user_to_remove)
            
            return True, "User removed from document successfully."
        else:
            return False, "Failed to remove user from document."
    
    # Document content operations with conflict resolution
    def update_document_content(self, document_id: str, content: str, username: str) -> Tuple[bool, str, Optional[str]]:
        """
        Update a document's content with simple last-write-wins conflict resolution.
        """
        logger.info(f"Updating content of document {document_id} by user: {username}")
        
        success, message, document = self.get_document(document_id, username)
        if not success:
            return False, message, None
        
        # Update document content
        document.data = content
        document.last_edited = datetime.now()
        
        success = self.db.update_document(document)
        if success:
            return True, "Document content updated successfully.", content
        else:
            return False, "Failed to update document content.", None
    
    def update_document_content_with_merge(self, document_id: str, new_content: str, base_content: str, username: str) -> Tuple[bool, str, Optional[str]]:
        """
        Update a document's content with three-way merge conflict resolution.
        This is more sophisticated than last-write-wins and tries to merge concurrent edits.
        
        Args:
            document_id: The ID of the document to update
            new_content: The new content from the client
            base_content: The base content the client was working with
            username: The username of the user making the edit
        """
        logger.info(f"Updating content of document {document_id} with merge by user: {username}")
        
        success, message, document = self.get_document(document_id, username)
        if not success:
            return False, message, None
        
        current_content = document.data
        
        # If the base content matches the current content, no conflict
        if base_content == current_content:
            document.data = new_content
            document.last_edited = datetime.now()
            success = self.db.update_document(document)
            
            if success:
                return True, "Document content updated successfully.", new_content
            else:
                return False, "Failed to update document content.", None
        
        # Otherwise, we need to merge the changes
        try:
            # Convert strings to lists of lines
            base_lines = base_content.splitlines(True)
            current_lines = current_content.splitlines(True)
            new_lines = new_content.splitlines(True)
            
            # Create a differ object
            differ = difflib.Differ()
            
            # Find differences between base and current
            diff1 = list(differ.compare(base_lines, current_lines))
            
            # Find differences between base and new
            diff2 = list(differ.compare(base_lines, new_lines))
            
            # Merge the differences
            merged_content = self._merge_diffs(base_lines, diff1, diff2)
            
            # Update the document with the merged content
            document.data = merged_content
            document.last_edited = datetime.now()
            success = self.db.update_document(document)
            
            if success:
                return True, "Document content merged successfully.", merged_content
            else:
                return False, "Failed to update document content.", None
            
        except Exception as e:
            logger.error(f"Error merging document content: {str(e)}")
            # Fallback to last-write-wins
            document.data = new_content
            document.last_edited = datetime.now()
            success = self.db.update_document(document)
            
            if success:
                return True, "Document content updated with fallback strategy.", new_content
            else:
                return False, "Failed to update document content.", None
    
    def _merge_diffs(self, base_lines, diff1, diff2) -> str:
        """
        Merge two diffs into a single content.
        This is a simplified merge algorithm and may not handle all conflict cases perfectly.
        """
        merged_lines = []
        
        # Extract changes from diff1 (base -> current)
        changes1 = {}
        for i, line in enumerate(diff1):
            if line.startswith('+ '):
                changes1[i] = line[2:]
            elif line.startswith('- '):
                changes1[i] = None  # Mark as deleted
        
        # Extract changes from diff2 (base -> new)
        changes2 = {}
        for i, line in enumerate(diff2):
            if line.startswith('+ '):
                changes2[i] = line[2:]
            elif line.startswith('- '):
                changes2[i] = None  # Mark as deleted
        
        # Apply changes from both diffs
        for i, line in enumerate(base_lines):
            if i in changes1 and i in changes2:
                # Conflict: both changed the same line
                if changes1[i] is None and changes2[i] is None:
                    # Both deleted, do nothing
                    pass
                elif changes1[i] is None:
                    # First deleted, second changed
                    merged_lines.append(changes2[i])
                elif changes2[i] is None:
                    # Second deleted, first changed
                    merged_lines.append(changes1[i])
                else:
                    # Both changed, include both with a marker
                    merged_lines.append(changes1[i])
                    merged_lines.append("<<<CONFLICT>>>\n")
                    merged_lines.append(changes2[i])
            elif i in changes1:
                # Only first changed
                if changes1[i] is not None:
                    merged_lines.append(changes1[i])
            elif i in changes2:
                # Only second changed
                if changes2[i] is not None:
                    merged_lines.append(changes2[i])
            else:
                # No changes
                merged_lines.append(line)
        
        return ''.join(merged_lines)
