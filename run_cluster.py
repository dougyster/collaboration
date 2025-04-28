#!/usr/bin/env python
"""
Simplified script to run multiple instances of the distributed server.
This script will start three Flask servers, each with its own distributed server instance.
"""
import os
import sys
import time
import signal
import subprocess
import threading
import argparse
from typing import List, Dict

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath('.'))

def run_server(server_id: str, port: int, grpc_port: int, peer_grpc_ports: List[int]):
    """Run a Flask server with a distributed server instance."""
    # Convert peer gRPC ports to peer addresses
    peer_addresses = [f"localhost:{p}" for p in peer_grpc_ports]
    
    print(f"Starting server {server_id} on port {port} with gRPC port {grpc_port}")
    print(f"Peer addresses: {peer_addresses}")
    
    # Set environment variables for the server
    os.environ['SERVER_ID'] = f"server-{server_id}"
    os.environ['GRPC_PORT'] = str(grpc_port)
    os.environ['PEER_ADDRESSES'] = ','.join(peer_addresses)
    
    # Import the necessary modules here to avoid import issues
    from flask import Flask
    from backend.distributed.gateway import DistributedGateway
    from backend.controller.routes import app
    
    # Set up the database path
    db_path = os.path.join('backend', 'database', f'data_server-{server_id}.json')
    
    # Create a copy of the database file if it doesn't exist
    if not os.path.exists(db_path):
        original_db_path = os.path.join('backend', 'database', 'data.json')
        if os.path.exists(original_db_path):
            import shutil
            shutil.copy(original_db_path, db_path)
            
    # Override the database path in the environment
    os.environ['DB_PATH'] = db_path
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def main():
    """Run multiple instances of the distributed server."""
    parser = argparse.ArgumentParser(description="Run multiple instances of the distributed server.")
    parser.add_argument("--count", type=int, default=3, help="Number of servers to run")
    parser.add_argument("--base-port", type=int, default=5000, help="Base port for Flask servers")
    parser.add_argument("--base-grpc-port", type=int, default=50051, help="Base port for gRPC servers")
    args = parser.parse_args()
    
    # Calculate ports for each server
    server_configs = []
    for i in range(args.count):
        server_id = f"{i+1}"
        port = args.base_port + i
        grpc_port = args.base_grpc_port + i
        server_configs.append({
            "server_id": server_id,
            "port": port,
            "grpc_port": grpc_port
        })
    
    # Get all gRPC ports
    all_grpc_ports = [config["grpc_port"] for config in server_configs]
    
    # Start each server in a separate thread
    threads = []
    try:
        for config in server_configs:
            # Get peer gRPC ports (all other servers)
            peer_grpc_ports = [p for p in all_grpc_ports if p != config["grpc_port"]]
            
            # Start the server in a separate thread
            thread = threading.Thread(
                target=run_server,
                args=(
                    config["server_id"],
                    config["port"],
                    config["grpc_port"],
                    peer_grpc_ports
                ),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            
            # Wait much longer before starting the next server to allow full initialization
            wait_time = 15  # 15 seconds between server startups
            print(f"Waiting {wait_time} seconds for server {config['server_id']} to initialize...")
            time.sleep(wait_time)
        
        # Wait for all threads to finish (they won't since they're daemon threads)
        for thread in threads:
            thread.join()
    
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        sys.exit(0)

if __name__ == "__main__":
    main()
