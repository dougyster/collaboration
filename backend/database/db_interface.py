"""
Database interface for the collaboration system.
Defines schemas and CRUD operations for the database.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os
import threading

# Define schemas as type hints
class User:
    def __init__(self, username: str, password: str, documents: List[str] = None):
        self.username = username
        self.password = password  # Note: In a real app, this should be hashed
        self.documents = documents or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "password": self.password,
            "documents": self.documents
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        return cls(
            username=data["username"],
            password=data["password"],
            documents=data.get("documents", [])
        )

class Document:
    def __init__(self, id: str, title: str, data: str, last_edited: datetime = None, users: List[str] = None):
        self.id = id
        self.title = title
        self.data = data
        self.last_edited = last_edited or datetime.now()
        self.users = users or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "data": self.data,
            "last_edited": self.last_edited.isoformat(),
            "users": self.users
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        return cls(
            id=data["id"],
            title=data["title"],
            data=data["data"],
            last_edited=datetime.fromisoformat(data["last_edited"]),
            users=data.get("users", [])
        )

class DatabaseInterface:
    """Interface for CRUD operations on the database."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()  # For thread safety
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """Ensure the database file exists."""
        if not os.path.exists(os.path.dirname(self.db_path)):
            os.makedirs(os.path.dirname(self.db_path))
        
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w') as f:
                json.dump({"users": {}, "documents": {}}, f)
    
    def _read_db(self) -> Dict[str, Any]:
        """Read the database file."""
        with open(self.db_path, 'r') as f:
            return json.load(f)
    
    def _write_db(self, data: Dict[str, Any]) -> None:
        """Write to the database file."""
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    # User CRUD operations
    def create_user(self, user: User) -> bool:
        """Create a new user."""
        with self.lock:
            db = self._read_db()
            if user.username in db["users"]:
                return False  # User already exists
            
            db["users"][user.username] = user.to_dict()
            self._write_db(db)
            return True
    
    def get_user(self, username: str) -> Optional[User]:
        """Get a user by username."""
        with self.lock:
            db = self._read_db()
            user_data = db["users"].get(username)
            if not user_data:
                return None
            
            return User.from_dict(user_data)
    
    def update_user(self, user: User) -> bool:
        """Update a user."""
        with self.lock:
            db = self._read_db()
            if user.username not in db["users"]:
                return False  # User doesn't exist
            
            db["users"][user.username] = user.to_dict()
            self._write_db(db)
            return True
    
    def delete_user(self, username: str) -> bool:
        """Delete a user."""
        with self.lock:
            db = self._read_db()
            if username not in db["users"]:
                return False  # User doesn't exist
            
            del db["users"][username]
            self._write_db(db)
            return True
    
    # Document CRUD operations
    def create_document(self, document: Document) -> bool:
        """Create a new document."""
        with self.lock:
            db = self._read_db()
            if document.id in db["documents"]:
                return False  # Document already exists
            
            db["documents"][document.id] = document.to_dict()
            
            # Update users' document lists
            for username in document.users:
                if username in db["users"]:
                    user_data = db["users"][username]
                    if document.id not in user_data["documents"]:
                        user_data["documents"].append(document.id)
            
            self._write_db(db)
            return True
    
    def get_document(self, document_id: str) -> Optional[Document]:
        """Get a document by ID."""
        with self.lock:
            db = self._read_db()
            doc_data = db["documents"].get(document_id)
            if not doc_data:
                return None
            
            return Document.from_dict(doc_data)
    
    def update_document(self, document: Document) -> bool:
        """Update a document."""
        with self.lock:
            db = self._read_db()
            if document.id not in db["documents"]:
                return False  # Document doesn't exist
            
            db["documents"][document.id] = document.to_dict()
            self._write_db(db)
            return True
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document."""
        with self.lock:
            db = self._read_db()
            if document_id not in db["documents"]:
                return False  # Document doesn't exist
            
            # Get the document to remove it from users
            document = Document.from_dict(db["documents"][document_id])
            
            # Remove document from users' document lists
            for username in document.users:
                if username in db["users"]:
                    user_data = db["users"][username]
                    if document_id in user_data["documents"]:
                        user_data["documents"].remove(document_id)
            
            del db["documents"][document_id]
            self._write_db(db)
            return True
    
    def get_user_documents(self, username: str) -> List[Document]:
        """Get all documents for a user."""
        with self.lock:
            db = self._read_db()
            user_data = db["users"].get(username)
            if not user_data:
                return []
            
            documents = []
            for doc_id in user_data["documents"]:
                if doc_id in db["documents"]:
                    documents.append(Document.from_dict(db["documents"][doc_id]))
            
            return documents
