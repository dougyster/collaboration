import React, { createContext, useState, useContext, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext();

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  // Initialize user state from localStorage if available
  const [user, setUser] = useState(() => {
    const savedUser = localStorage.getItem('collaborationUser');
    return savedUser ? JSON.parse(savedUser) : null;
  });
  const [loading, setLoading] = useState(true);

  // Update localStorage when user changes
  useEffect(() => {
    if (user) {
      localStorage.setItem('collaborationUser', JSON.stringify(user));
    }
  }, [user]);

  useEffect(() => {
    // Check if user is already logged in
    const checkLoggedIn = async () => {
      try {
        // If we already have a user in localStorage, skip the API call
        if (user) {
          setLoading(false);
          return;
        }
        
        const response = await axios.get('/api/user', { withCredentials: true });
        if (response.data.success) {
          setUser(response.data.user);
        }
      } catch (error) {
        console.log('Not logged in');
      } finally {
        setLoading(false);
      }
    };

    checkLoggedIn();
  }, [user]);

  const login = async (username, password) => {
    try {
      const response = await axios.post('/api/login', { username, password }, { withCredentials: true });
      if (response.data.success) {
        // Fetch user data after successful login
        const userResponse = await axios.get('/api/user', { withCredentials: true });
        if (userResponse.data.success) {
          const userData = userResponse.data.user;
          // Store user in state and localStorage
          setUser(userData);
          localStorage.setItem('collaborationUser', JSON.stringify(userData));
          return { success: true, message: response.data.message };
        }
      }
      return { success: false, message: response.data.message };
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.message || 'Login failed. Please try again.'
      };
    }
  };

  const register = async (username, password) => {
    try {
      const response = await axios.post('/api/register', { username, password });
      return { success: response.data.success, message: response.data.message };
    } catch (error) {
      return {
        success: false,
        message: error.response?.data?.message || 'Registration failed. Please try again.'
      };
    }
  };

  const logout = async () => {
    try {
      await axios.post('/api/logout', {}, { withCredentials: true });
      // Clear user from state and localStorage
      setUser(null);
      localStorage.removeItem('collaborationUser');
      return { success: true };
    } catch (error) {
      return { success: false, message: 'Logout failed. Please try again.' };
    }
  };

  const value = {
    user,
    login,
    register,
    logout,
    loading
  };

  return (
    <AuthContext.Provider value={value}>
      {!loading && children}
    </AuthContext.Provider>
  );
}
