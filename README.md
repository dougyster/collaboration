# Collaborative Document Editor

A real-time collaboration document editor similar to Google Docs. This application allows users to create, edit, and share documents with other users.

## Project Structure

- `backend/`: Backend with distributed server architecture, business logic, and API routes
- `client/`: React frontend for the user interface

## Setup and Running

### Backend Setup

1. Navigate to the project root directory

2. Install dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```

3. Run the distributed server cluster:
   ```
   ./start_cluster.sh
   ```
   This will start a cluster of servers using the Raft consensus algorithm for distributed operation

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

- User authentication (register, login, logout) with bcrypt password hashing
- Create, view, edit, and delete documents
- Real-time document editing with conflict resolution
- Share documents with other users
- Secure password storage using bcrypt

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

## Testing

The application includes a comprehensive test suite for the backend components:

- Business logic tests
- Distributed server tests
- Gateway tests
- API routes tests

To run the tests, navigate to the backend directory and use Python's unittest framework:

```
cd backend
python -m unittest discover tests
```

Individual test files can be run with:

```
python -m unittest tests/test_business_logic.py
python -m unittest tests/test_server.py
python -m unittest tests/test_gateway.py
python -m unittest tests/test_routes.py
```

## Security

### Password Hashing

This application uses bcrypt for secure password hashing. When users register, their passwords are hashed before being stored in the database. During authentication, the provided password is verified against the stored hash.

### Password Migration

A migration script is provided to update existing passwords to use bcrypt hashing:

```
source venv/bin/activate
python backend/scripts/migrate_passwords.py
```

This script will automatically convert plaintext passwords in the database to bcrypt hashed passwords.
