#!/usr/bin/env python3
"""
Migration script to update existing user passwords to use bcrypt hashing.
Run this script after updating the User class to use bcrypt.
"""
import sys
import os
import json
import bcrypt
import logging

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.database.db_interface import DatabaseInterface

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_passwords(db_path):
    """
    Migrate all user passwords in the database to use bcrypt hashing.
    
    Args:
        db_path: Path to the database file
    """
    logger.info(f"Starting password migration for database at {db_path}")
    
    # Initialize the database interface
    db = DatabaseInterface(db_path)
    
    # Read the database directly to get all users
    try:
        with open(db_path, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read database: {e}")
        return False
    
    # Check if the database has a users section
    if 'users' not in data:
        logger.warning("No users found in database")
        return True
    
    # Count of users processed
    total_users = len(data['users'])
    processed_users = 0
    
    # Process each user
    for username, user_data in data['users'].items():
        # Skip users that might already have hashed passwords (very long passwords)
        if len(user_data['password']) > 50:
            logger.info(f"Skipping user {username} - password appears to be already hashed")
            processed_users += 1
            continue
        
        # Hash the password
        password = user_data['password']
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Update the user data with the hashed password
        user_data['password'] = hashed.decode('utf-8')
        
        logger.info(f"Hashed password for user {username}")
        processed_users += 1
    
    # Write the updated data back to the database
    try:
        with open(db_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Successfully migrated {processed_users}/{total_users} user passwords")
        return True
    except Exception as e:
        logger.error(f"Failed to write updated database: {e}")
        return False

if __name__ == "__main__":
    # Check if a database path was provided
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Use the default database path
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/collaboration_db.json'))
    
    # Run the migration
    success = migrate_passwords(db_path)
    
    if success:
        logger.info("Password migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Password migration failed")
        sys.exit(1)
