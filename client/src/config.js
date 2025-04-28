/**
 * Configuration for the collaboration client
 * This file contains settings for connecting to the distributed server cluster
 */

// List of available API servers in the cluster
const API_SERVERS = [
  'http://localhost:5000',
  'http://localhost:5001',
  'http://localhost:5002'
];

// Default server to use (first one in the list)
const DEFAULT_SERVER = API_SERVERS[0];

// Timeout for API requests in milliseconds
const REQUEST_TIMEOUT = 5000;

// Maximum number of retries for failed requests
const MAX_RETRIES = 3;

// Delay between retries in milliseconds
const RETRY_DELAY = 1000;

export {
  API_SERVERS,
  DEFAULT_SERVER,
  REQUEST_TIMEOUT,
  MAX_RETRIES,
  RETRY_DELAY
};
