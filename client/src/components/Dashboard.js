import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';

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
      // Pass username explicitly in the query parameter
      const response = await axios.get(`/api/documents?username=${encodeURIComponent(username)}`, { withCredentials: true });
      
      if (response.data.success) {
        setDocuments(response.data.documents);
      } else {
        setError('Failed to fetch documents');
      }
    } catch (err) {
      setError('Error fetching documents. Please try again.');
      console.error(err);
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
  
  return { documents, loading, error, fetchDocuments };
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
      const response = await axios.get(`/api/users?username=${encodeURIComponent(username)}`, { withCredentials: true });
      
      if (response.data.success) {
        setUsers(response.data.users);
      } else {
        setError('Failed to fetch users');
      }
    } catch (err) {
      setError('Error fetching users. Please try again.');
      console.error(err);
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
  
  const { user } = useAuth();
  const navigate = useNavigate();
  const { users, loading: loadingUsers } = useUsers(user?.username);
  
  // Use our polling hook for documents with explicit username
  const { 
    documents, 
    loading, 
    error, 
    fetchDocuments 
  } = useDocumentsPolling(user?.username, refreshTrigger);
  
  // Force refresh when a new document is created
  const triggerRefresh = () => {
    setRefreshTrigger(prev => prev + 1);
  };

  // fetchDocuments is now provided by the useDocumentsPolling hook

  const handleCreateDocument = async (e) => {
    e.preventDefault();
    
    if (!newDocTitle.trim()) {
      setLocalError('Please enter a document title');
      return;
    }
    
    try {
      setCreating(true);
      setLocalError('');
      
      const response = await axios.post('/api/documents', {
        title: newDocTitle,
        username: user.username // Explicitly pass the username
      }, { withCredentials: true });
      
      if (response.data.success) {
        setNewDocTitle('');
        triggerRefresh(); // Use our new refresh trigger
        navigate(`/documents/${response.data.document_id}`);
      } else {
        setLocalError(response.data.message);
      }
    } catch (err) {
      setLocalError('Failed to create document. Please try again.');
      console.error(err);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteDocument = async (documentId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) {
      return;
    }
    
    try {
      const response = await axios.delete(`/api/documents/${documentId}`, { withCredentials: true });
      
      if (response.data.success) {
        triggerRefresh(); // Use our new refresh trigger
      } else {
        setLocalError(response.data.message);
      }
    } catch (err) {
      setLocalError('Failed to delete document. Please try again.');
      console.error(err);
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
      const response = await axios.post(`/api/documents/${documentId}/users`, {
        username: selectedUser
      }, { withCredentials: true });
      
      if (response.data.success) {
        setSharingStatus({ message: `Document shared with ${selectedUser}`, isError: false });
        triggerRefresh(); // Use our new refresh trigger
        setSelectedUser('');
        
        // Auto-close sharing UI after 3 seconds
        setTimeout(() => {
          setSharingDocId(null);
          setSharingStatus({ message: '', isError: false });
        }, 3000);
      } else {
        setSharingStatus({ message: response.data.message, isError: true });
      }
    } catch (err) {
      setSharingStatus({ message: 'Failed to share document. Please try again.', isError: true });
      console.error(err);
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
          />
          <button type="submit" className="btn btn-primary" disabled={creating}>
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
