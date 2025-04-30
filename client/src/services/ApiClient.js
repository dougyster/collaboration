import axios from 'axios';
import { API_SERVERS, DEFAULT_SERVER, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY } from '../config';

/**
 * API Client for the distributed collaboration system
 * Handles communication with the backend servers, including retries and failover
 */
class ApiClient {
  constructor() {
    this.currentServerIndex = 0;
    this.currentServer = DEFAULT_SERVER;
    this.axios = axios.create({
      baseURL: this.currentServer,
      timeout: REQUEST_TIMEOUT,
      withCredentials: true
    });
  }

  /**
   * Switch to the next available server in the cluster
   */
  switchServer() {
    this.currentServerIndex = (this.currentServerIndex + 1) % API_SERVERS.length;
    this.currentServer = API_SERVERS[this.currentServerIndex];
    this.axios.defaults.baseURL = this.currentServer;
    console.log(`Switched to server: ${this.currentServer}`);
  }

  /**
   * Make an API request with automatic retries and server failover
   * @param {String} method - HTTP method (get, post, put, delete)
   * @param {String} url - API endpoint
   * @param {Object} data - Request data (for POST, PUT)
   * @param {Object} config - Additional axios config
   * @returns {Promise} - Promise resolving to the API response
   */
  async request(method, url, data = null, config = {}) {
    // Make sure username is included in all requests to avoid session confusion
    // But only add it as a query parameter for GET and DELETE requests
    // For POST and PUT, we'll include it in the request body
    const username = localStorage.getItem('username');
    const isGetOrDelete = method.toLowerCase() === 'get' || method.toLowerCase() === 'delete';
    
    if (username && isGetOrDelete) {
      if (!url.includes('?')) {
        url = `${url}?username=${encodeURIComponent(username)}`;
      } else if (!url.includes('username=')) {
        url = `${url}&username=${encodeURIComponent(username)}`;
      }
    }

    let retries = 0;
    let lastError = null;

    while (retries < MAX_RETRIES * API_SERVERS.length) {
      try {
        let response;
        
        if (method.toLowerCase() === 'get') {
          response = await this.axios.get(url, config);
        } else if (method.toLowerCase() === 'post') {
          response = await this.axios.post(url, data, config);
        } else if (method.toLowerCase() === 'put') {
          response = await this.axios.put(url, data, config);
        } else if (method.toLowerCase() === 'delete') {
          response = await this.axios.delete(url, config);
        }

        // If we get a redirect to the leader, follow it
        if (response.data && response.data.redirect_to_leader) {
          const leaderUrl = response.data.leader_url;
          console.log(`Redirecting to leader: ${leaderUrl}`);
          this.axios.defaults.baseURL = leaderUrl;
          this.currentServer = leaderUrl;
          
          // Retry the request with the leader
          if (method.toLowerCase() === 'get') {
            response = await this.axios.get(url, config);
          } else if (method.toLowerCase() === 'post') {
            response = await this.axios.post(url, data, config);
          } else if (method.toLowerCase() === 'put') {
            response = await this.axios.put(url, data, config);
          } else if (method.toLowerCase() === 'delete') {
            response = await this.axios.delete(url, config);
          }
        }

        return response.data;
      } catch (error) {
        lastError = error;
        retries++;
        
        // If we've tried all servers, wait before cycling through them again
        if (retries % API_SERVERS.length === 0) {
          await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
        } else {
          // Try the next server
          this.switchServer();
        }
      }
    }

    // If all retries failed, throw the last error
    throw lastError;
  }

  // Convenience methods for different HTTP verbs
  async get(url, config = {}) {
    return this.request('get', url, null, config);
  }

  async post(url, data = {}, config = {}) {
    return this.request('post', url, data, config);
  }

  async put(url, data = {}, config = {}) {
    return this.request('put', url, data, config);
  }

  async delete(url, config = {}) {
    return this.request('delete', url, config);
  }

  // Authentication methods
  async login(username, password) {
    const response = await this.post('/api/login', { username, password });
    if (response.success) {
      localStorage.setItem('username', username);
    }
    return response;
  }

