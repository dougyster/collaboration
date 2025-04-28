import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../services/ApiClient';
import { useAuth } from '../context/AuthContext';

// Custom hook for polling document changes
function useDocumentPolling(documentId, username, initialLastEdited, onDocumentChanged) {
  const [lastPolled, setLastPolled] = useState(null);
  const pollingIntervalRef = useRef(null);
  const isPollingRef = useRef(false);
  
  // Start polling for changes
  useEffect(() => {
    if (!documentId || !username) return;
    
    const pollForChanges = async () => {
      if (isPollingRef.current) return; // Prevent overlapping polls
      
      try {
        isPollingRef.current = true;
        const response = await apiClient.getDocument(documentId);
        
        if (response.data.success) {
          const doc = response.data.document;
          const currentLastEdited = new Date(doc.last_edited).getTime();
          const previousLastEdited = lastPolled || initialLastEdited;
          
          // If the document has been updated since our last check
          if (currentLastEdited > previousLastEdited) {
            console.log('Document changed, fetching updates...');
            onDocumentChanged(doc);
          }
          
          setLastPolled(currentLastEdited);
        }
      } catch (error) {
        console.error('Error polling document:', error);
      } finally {
        isPollingRef.current = false;
      }
    };
    
    // Poll every 5 seconds
    pollingIntervalRef.current = setInterval(pollForChanges, 5000);
    
    // Initial poll
    pollForChanges();
    
    // Cleanup on unmount
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [documentId, initialLastEdited, onDocumentChanged, lastPolled]);
  
  return { lastPolled };
}

function DocumentEditor() {
  const [document, setDocument] = useState(null);
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [baseContent, setBaseContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [editingTitle, setEditingTitle] = useState(false);
  const [initialLastEdited, setInitialLastEdited] = useState(null);
  const [isUserTyping, setIsUserTyping] = useState(false);
  
  const { documentId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const saveTimeoutRef = useRef(null);
  const userEditingRef = useRef(false);

  useEffect(() => {
    fetchDocument();
  }, [documentId]);
  
  // Handle document changes from other users
  const handleDocumentChanged = React.useCallback((updatedDoc) => {
    // Only update if the user isn't actively typing
    if (!userEditingRef.current) {
      setDocument(updatedDoc);
      setContent(updatedDoc.data);
      setBaseContent(updatedDoc.data);
      setTitle(updatedDoc.title);
      
      // Show a notification
      setMessage('Document was updated by another user');
      setTimeout(() => setMessage(''), 3000);
    } else {
      // If user is typing, just update the base content for the next merge
      setBaseContent(updatedDoc.data);
      
      // Show a notification that there are changes
      setMessage('Document was updated by another user. Your changes will be merged when you stop typing.');
      setTimeout(() => setMessage(''), 5000);
    }
  }, []);
  
  // Use our polling hook with explicit username
  useDocumentPolling(
    documentId,
    user?.username, // Pass username explicitly
    initialLastEdited,
    handleDocumentChanged
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  const fetchDocument = async () => {
    if (!user) return; // Don't fetch if no user
    
    try {
      setLoading(true);
      const response = await apiClient.getDocument(documentId);
      
      if (response.data.success) {
        const doc = response.data.document;
        setDocument(doc);
        setContent(doc.data);
        setBaseContent(doc.data);
        setTitle(doc.title);
        
        // Set initial last edited timestamp for polling
        const lastEditedTimestamp = new Date(doc.last_edited).getTime();
        setInitialLastEdited(lastEditedTimestamp);
      } else {
        setError('Failed to fetch document');
      }
    } catch (err) {
      setError('Error fetching document. Please try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleContentChange = (e) => {
    setContent(e.target.value);
    
    // Mark that user is actively typing
    userEditingRef.current = true;
    setIsUserTyping(true);
    
    // Debounce save to avoid too many API calls
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    
    saveTimeoutRef.current = setTimeout(() => {
      saveDocument(e.target.value);
      // Mark that user has stopped typing after save
      userEditingRef.current = false;
      setIsUserTyping(false);
    }, 1000); // Save after 1 second of inactivity
  };

  const saveDocument = async (newContent) => {
    if (!user) return; // Don't save if no user
    
    try {
      setSaving(true);
      setMessage('');
      setError('');
      
      const response = await axios.put(`/api/documents/${documentId}/content`, {
        content: newContent,
        base_content: baseContent,
        username: user.username // Explicitly pass the username
      }, { withCredentials: true });
      
      if (response.data.success) {
        setMessage('Document saved');
        setBaseContent(response.data.content); // Update base content for future merges
        
        // If the content was modified during merge, update the editor
        if (response.data.content !== newContent) {
          setContent(response.data.content);
        }
      } else {
        setError(response.data.message);
      }
    } catch (err) {
      setError('Failed to save document. Please try again.');
      console.error(err);
    } finally {
      setSaving(false);
      
      // Clear message after 3 seconds
      setTimeout(() => {
        setMessage('');
      }, 3000);
    }
  };

  const handleTitleChange = async () => {
    if (!title.trim()) {
      setTitle(document.title);
      setEditingTitle(false);
      return;
    }
    
    if (title === document.title) {
      setEditingTitle(false);
      return;
    }
    
    try {
      const response = await axios.put(`/api/documents/${documentId}/title`, {
        title
      }, { withCredentials: true });
      
      if (!response.data.success) {
        setError(response.data.message);
        setTitle(document.title);
      }
    } catch (err) {
      setError('Failed to update title. Please try again.');
      setTitle(document.title);
      console.error(err);
    } finally {
      setEditingTitle(false);
    }
  };

  const handleTitleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleTitleChange();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setTitle(document.title);
      setEditingTitle(false);
    }
  };

  if (loading) {
    return <div className="editor-container">Loading document...</div>;
  }

  if (!document) {
    return <div className="editor-container">Document not found</div>;
  }

  return (
    <div className="editor-container">
      <div className="editor-header">
        {editingTitle ? (
          <input
            type="text"
            className="form-control"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleChange}
            onKeyDown={handleTitleKeyDown}
            autoFocus
          />
        ) : (
          <h2 className="editor-title" onClick={() => setEditingTitle(true)}>
            {title}
          </h2>
        )}
        <div className="editor-actions">
          <button 
            className="btn btn-secondary"
            onClick={() => navigate('/dashboard')}
          >
            Back to Dashboard
          </button>
        </div>
      </div>
      
      {error && <div className="alert alert-danger">{error}</div>}
      {message && <div className="alert alert-success">{message}</div>}
      
      <div className="editor-meta mb-3">
        <div className="flex justify-between items-center">
          <div>
            <p className="text-muted">
              Last edited: {new Date(document.last_edited).toLocaleString()}
            </p>
            <p className="text-muted">
              Shared with: {document.users.filter(u => u !== user.username).join(', ') || 'No one'}
            </p>
          </div>
          <div className="sync-status">
            {isUserTyping ? (
              <span className="status-badge editing">Editing...</span>
            ) : saving ? (
              <span className="status-badge saving">Saving...</span>
            ) : (
              <span className="status-badge synced">Synced</span>
            )}
          </div>
        </div>
      </div>
      
      <textarea
        className="editor-content"
        value={content}
        onChange={handleContentChange}
        placeholder="Start typing your document content here..."
      />
      
      {saving && <p className="text-muted mt-3">Saving...</p>}
    </div>
  );
}

export default DocumentEditor;
