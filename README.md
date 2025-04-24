# Collaborative Document Editor

A real-time collaboration document editor similar to Google Docs. This application allows users to create, edit, and share documents with other users.

## Project Structure

- `backend/`: Flask backend with database, business logic, and API routes
- `client/`: React frontend for the user interface

## Setup and Running

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the Flask server:
   ```
   python app.py
   ```
   This will start the server on http://localhost:5000

### Frontend Setup

1. Navigate to the client directory:
   ```
   cd client
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Run the React development server:
   ```
   npm start
   ```
   This will start the client on http://localhost:3000

## Features

- User authentication (register, login, logout)
- Create, view, edit, and delete documents
- Real-time document editing with conflict resolution
- Share documents with other users

## API Endpoints

### Authentication
- `POST /api/register`: Register a new user
- `POST /api/login`: Login a user
- `POST /api/logout`: Logout a user
- `GET /api/user`: Get the current user

### Documents
- `GET /api/documents`: Get all documents for the current user
- `POST /api/documents`: Create a new document
- `GET /api/documents/:id`: Get a document by ID
- `PUT /api/documents/:id/title`: Update a document's title
- `PUT /api/documents/:id/content`: Update a document's content
- `DELETE /api/documents/:id`: Delete a document
- `POST /api/documents/:id/users`: Add a user to a document
- `DELETE /api/documents/:id/users/:username`: Remove a user from a document