  async register(username, password) {
    const response = await this.post('/api/register', { username, password });
    if (response.success) {
      localStorage.setItem('username', username);
    }
    return response;
  }

  async logout() {
    const response = await this.post('/api/logout');
    if (response.success) {
      localStorage.removeItem('username');
    }
    return response;
  }

  async checkAuth() {
    const username = localStorage.getItem('username');
    if (!username) {
      return { success: false };
    }
    
    try {
      return await this.get(`/api/user?username=${encodeURIComponent(username)}`);
    } catch (error) {
      localStorage.removeItem('username');
      return { success: false };
    }
  }

  // Document methods
  async getDocuments() {
    const username = this.getCurrentUsername();
    return this.get(`/api/documents?username=${encodeURIComponent(username)}`);
  }

  async getDocument(documentId) {
    const username = this.getCurrentUsername();
    return this.get(`/api/documents/${documentId}?username=${encodeURIComponent(username)}`);
  }

  async createDocument(title) {
    const username = this.getCurrentUsername();
    return this.post('/api/documents', { title, username });
  }

  async updateDocumentContent(documentId, content) {
    const username = this.getCurrentUsername();
    return this.put(`/api/documents/${documentId}/content`, { content, username });
  }

  async updateDocumentTitle(documentId, title) {
    const username = this.getCurrentUsername();
    return this.put(`/api/documents/${documentId}/title`, { title, username });
  }

  async deleteDocument(documentId) {
    const username = this.getCurrentUsername();
    return this.delete(`/api/documents/${documentId}?username=${encodeURIComponent(username)}`);
  }

  async getUsers() {
    const username = this.getCurrentUsername();
    return this.get(`/api/users?username=${encodeURIComponent(username)}`);
  }

  async addUserToDocument(documentId, userToAdd) {
    const currentUsername = this.getCurrentUsername();
    
    // Enhanced debugging for username retrieval
    console.log('DEBUG - localStorage contents:', {
      username: localStorage.getItem('username'),
      allKeys: Object.keys(localStorage),
      documentId,
      userToAdd
    });
    
    // Check if username is missing and provide clear error
    if (!currentUsername) {
      console.error('ERROR: No username found in localStorage! User must be logged in to share documents.');
      return Promise.reject(new Error('No username found in localStorage. Please log out and log back in.'));
    }
    
    console.log(`User ${currentUsername} sharing document ${documentId} with user ${userToAdd}`);
    
    // Pass both the current user (owner_username) and the user to add (username)
    return this.post(`/api/documents/${documentId}/users`, { 
      username: userToAdd,
      owner_username: currentUsername 
    });
  }
  
  async removeUserFromDocument(documentId, userToRemove) {
    const currentUsername = this.getCurrentUsername();
    console.log(`User ${currentUsername} removing user ${userToRemove} from document ${documentId}`);
    
    // Check if username is missing and provide clear error
    if (!currentUsername) {
      console.error('ERROR: No username found in localStorage! User must be logged in to remove users from documents.');
      return Promise.reject(new Error('No username found in localStorage. Please log out and log back in.'));
    }
    
    // Pass the owner_username as a query parameter for DELETE requests
    return this.delete(`/api/documents/${documentId}/users/${userToRemove}?owner_username=${encodeURIComponent(currentUsername)}`);
  }

  async getClusterStatus() {
    return this.get('/api/cluster/status');
  }
  
  /**
   * Helper method to get the current username from localStorage
   * Handles both direct username and username stored in collaborationUser object
   */
  getCurrentUsername() {
    // First try to get username directly (for backward compatibility)
    const directUsername = localStorage.getItem('username');
    if (directUsername) return directUsername;
    
    // If not found, try to get it from the collaborationUser object
    const userJson = localStorage.getItem('collaborationUser');
    if (userJson) {
      try {
        const userObj = JSON.parse(userJson);
        if (userObj && userObj.username) {
          // For convenience, also set it directly for future use
          localStorage.setItem('username', userObj.username);
          return userObj.username;
        }
      } catch (e) {
        console.error('Error parsing user JSON from localStorage:', e);
      }
    }
    
    return null;
  }
}

// Create and export a singleton instance
const apiClient = new ApiClient();
export default apiClient;
