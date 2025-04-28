#!/bin/bash

# This script starts a replica server with the specified ID, port, and data directory
# Usage: ./start_replica.sh <id> <port> <grpc_port> <data_dir> <peer_list>

if [ $# -lt 5 ]; then
    echo "Usage: ./start_replica.sh <id> <port> <grpc_port> <data_dir> <peer_list>"
    echo "Example: ./start_replica.sh server-1 5000 50051 ./backend/database/server1 localhost:50052,localhost:50053"
    exit 1
fi

SERVER_ID=$1
PORT=$2
GRPC_PORT=$3
DATA_DIR=$4
PEER_ADDRESSES=$5

# More thorough check and cleanup for port usage
echo "Checking if ports $PORT and $GRPC_PORT are available..."

# Kill any process using the HTTP port
if lsof -i:$PORT > /dev/null 2>&1; then
    echo "Port $PORT is already in use. Killing the process..."
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 2  # Give the process time to terminate
fi

# Kill any process using the gRPC port
if lsof -i:$GRPC_PORT > /dev/null 2>&1; then
    echo "gRPC port $GRPC_PORT is already in use. Killing the process..."
    lsof -ti:$GRPC_PORT | xargs kill -9 2>/dev/null || true
    sleep 2  # Give the process time to terminate
fi

# Create data directory if it doesn't exist
mkdir -p $DATA_DIR

# Copy the original database file if it doesn't exist in the data directory
if [ ! -f "$DATA_DIR/data.json" ]; then
    echo "Copying original database to $DATA_DIR/data.json"
    cp backend/database/data.json $DATA_DIR/data.json
fi

# Set environment variables
export SERVER_ID=$SERVER_ID
export FLASK_APP="backend/app.py"
export GRPC_PORT=$GRPC_PORT
export PEER_ADDRESSES=$PEER_ADDRESSES
export DB_PATH="$DATA_DIR/data.json"

echo "Starting server $SERVER_ID with HTTP port $PORT and gRPC port $GRPC_PORT"
echo "Data directory: $DATA_DIR"
echo "Peer addresses: $PEER_ADDRESSES"

# Virtual environment path (default to venv in the project directory)
VENV_PATH="${VENV_PATH:-$(dirname $0)/venv}"

# Activate virtual environment if not already activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Activating virtual environment at $VENV_PATH"
    source "$VENV_PATH/bin/activate"
fi

# Start the Flask server
python -m flask run --host=0.0.0.0 --port=$PORT
