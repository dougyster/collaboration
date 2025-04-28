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
    const username = localStorage.getItem('username');
    if (username) {
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
    const username = localStorage.getItem('username');
    return this.get(`/api/documents?username=${encodeURIComponent(username)}`);
  }

  async getDocument(documentId) {
    const username = localStorage.getItem('username');
    return this.get(`/api/documents/${documentId}?username=${encodeURIComponent(username)}`);
  }

  async createDocument(title) {
    const username = localStorage.getItem('username');
    return this.post('/api/documents', { title, username });
  }

  async updateDocumentContent(documentId, content) {
    const username = localStorage.getItem('username');
    return this.put(`/api/documents/${documentId}/content`, { content, username });
  }

  async updateDocumentTitle(documentId, title) {
    const username = localStorage.getItem('username');
    return this.put(`/api/documents/${documentId}/title`, { title, username });
  }

  async deleteDocument(documentId) {
    const username = localStorage.getItem('username');
    return this.delete(`/api/documents/${documentId}?username=${encodeURIComponent(username)}`);
  }

  async getUsers() {
    const username = localStorage.getItem('username');
    return this.get(`/api/users?username=${encodeURIComponent(username)}`);
  }

  async addUserToDocument(documentId, userToAdd) {
    const username = localStorage.getItem('username');
    return this.post(`/api/documents/${documentId}/users`, { username, user_to_add: userToAdd });
  }

  async getClusterStatus() {
    return this.get('/api/cluster/status');
  }
}

// Create and export a singleton instance
const apiClient = new ApiClient();
export default apiClient;
