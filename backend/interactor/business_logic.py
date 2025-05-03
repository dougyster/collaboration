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
            
    def create_document_with_id(self, title: str, username: str, document_id: str) -> Tuple[bool, str, Optional[str]]:
        """Create a new document with a specified ID to prevent duplicate creation."""
        logger.info(f"Creating document '{title}' with ID {document_id} for user: {username}")
        
        user = self.db.get_user(username)
        if not user:
            return False, "User not found.", None
        
        # Check if document already exists
        existing_doc = self.db.get_document(document_id)
        if existing_doc:
            # Document already exists, just return success
            logger.info(f"Document {document_id} already exists, skipping creation")
            return True, "Document already exists.", document_id
        
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
            # Log the merge attempt for debugging
            logger.info(f"Attempting to merge changes for document {document_id}")
            logger.info(f"Base length: {len(base_content)}, Current length: {len(current_content)}, New length: {len(new_content)}")
            
            # Use character-level diffing instead of line-level for more precise merges
            merged_content = self._merge_changes_character_level(base_content, current_content, new_content)
            
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
        Merge two diffs into a single content using a simple operational transformation approach.
        This preserves the order and indices of changes from both users.
        """
        # Use the operational transformation approach instead of the old diff-based approach
        return self._merge_with_operational_transformation(base_lines, diff1, diff2)
    
    def _merge_with_operational_transformation(self, base_lines, diff1, diff2) -> str:
        """
        Merge changes using a simple operational transformation approach.
        This preserves both users' changes while maintaining document consistency.
        
        Args:
            base_lines: The original document content as a list of lines
            diff1: Diff between base and current server version
            diff2: Diff between base and new client version
        
        Returns:
            Merged content as a string
        """
        # Extract operations from both diffs
        ops1 = self._extract_operations(diff1)  # Server operations
        ops2 = self._extract_operations(diff2)  # Client operations
        
        # Apply operational transformation
        transformed_ops = self._transform_operations(ops1, ops2)
        
        # Apply all operations to the base document
        result_lines = base_lines.copy()
        
        # First apply server operations (ops1)
        for op in ops1:
            if op['type'] == 'insert':
                result_lines.insert(op['index'], op['content'])
            elif op['type'] == 'delete':
                if 0 <= op['index'] < len(result_lines):
                    result_lines.pop(op['index'])
            elif op['type'] == 'replace':
                if 0 <= op['index'] < len(result_lines):
                    result_lines[op['index']] = op['content']
        
        # Then apply transformed client operations
        for op in transformed_ops:
            if op['type'] == 'insert':
                if 0 <= op['index'] <= len(result_lines):
                    result_lines.insert(op['index'], op['content'])
            elif op['type'] == 'delete':
                if 0 <= op['index'] < len(result_lines):
                    result_lines.pop(op['index'])
            elif op['type'] == 'replace':
                if 0 <= op['index'] < len(result_lines):
                    result_lines[op['index']] = op['content']
        
        # Join the lines back into a single string
        return ''.join(result_lines)
    
    def _extract_operations(self, diff):
        """
        Extract operations (insert, delete, replace) from a diff.
        
        Args:
            diff: Diff generated by difflib.Differ
            
        Returns:
            List of operations, each as a dict with type, index, and content
        """
        operations = []
        line_index = 0
        
        for i, line in enumerate(diff):
            if line.startswith('  '):  # Unchanged line
                line_index += 1
            elif line.startswith('- '):  # Deleted line
                operations.append({
                    'type': 'delete',
                    'index': line_index
                })
                # Don't increment line_index for deleted lines
            elif line.startswith('+ '):  # Added line
                operations.append({
                    'type': 'insert',
                    'index': line_index,
                    'content': line[2:]
                })
                line_index += 1
            elif line.startswith('? '):  # Hint line, ignore
                continue
        
        return operations
    
    def _merge_changes_character_level(self, base_content, current_content, new_content):
        """
        Merge changes at the character level using a more robust algorithm.
        This handles concurrent edits at the same or different positions better.
        
        Args:
            base_content: The original content that both edits started from
            current_content: The current content on the server
            new_content: The new content from the client
            
        Returns:
            Merged content as a string
        """
        # Use difflib's SequenceMatcher for character-level operations
        # Get operations from base to current (server changes)
        server_matcher = difflib.SequenceMatcher(None, base_content, current_content)
        server_ops = self._get_character_operations(server_matcher)
        
        # Get operations from base to new (client changes)
        client_matcher = difflib.SequenceMatcher(None, base_content, new_content)
        client_ops = self._get_character_operations(client_matcher)
        
        # Log the operations for debugging
        logger.info(f"Server operations: {len(server_ops)}")
        logger.info(f"Client operations: {len(client_ops)}")
        
        # Apply both sets of operations to the base content
        result = list(base_content)  # Convert to list of characters for easier manipulation
        
        # Sort operations by position (descending) so that earlier operations don't affect indices of later ones
        server_ops.sort(key=lambda x: x['pos'], reverse=True)
        client_ops.sort(key=lambda x: x['pos'], reverse=True)
        
        # Apply server operations first
        for op in server_ops:
            if op['type'] == 'insert':
                result.insert(op['pos'], op['text'])
            elif op['type'] == 'delete':
                del result[op['pos']:op['pos'] + op['length']]
            elif op['type'] == 'replace':
                del result[op['pos']:op['pos'] + op['old_length']]
                result.insert(op['pos'], op['text'])
        
        # Transform client operations based on server operations
        transformed_client_ops = self._transform_character_operations(server_ops, client_ops)
        
        # Apply transformed client operations
        for op in transformed_client_ops:
            if op['type'] == 'insert':
                # Ensure we're not inserting beyond the end of the document
                pos = min(op['pos'], len(result))
                result.insert(pos, op['text'])
            elif op['type'] == 'delete':
                # Ensure we're not deleting beyond the end of the document
                if op['pos'] < len(result):
                    end_pos = min(op['pos'] + op['length'], len(result))
                    del result[op['pos']:end_pos]
            elif op['type'] == 'replace':
                # Ensure we're not replacing beyond the end of the document
                if op['pos'] < len(result):
                    end_pos = min(op['pos'] + op['old_length'], len(result))
                    del result[op['pos']:end_pos]
                    result.insert(op['pos'], op['text'])
        
        # Convert back to string
        return ''.join(result)
    
    def _get_character_operations(self, matcher):
        """
        Extract character-level operations from a SequenceMatcher.
        
        Args:
            matcher: A difflib.SequenceMatcher instance
            
        Returns:
            List of operations (insert, delete, replace)
        """
        operations = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                # Text was inserted in the second sequence
                operations.append({
                    'type': 'insert',
                    'pos': i1,  # Position in the original text
                    'text': matcher.b[j1:j2]  # Text that was inserted
                })
            elif tag == 'delete':
                # Text was deleted from the first sequence
                operations.append({
                    'type': 'delete',
                    'pos': i1,  # Position in the original text
                    'length': i2 - i1  # Length of deleted text
                })
            elif tag == 'replace':
                # Text was replaced
                operations.append({
                    'type': 'replace',
                    'pos': i1,  # Position in the original text
                    'old_length': i2 - i1,  # Length of replaced text
                    'text': matcher.b[j1:j2]  # New text
                })
            # 'equal' tag means text is the same, no operation needed
        
        return operations
    
    def _transform_character_operations(self, server_ops, client_ops):
        """
        Transform client operations against server operations for character-level edits.
        
        Args:
            server_ops: Operations from the server
            client_ops: Operations from the client to be transformed
            
        Returns:
            Transformed client operations
        """
        transformed_ops = []
        
        # Sort server operations by position (ascending) for transformation
        server_ops_sorted = sorted(server_ops, key=lambda x: x['pos'])
        
        for client_op in client_ops:
            # Create a copy of the client operation to transform
            transformed_op = client_op.copy()
            
            # Apply transformations based on server operations
            for server_op in server_ops_sorted:
                if server_op['type'] == 'insert':
                    # Server inserted text before or at client's position, shift client position
                    if server_op['pos'] <= transformed_op['pos']:
                        transformed_op['pos'] += len(server_op['text'])
                
                elif server_op['type'] == 'delete':
                    server_end = server_op['pos'] + server_op['length']
                    
                    if transformed_op['type'] == 'insert':
                        # Client is inserting
                        if server_op['pos'] < transformed_op['pos']:
                            # Server deleted text before client's position
                            if server_end <= transformed_op['pos']:
                                # Deletion entirely before insertion point
                                transformed_op['pos'] -= server_op['length']
                            else:
                                # Deletion overlaps insertion point
                                transformed_op['pos'] = server_op['pos']
                    
                    elif transformed_op['type'] in ['delete', 'replace']:
                        # Client is deleting or replacing
                        client_end = transformed_op['pos'] + transformed_op.get('length', transformed_op.get('old_length', 0))
                        
                        # Check for overlap
                        if server_end <= transformed_op['pos']:
                            # Server deletion before client operation
                            transformed_op['pos'] -= server_op['length']
                        elif server_op['pos'] >= client_end:
                            # Server deletion after client operation
                            pass  # No change needed
                        else:
                            # Overlapping deletions/replacements - complex case
                            # For simplicity, we'll prioritize the client operation but adjust its position
                            if server_op['pos'] <= transformed_op['pos']:
                                # Adjust position if server deletion starts before client operation
                                transformed_op['pos'] = server_op['pos']
                            
                            # Adjust length for delete operations
                            if transformed_op['type'] == 'delete':
                                overlap = min(client_end, server_end) - max(transformed_op['pos'], server_op['pos'])
                                if overlap > 0:
                                    transformed_op['length'] = max(0, transformed_op['length'] - overlap)
                            
                            # Adjust old_length for replace operations
                            elif transformed_op['type'] == 'replace':
                                overlap = min(client_end, server_end) - max(transformed_op['pos'], server_op['pos'])
                                if overlap > 0:
                                    transformed_op['old_length'] = max(0, transformed_op['old_length'] - overlap)
                
                elif server_op['type'] == 'replace':
                    server_end = server_op['pos'] + server_op['old_length']
                    
                    # Similar logic to delete, but we need to account for the new text length
                    if transformed_op['type'] == 'insert':
                        if server_op['pos'] < transformed_op['pos']:
                            # Server replaced text before client's position
                            length_diff = len(server_op['text']) - server_op['old_length']
                            if server_end <= transformed_op['pos']:
                                # Replacement entirely before insertion point
                                transformed_op['pos'] += length_diff
                            else:
                                # Replacement overlaps insertion point
                                transformed_op['pos'] = server_op['pos'] + len(server_op['text'])
                    
                    elif transformed_op['type'] in ['delete', 'replace']:
                        # Complex case - similar to delete but with length differences
                        client_end = transformed_op['pos'] + transformed_op.get('length', transformed_op.get('old_length', 0))
                        length_diff = len(server_op['text']) - server_op['old_length']
                        
                        if server_end <= transformed_op['pos']:
                            # Server replacement before client operation
                            transformed_op['pos'] += length_diff
                        elif server_op['pos'] >= client_end:
                            # Server replacement after client operation
                            pass  # No change needed
                        else:
                            # Overlapping replacements - complex case
                            # For simplicity, we'll prioritize both changes by adjusting positions
                            if server_op['pos'] <= transformed_op['pos']:
                                # Server replacement starts before client operation
                                transformed_op['pos'] = server_op['pos'] + len(server_op['text'])
                            
                            # Adjust length/old_length based on overlap
                            if transformed_op['type'] == 'delete':
                                overlap = min(client_end, server_end) - max(transformed_op['pos'], server_op['pos'])
                                if overlap > 0:
                                    transformed_op['length'] = max(0, transformed_op['length'] - overlap)
                            elif transformed_op['type'] == 'replace':
                                overlap = min(client_end, server_end) - max(transformed_op['pos'], server_op['pos'])
                                if overlap > 0:
                                    transformed_op['old_length'] = max(0, transformed_op['old_length'] - overlap)
            
            # Add the transformed operation if it's still valid
            if (transformed_op['type'] == 'insert' and transformed_op['text']) or \
               (transformed_op['type'] == 'delete' and transformed_op['length'] > 0) or \
               (transformed_op['type'] == 'replace' and transformed_op['text']):
                transformed_ops.append(transformed_op)
        
        return transformed_ops
        
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
