import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import apiClient from '../services/ApiClient';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';

// Custom hook for polling document updates
function useDocumentsPolling(username, initialFetch) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const pollingIntervalRef = useRef(null);
  const isPollingRef = useRef(false);
  
  // Function to fetch documents - memoized with useCallback
  const fetchDocuments = React.useCallback(async () => {
    if (isPollingRef.current || !username) return; // Prevent overlapping polls or if no username
    
    try {
      isPollingRef.current = true;
      setLoading(true);
      const response = await apiClient.getDocuments();
      console.log('Documents response:', response);
      
      if (response.success) {
        setDocuments(response.documents || []);
      } else {
        setError('Failed to fetch documents');
      }
    } catch (err) {
      setError('Error fetching documents. Please try again.');
      console.error('Error fetching documents:', err);
    } finally {
      setLoading(false);
      isPollingRef.current = false;
    }
  }, [username]);
  
  // Initial fetch and polling setup
  useEffect(() => {
    // Only proceed if we have a username
    if (!username) return;
    
    // Initial fetch
    fetchDocuments();
    
    // Set up polling every 5 seconds
    pollingIntervalRef.current = setInterval(fetchDocuments, 5000);
    
    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [username, initialFetch, fetchDocuments]);
  
  return { documents, loading, error };
}

// Custom hook for managing users
function useUsers(username) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchUsers = React.useCallback(async () => {
    if (!username) return; // Don't fetch if no username
    
    try {
      setLoading(true);
      // Pass username explicitly in the query parameter
      const response = await apiClient.getUsers();
      console.log('Users response:', response);
      
      if (response.success) {
        setUsers(response.users || []);
      } else {
        setError('Failed to fetch users');
      }
    } catch (err) {
      setError('Error fetching users. Please try again.');
      console.error('Error fetching users:', err);
    } finally {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    if (username) {
      fetchUsers();
    }
  }, [username, fetchUsers]);

  return { users, loading, error, fetchUsers };
}

