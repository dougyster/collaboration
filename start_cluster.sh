#!/bin/bash

# This script starts a cluster of 3 replica servers for the distributed collaboration system
# Usage: ./start_cluster.sh

# Get the project root directory
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables from .env file if it exists
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    echo "Loading configuration from $ENV_FILE"
    source "$ENV_FILE"
fi

# Virtual environment path (default to venv in the project directory)
VENV_PATH="${VENV_PATH:-$PROJECT_DIR/venv}"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found at $VENV_PATH"
    echo "Creating a new virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
echo "Activating virtual environment at $VENV_PATH"
source "$VENV_PATH/bin/activate"

# Set default values if not provided in environment
# Server ports (HTTP)
PORT1="${PORT1:-5000}"
PORT2="${PORT2:-5001}"
PORT3="${PORT3:-5002}"

# gRPC ports
GRPC_PORT1="${GRPC_PORT1:-50051}"
GRPC_PORT2="${GRPC_PORT2:-50052}"
GRPC_PORT3="${GRPC_PORT3:-50053}"

# Data directories
DATA_DIR="${DATA_DIR:-$PROJECT_DIR/backend/database}"
SERVER1_DIR="${SERVER1_DIR:-$DATA_DIR/server1}"
SERVER2_DIR="${SERVER2_DIR:-$DATA_DIR/server2}"
SERVER3_DIR="${SERVER3_DIR:-$DATA_DIR/server3}"

# Kill any existing server processes more thoroughly
echo "Stopping any existing server processes..."
pkill -f "python -m flask run" || true

# Kill any processes using our ports
for PORT in $PORT1 $PORT2 $PORT3 $GRPC_PORT1 $GRPC_PORT2 $GRPC_PORT3; do
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
done

# Close any existing terminal windows running our servers
osascript -e 'tell application "Terminal" to close (every window whose name contains "'$PORT1'" or name contains "'$PORT2'" or name contains "'$PORT3'")' || true
sleep 3  # Give processes more time to fully terminate

# Define peer lists for each server
PEER_LIST1="localhost:$GRPC_PORT2,localhost:$GRPC_PORT3"
PEER_LIST2="localhost:$GRPC_PORT1,localhost:$GRPC_PORT3"
PEER_LIST3="localhost:$GRPC_PORT1,localhost:$GRPC_PORT2"

# Make scripts executable
chmod +x start_replica.sh

# Create data directories if they don't exist
mkdir -p $SERVER1_DIR $SERVER2_DIR $SERVER3_DIR

# Start each replica in a separate terminal window
# Server 1
echo "Starting Server 1 on HTTP port $PORT1 and gRPC port $GRPC_PORT1"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source $VENV_PATH/bin/activate && ./start_replica.sh server-1 $PORT1 $GRPC_PORT1 $SERVER1_DIR '$PEER_LIST1'\""
sleep 5  # Give the first server time to start up

# Server 2
echo "Starting Server 2 on HTTP port $PORT2 and gRPC port $GRPC_PORT2"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source $VENV_PATH/bin/activate && ./start_replica.sh server-2 $PORT2 $GRPC_PORT2 $SERVER2_DIR '$PEER_LIST2'\""
sleep 5  # Give the second server time to start up

# Server 3
echo "Starting Server 3 on HTTP port $PORT3 and gRPC port $GRPC_PORT3"
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd) && source $VENV_PATH/bin/activate && ./start_replica.sh server-3 $PORT3 $GRPC_PORT3 $SERVER3_DIR '$PEER_LIST3'\""

echo "Started 3 servers. The distributed system is now running."
echo "You can connect to any of the servers using the REST API on ports $PORT1, $PORT2, or $PORT3."
echo "The servers will communicate with each other via gRPC on ports $GRPC_PORT1, $GRPC_PORT2, and $GRPC_PORT3."
echo "Remember that write operations must go through the leader server, while read operations can be served by any server."
