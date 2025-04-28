import React, { createContext, useState, useContext, useEffect } from 'react';
import apiClient from '../services/ApiClient';

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
        
        const response = await apiClient.checkAuth();
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
      const response = await apiClient.login(username, password);
      if (response.data.success) {
        // User data is already included in the login response
        setUser(response.data.user);  
        localStorage.setItem('collaborationUser', JSON.stringify(response.data.user));
        return { success: true, message: response.data.message };
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
      const response = await apiClient.register(username, password);
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
      await apiClient.logout();
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