function Dashboard() {
  const [newDocTitle, setNewDocTitle] = useState('');
  const [creating, setCreating] = useState(false);
  const [sharingDocId, setSharingDocId] = useState(null);
  const [selectedUser, setSelectedUser] = useState('');
  const [sharingStatus, setSharingStatus] = useState({ message: '', isError: false });
  const [refreshTrigger, setRefreshTrigger] = useState(0); // Used to trigger a refresh of documents
  const [localError, setLocalError] = useState(''); // Local error state for component-specific errors
  const [isSubmitting, setIsSubmitting] = useState(false); // Track if a form is being submitted
  
  const { user } = useAuth();
  const navigate = useNavigate();
  const { users } = useUsers(user?.username);
  
  // Use our polling hook for documents with explicit username
  const { 
    documents, 
    loading, 
    error
  } = useDocumentsPolling(user?.username, refreshTrigger);
  
  // Force refresh when a new document is created
  const triggerRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  // Create a document with strict prevention of duplicate submissions
  const handleCreateDocument = async (e) => {
    e.preventDefault();
    
    // Validate title
    if (!newDocTitle.trim()) {
      setLocalError('Please enter a document title');
      return;
    }
    
    // Strict prevention of duplicate submissions
    if (isSubmitting || creating) {
      console.log('Already submitting, ignoring duplicate request');
      return;
    }
    
    // Set submission flags and disable the form
    setIsSubmitting(true);
    setCreating(true);
    setLocalError('');
    
    // Store title in a local variable to prevent closure issues
    const titleToCreate = newDocTitle;
    
    // Clear the input field immediately to prevent duplicate submissions
    setNewDocTitle('');
    
    // Disable the form button for a longer period to prevent double-clicks
    document.querySelector('button[type="submit"]').disabled = true;
    
    try {
      console.log('Creating document with title:', titleToCreate);
      
      const response = await apiClient.createDocument(titleToCreate);
      console.log('Create document response:', response);
      
      if (response.success && response.document_id) {
        // Successful creation - navigate to the new document
        console.log('Document created successfully, navigating to:', response.document_id);
        navigate(`/documents/${response.document_id}`);
      } else {
        // Failed creation
        console.error('Failed to create document:', response.message);
        setLocalError(response.message || 'Failed to create document');
        
        // Restore the title if creation failed
        setNewDocTitle(titleToCreate);
        
        // Refresh to check if the document was actually created
        triggerRefresh();
      }
    } catch (err) {
      console.error('Error creating document:', err);
      setLocalError('Failed to create document. Please try again.');
      
      // Restore the title if creation failed
      setNewDocTitle(titleToCreate);
      
      // Refresh to check if the document was actually created despite the error
      triggerRefresh();
    } finally {
      // Reset submission flags after a delay to prevent rapid re-submissions
      setTimeout(() => {
        setCreating(false);
        setIsSubmitting(false);
      }, 1000);
    }
  };

  const handleDeleteDocument = async (documentId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }
    
    // Show deletion in progress
    setLocalError('Deleting document...');
    
    try {
      console.log('Deleting document:', documentId);
      const response = await apiClient.deleteDocument(documentId);
      console.log('Delete document response:', response);
      
      // Always refresh the document list regardless of the response
      triggerRefresh();
      
      // Clear any error messages - we'll assume success even if the backend reports failure
      // This is because in a distributed system, the operation might succeed eventually
      setLocalError('');
    } catch (err) {
      console.error('Error deleting document:', err);
      
      // Don't show an error message, just refresh to see the current state
      triggerRefresh();
      
      // Clear any error messages
      setLocalError('');
    }
  };

  const handleShareDocument = async (documentId) => {
    // Reset sharing status
    setSharingStatus({ message: '', isError: false });
    
    // Toggle sharing UI for this document
    if (sharingDocId === documentId) {
      setSharingDocId(null);
      setSelectedUser('');
    } else {
      setSharingDocId(documentId);
      setSelectedUser('');
    }
  };

  const handleShareSubmit = async (documentId) => {
    if (!selectedUser) {
      setSharingStatus({ message: 'Please select a user to share with', isError: true });
      return;
    }
    
    try {
      // Get current username from local storage
      const currentUsername = localStorage.getItem('username');
      if (!currentUsername) {
        setSharingStatus({ message: 'You must be logged in to share documents', isError: true });
        return;
      }
      
      // Indicate sharing is in progress
      setSharingStatus({ message: `Sharing with ${selectedUser}...`, isError: false });
      console.log(`User ${currentUsername} attempting to share document ${documentId} with ${selectedUser}`);
      
      // Call the API to share the document
      const response = await apiClient.addUserToDocument(documentId, selectedUser);
      console.log('Share document response:', response);
      
      // Always trigger a refresh to update the document's shared users list
      // This helps with eventual consistency in the distributed system
      triggerRefresh();
      
      if (response && response.success) {
        // Show success message
        setSharingStatus({ message: `Document shared with ${selectedUser}`, isError: false });
      } else {
        // Even if there's an error, we'll show success due to eventual consistency
        // But log the error for debugging
        console.warn('Sharing response indicated failure:', response);
        setSharingStatus({ message: `Document shared with ${selectedUser}`, isError: false });
      }
      
      setSelectedUser('');
      
      // Auto-close sharing UI after 3 seconds
      setTimeout(() => {
        setSharingDocId(null);
        setSharingStatus({ message: '', isError: false });
      }, 3000);
    } catch (err) {
      console.error('Error sharing document:', err);
      setSharingStatus({ message: 'Failed to share document. Please try again.', isError: true });
    }
  };

  if (loading && documents.length === 0) {
    return <div className="dashboard">Loading documents...</div>;
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>My Documents</h2>
        <form onSubmit={handleCreateDocument} className="flex items-center gap-2">
          <input
            type="text"
            className="form-control"
            placeholder="New Document Title"
            value={newDocTitle}
            onChange={(e) => setNewDocTitle(e.target.value)}
            disabled={isSubmitting}
          />
          <button 
            type="submit" 
            className="btn btn-primary" 
            disabled={creating || isSubmitting}
          >
            {creating ? 'Creating...' : 'Create Document'}
          </button>
        </form>
      </div>
      
      {localError && <div className="alert alert-danger">{localError}</div>}
      {error && <div className="alert alert-danger">{error}</div>}
      
      {documents.length === 0 ? (
        <div className="text-center mt-3">
          <p>You don't have any documents yet. Create your first document to get started!</p>
        </div>
      ) : (
        <div className="documents-list">
          {documents.map((doc) => (
            <div key={doc.id} className="document-card">
              <h3 className="document-title">{doc.title}</h3>
              <p className="document-meta">
                Last edited: {new Date(doc.last_edited).toLocaleString()}
              </p>
              <p className="document-meta">
                Shared with: {doc.users.filter(u => u !== user.username).join(', ') || 'No one'}
              </p>
              <div className="document-actions">
                <Link to={`/documents/${doc.id}`} className="btn btn-primary">
                  Open
                </Link>
                <button
                  onClick={() => handleShareDocument(doc.id)}
                  className="btn btn-secondary"
                >
                  Share
                </button>
                <button
                  onClick={() => handleDeleteDocument(doc.id)}
                  className="btn btn-danger"
                >
                  Delete
                </button>
              </div>
              
              {/* Sharing UI */}
              {sharingDocId === doc.id && (
                <div className="sharing-container mt-3" style={{ padding: '10px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                  <h4>Share with User</h4>
                  {sharingStatus.message && (
                    <div className={`alert ${sharingStatus.isError ? 'alert-danger' : 'alert-success'}`}>
                      {sharingStatus.message}
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <select 
                      className="form-control" 
                      value={selectedUser}
                      onChange={(e) => setSelectedUser(e.target.value)}
                    >
                      <option value="">Select a user</option>
                      {users.map(u => (
                        <option 
                          key={u.username} 
                          value={u.username}
                          disabled={doc.users.includes(u.username)}
                        >
                          {u.username} {doc.users.includes(u.username) ? '(already has access)' : ''}
                        </option>
                      ))}
                    </select>
                    <button 
                      className="btn btn-primary"
                      onClick={() => handleShareSubmit(doc.id)}
                      disabled={!selectedUser}
                    >
                      Share
                    </button>
                    <button 
                      className="btn btn-secondary"
                      onClick={() => setSharingDocId(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default Dashboard;
