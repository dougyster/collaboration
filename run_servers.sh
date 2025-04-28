#!/bin/bash
# Script to run multiple distributed servers

# Kill any existing servers
pkill -f "python -m flask run"

# Create data directories if they don't exist
mkdir -p backend/database/server1
mkdir -p backend/database/server2
mkdir -p backend/database/server3

# Copy the original database file to each server's directory
cp backend/database/data.json backend/database/server1/data.json
cp backend/database/data.json backend/database/server2/data.json
cp backend/database/data.json backend/database/server3/data.json

# Start server 1
export SERVER_ID="server-1"
export FLASK_APP="backend/app.py"
export GRPC_PORT="50051"
export PEER_ADDRESSES="localhost:50052,localhost:50053"
export DB_PATH="backend/database/server1/data.json"
python -m flask run --host=0.0.0.0 --port=5000 &
echo "Started server 1 on port 5000 with gRPC port 50051"

# Wait for server 1 to initialize
sleep 10
echo "Server 1 initialized"

# Start server 2
export SERVER_ID="server-2"
export FLASK_APP="backend/app.py"
export GRPC_PORT="50052"
export PEER_ADDRESSES="localhost:50051,localhost:50053"
export DB_PATH="backend/database/server2/data.json"
python -m flask run --host=0.0.0.0 --port=5001 &
echo "Started server 2 on port 5001 with gRPC port 50052"

# Wait for server 2 to initialize
sleep 10
echo "Server 2 initialized"

# Start server 3
export SERVER_ID="server-3"
export FLASK_APP="backend/app.py"
export GRPC_PORT="50053"
export PEER_ADDRESSES="localhost:50051,localhost:50052"
export DB_PATH="backend/database/server3/data.json"
python -m flask run --host=0.0.0.0 --port=5002 &
echo "Started server 3 on port 5002 with gRPC port 50053"

echo "All servers started. Press Ctrl+C to stop all servers."
wait
