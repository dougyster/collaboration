#!/usr/bin/env python
"""
Script to run multiple instances of the distributed server.
This script will start three Flask servers, each with its own distributed server instance.
The servers will communicate with each other via gRPC for leader election and state replication.
"""
import os
import sys
import time
import signal
import subprocess
import threading
import argparse
from typing import List, Dict

def run_server(server_id: str, port: int, grpc_port: int, peer_grpc_ports: List[int]):
    """Run a Flask server with a distributed server instance."""
    # Convert peer gRPC ports to peer addresses
    peer_addresses = [f"localhost:{p}" for p in peer_grpc_ports]
    
    # Set environment variables for the server
    env = os.environ.copy()
    env["SERVER_ID"] = server_id
    env["FLASK_APP"] = "backend/app.py"
    env["FLASK_ENV"] = "development"
    env["FLASK_DEBUG"] = "1"
    env["GRPC_PORT"] = str(grpc_port)
    env["PEER_ADDRESSES"] = ",".join(peer_addresses)
    
    # Start the Flask server
    cmd = [
        "python", "-m", "flask", "run",
        "--host=0.0.0.0",
        f"--port={port}"
    ]
    
    print(f"Starting server {server_id} on port {port} with gRPC port {grpc_port}")
    print(f"Peer addresses: {peer_addresses}")
    
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Print server output with server ID prefix
    prefix = f"[Server {server_id}] "
    for line in iter(process.stdout.readline, ""):
        print(prefix + line.rstrip())
    
    return process

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
        server_id = f"server-{i+1}"
        port = args.base_port + i
        grpc_port = args.base_grpc_port + i
        server_configs.append({
            "server_id": server_id,
            "port": port,
            "grpc_port": grpc_port
        })
    
    # Start each server in a separate thread
    processes = []
    try:
        for i, config in enumerate(server_configs):
            # Get peer gRPC ports (all other servers)
            peer_grpc_ports = [s["grpc_port"] for s in server_configs if s["server_id"] != config["server_id"]]
            
            # Start the server
            process = run_server(
                config["server_id"],
                config["port"],
                config["grpc_port"],
                peer_grpc_ports
            )
            processes.append(process)
            
            # Wait longer before starting the next server to allow full initialization
            time.sleep(5)
            print(f"Waiting for server {config['server_id']} to initialize...")
        
        # Wait for all servers to finish
        for process in processes:
            process.wait()
    
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        for process in processes:
            process.terminate()
        
        # Wait for processes to terminate
        for process in processes:
            process.wait()
        
        print("All servers shut down.")

if __name__ == "__main__":
    main()
