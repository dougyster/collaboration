"""
Distributed server implementation for the collaboration system.
Implements a consensus-based distributed system with leader election.
"""
import os
import sys
import uuid
import time
import random
import threading
import logging
import grpc
from concurrent import futures
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import json

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import generated gRPC code
from backend.distributed import distributed_server_pb2 as ds_pb2
from backend.distributed import distributed_server_pb2_grpc as ds_grpc

# Import business logic
from backend.interactor.business_logic import BusinessLogic
from backend.database.db_interface import DatabaseInterface, User, Document

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Server states
FOLLOWER = 'follower'
CANDIDATE = 'candidate'
LEADER = 'leader'

class DistributedServer(ds_grpc.DistributedServiceServicer):
    """
    Implementation of a distributed server using the Raft consensus algorithm.
    """
    
    def __init__(self, server_id=None, port=50051, peer_addresses=None, db_path=None):
        """Initialize the distributed server."""
        # Server identity
        if server_id is None:
            raise ValueError("server_id must be provided")
        self.server_id = server_id
        self.port = port
        
        # Consensus state
        self.state = FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.leader_id = None
        self.votes_received = 0
        
        # Log state
        self.log = []  # List of LogEntry objects
        self.commit_index = -1
        self.last_applied = -1
        
        # Peer management
        self.peer_addresses = peer_addresses or []
        self.next_index = {}  # Dict of server_id -> next log index to send
        self.match_index = {}  # Dict of server_id -> highest log index known to be replicated
        
        # Timeouts - use longer values to prevent rapid elections
        self.election_timeout = random.uniform(2000, 4000) / 1000  # 2-4 seconds
        self.heartbeat_interval = 500 / 1000  # 500ms
        self.last_heartbeat = time.time()
        
        # Database and business logic
        if db_path is None:
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database', 'data.json')
        self.db_interface = DatabaseInterface(db_path)
        self.business_logic = BusinessLogic(self.db_interface)
        
        # Thread management
        self.running = False
        self.election_thread = None
        self.heartbeat_thread = None
        self.apply_thread = None
        self.server = None
        self.lock = threading.RLock()  # Reentrant lock for thread safety
        
        logger.info(f"Initialized server {self.server_id} on port {self.port}")
    
    def start(self):
        """Start the distributed server."""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            
            # Start gRPC server
            self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            ds_grpc.add_DistributedServiceServicer_to_server(self, self.server)
            self.server.add_insecure_port(f'[::]:{self.port}')
            self.server.start()
            logger.info(f"Server {self.server_id} started on port {self.port}")
            
            # Initialize peer tracking
            for peer in self.peer_addresses:
                self.next_index[peer] = 0
                self.match_index[peer] = -1
            
            # Wait a bit before starting election timer to allow other servers to start
            logger.info(f"Server {self.server_id} waiting for peers to start...")
            time.sleep(15.0)  # Longer delay to ensure all peers are up
            
            # Try to connect to peers to verify they're up
            self._check_peer_connectivity()
            
            # Start background threads
            self.election_thread = threading.Thread(target=self._run_election_timer, daemon=True)
            self.election_thread.start()
            
            self.apply_thread = threading.Thread(target=self._apply_committed_entries, daemon=True)
            self.apply_thread.start()
            
            logger.info(f"Server {self.server_id} fully initialized and running")
    
    def stop(self):
        """Stop the distributed server."""
        with self.lock:
            if not self.running:
                return
            
            self.running = False
            
            if self.server:
                self.server.stop(0)
            
            logger.info(f"Server {self.server_id} stopped")
    
    def _run_election_timer(self):
        """Run the election timer in a background thread."""
        while self.running:
            time.sleep(0.01)  # Small sleep to prevent CPU spinning
            
            with self.lock:
                # Skip if we're the leader
                if self.state == LEADER:
                    continue
                
                # Check if election timeout has elapsed
                elapsed = time.time() - self.last_heartbeat
                if elapsed >= self.election_timeout:
                    self._start_election()
    
    def _start_election(self):
        """Start a new election."""
        with self.lock:
            self.state = CANDIDATE
            self.current_term += 1
            self.voted_for = self.server_id
            self.votes_received = 1  # Vote for self
            self.last_heartbeat = time.time()  # Reset timeout
            
            logger.info(f"Server {self.server_id} starting election for term {self.current_term}")
            
            # Check if we're the only server left in the cluster
            all_peers_down = True
            for peer in self.peer_addresses:
                peer_key = f"peer_down_{peer}"
                peer_down_until = getattr(self, peer_key, 0)
                if peer_down_until <= time.time():
                    all_peers_down = False
                    break
            
            # If all peers are down, become leader immediately
            if all_peers_down and self.peer_addresses:
                logger.info(f"Server {self.server_id} becoming leader as all other servers are down")
                self._become_leader()
                return
            
            # Request votes from all peers
            active_vote_requests = 0
            for peer in self.peer_addresses:
                peer_key = f"peer_down_{peer}"
                peer_down_until = getattr(self, peer_key, 0)
                if peer_down_until <= time.time():  # Only request votes from peers that are not known to be down
                    active_vote_requests += 1
                    threading.Thread(target=self._request_vote, args=(peer,), daemon=True).start()
            
            # If no active vote requests were started (all peers known to be down), become leader
            if active_vote_requests == 0 and self.peer_addresses:
                logger.info(f"Server {self.server_id} becoming leader as all other servers are known to be down")
                self._become_leader()
    
    def _request_vote(self, peer_address):
        """Send a RequestVote RPC to a peer."""
        max_retries = 5
        retry_delay = 1.0  # seconds
        peer_key = f"peer_down_{peer_address}"
        
        for attempt in range(max_retries):
            try:
                with grpc.insecure_channel(peer_address) as channel:
                    stub = ds_grpc.DistributedServiceStub(channel)
                    
                    with self.lock:
                        # If we're no longer a candidate, stop trying
                        if self.state != CANDIDATE:
                            return
                            
                        last_log_index = len(self.log) - 1
                        last_log_term = self.log[last_log_index].term if last_log_index >= 0 else 0
                        
                        request = ds_pb2.VoteRequest(
                            server_id=self.server_id,
                            term=self.current_term,
                            last_log_index=last_log_index,
                            last_log_term=last_log_term
                        )
                    
                    response = stub.RequestVote(request, timeout=5.0)  # Increased timeout for vote requests
                    
                    with self.lock:
                        # If we're no longer a candidate, ignore the response
                        if self.state != CANDIDATE:
                            return
                        
                        # If the response term is higher, become follower
                        if response.term > self.current_term:
                            self._become_follower(response.term)
                            return
                        
                        # Count the vote if granted
                        if response.vote_granted:
                            self.votes_received += 1
                            
                            # Check if we have a majority
                            if self.votes_received > (len(self.peer_addresses) + 1) / 2:
                                self._become_leader()
                    
                    # If we got a successful response, break the retry loop
                    break
                    
            except Exception as e:
                # On the last retry, mark the peer as down
                if attempt == max_retries - 1:
                    # Set a cooldown period before trying this peer again (30 seconds)
                    setattr(self, peer_key, time.time() + 30)
                    
                    # Log warning instead of error
                    logger.warning(f"Peer {peer_address} is down during election, will retry in 30 seconds")
                    
                    with self.lock:
                        # Check if all peers are now known to be down
                        all_peers_down = True
                        for peer in self.peer_addresses:
                            peer_down_key = f"peer_down_{peer}"
                            peer_down_until = getattr(self, peer_down_key, 0)
                            if peer_down_until <= time.time() and peer != peer_address:  # Exclude the peer we just marked down
                                all_peers_down = False
                                break
                        
                        # If all peers are down and we're still a candidate, become leader
                        if all_peers_down and self.state == CANDIDATE:
                            logger.info(f"Server {self.server_id} becoming leader as all other servers are down")
                            self._become_leader()
                else:
                    # For earlier attempts, just log at debug level
                    logger.debug(f"Error requesting vote from {peer_address} (attempt {attempt+1}/{max_retries}): {e}")
                    
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    time.sleep(retry_delay)
    
    def _become_follower(self, term):
        """Transition to follower state."""
        with self.lock:
            self.state = FOLLOWER
            self.current_term = term
            self.voted_for = None
            self.last_heartbeat = time.time()
            
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread = None
            
            logger.info(f"Server {self.server_id} became follower for term {term}")
    
    def _become_leader(self):
        """Transition to leader state."""
        with self.lock:
            self.state = LEADER
            self.leader_id = self.server_id
            
            # Initialize leader state
            for peer in self.peer_addresses:
                self.next_index[peer] = len(self.log)
                self.match_index[peer] = -1
            
            logger.info(f"Server {self.server_id} became leader for term {self.current_term}")
            
            # Start sending heartbeats
            self.heartbeat_thread = threading.Thread(target=self._send_heartbeats, daemon=True)
            self.heartbeat_thread.start()
    
    def _send_heartbeats(self):
        """Send heartbeats to all peers periodically."""
        while self.running and self.state == LEADER:
            start_time = time.time()
            
            # Send heartbeat to each peer
            for peer in self.peer_addresses:
                threading.Thread(target=self._send_append_entries, args=(peer,), daemon=True).start()
            
            # Sleep until next heartbeat interval
            elapsed = time.time() - start_time
            sleep_time = max(0, self.heartbeat_interval - elapsed)
            time.sleep(sleep_time)
    
    def _send_append_entries(self, peer_address):
        """Send an AppendEntries RPC (heartbeat) to a peer."""
        max_retries = 5
        retry_delay = 1.0  # seconds
        
        # Check if this peer is already known to be down
        peer_key = f"peer_down_{peer_address}"
        peer_down_until = getattr(self, peer_key, 0)
        current_time = time.time()
        
        # If peer was marked as down and cooldown period hasn't expired, skip
        if peer_down_until > current_time:
            return
        
        for attempt in range(max_retries):
            try:
                with grpc.insecure_channel(peer_address) as channel:
                    stub = ds_grpc.DistributedServiceStub(channel)
                    
                    with self.lock:
                        # If we're no longer the leader, stop trying
                        if self.state != LEADER:
                            return
                            
                        prev_log_index = self.next_index.get(peer_address, 0) - 1
                        prev_log_term = 0
                        if prev_log_index >= 0 and prev_log_index < len(self.log):
                            prev_log_term = self.log[prev_log_index].term
                        
                        # Get entries to send
                        entries = []
                        next_idx = self.next_index.get(peer_address, 0)
                        if next_idx < len(self.log):
                            entries = self.log[next_idx:]
                        
                        # Convert entries to protobuf format
                        pb_entries = []
                        for entry in entries:
                            pb_entry = ds_pb2.LogEntry(
                                term=entry.term,
                                index=entry.index,
                                command=entry.command,
                                timestamp=entry.timestamp
                            )
                            pb_entries.append(pb_entry)
                        
                        request = ds_pb2.HeartbeatRequest(
                            leader_id=self.server_id,
                            term=self.current_term,
                            commit_index=self.commit_index,
                            entries=pb_entries
                        )
                    
                    response = stub.SendHeartbeat(request, timeout=5.0)
                    
                    with self.lock:
                        # If we're no longer the leader, ignore the response
                        if self.state != LEADER:
                            return
                        
                        # If the response term is higher, become follower
                        if response.term > self.current_term:
                            self._become_follower(response.term)
                            return
                        
                        # Update indices if successful
                        if response.success:
                            if entries:
                                self.next_index[peer_address] = entries[-1].index + 1
                                self.match_index[peer_address] = entries[-1].index
                            
                            # Update commit index if possible
                            self._update_commit_index()
                            
                            # If peer was previously down, log that it's back up
                            if hasattr(self, peer_key) and getattr(self, peer_key) > 0:
                                logger.info(f"Peer {peer_address} is back online")
                                setattr(self, peer_key, 0)  # Reset the down status
                        else:
                            # Decrement next_index and retry
                            self.next_index[peer_address] = max(0, self.next_index.get(peer_address, 0) - 1)
                    
                    # If we got a successful response, break the retry loop
                    break
                    
            except Exception as e:
                # On the last retry, mark the peer as down and log the error (but only once)
                if attempt == max_retries - 1:
                    # Set a cooldown period before trying this peer again (30 seconds)
                    setattr(self, peer_key, time.time() + 30)
                    
                    # Only log the error if this is the first time we're marking it down
                    if not hasattr(self, peer_key) or getattr(self, peer_key) == 0:
                        logger.warning(f"Peer {peer_address} is down, will retry in 30 seconds")
                
                if attempt < max_retries - 1:  # Don't sleep on the last attempt
                    time.sleep(retry_delay)
    
    def _check_peer_connectivity(self):
        """Try to connect to peers to verify they're up."""
        for peer in self.peer_addresses:
            connected = False
            retries = 10  # Increased number of retries
            
            for attempt in range(retries):
                try:
                    # Try to establish a connection and make a simple ping-like call
                    with grpc.insecure_channel(peer) as channel:
                        stub = ds_grpc.DistributedServiceStub(channel)
                        
                        # Create a simple vote request as a ping
                        request = ds_pb2.VoteRequest(
                            server_id=self.server_id,
                            term=0,  # Use term 0 to indicate this is just a connectivity check
                            last_log_index=0,
                            last_log_term=0
                        )
                        
                        try:
                            # Set a longer timeout for the request during startup
                            response = stub.RequestVote(request, timeout=5.0)
                            connected = True
                            logger.info(f"Server {self.server_id} successfully connected to peer {peer}")
                            break
                        except grpc.RpcError as rpc_error:
                            # If we get a specific gRPC error (not a connection error), the server is up
                            if rpc_error.code() != grpc.StatusCode.UNAVAILABLE:
                                connected = True
                                logger.info(f"Server {self.server_id} successfully connected to peer {peer} (got RPC error: {rpc_error.code()})")
                                break
                            else:
                                raise  # Re-raise to be caught by the outer exception handler
                except Exception as e:
                    logger.warning(f"Server {self.server_id} failed to connect to peer {peer} (attempt {attempt+1}/{retries}): {e}")
                
                # If not connected, wait before retrying
                if not connected and attempt < retries - 1:
                    time.sleep(2)  # Wait 2 seconds between retries
            
            if not connected:
                logger.warning(f"Server {self.server_id} could not connect to peer {peer} after {retries} attempts")
    
    def _update_commit_index(self):
        """Update the commit index based on the match indices of all servers."""
        with self.lock:
            if self.state != LEADER:
                return
            
            # Find the highest index that is replicated on a majority of servers
            for n in range(self.commit_index + 1, len(self.log)):
                # Only commit entries from the current term
                if self.log[n].term != self.current_term:
                    continue
                
                # Count servers that have replicated this entry
                count = 1  # Include self
                for peer in self.peer_addresses:
                    if self.match_index.get(peer, -1) >= n:
                        count += 1
                
                # If a majority have replicated, update commit index
                if count > (len(self.peer_addresses) + 1) / 2:
                    self.commit_index = n
                    logger.info(f"Leader {self.server_id} updated commit index to {n}")
                    break
    
    def _apply_committed_entries(self):
        """Apply committed log entries to the state machine."""
        while self.running:
            time.sleep(0.01)  # Small sleep to prevent CPU spinning
            
            with self.lock:
                if self.commit_index > self.last_applied:
                    self.last_applied += 1
                    entry = self.log[self.last_applied]
                    self._apply_command(entry.command)
                    logger.info(f"Server {self.server_id} applied entry {self.last_applied}")
    
    def _apply_command(self, command_bytes):
        """Apply a command to the business logic."""
        try:
            command = json.loads(command_bytes.decode('utf-8'))
            operation = command.get('operation')
            args = command.get('args', {})
            
            # Call the appropriate business logic method based on the operation
            if operation == 'register_user':
                username = args.get('username')
                password = args.get('password')
                self.business_logic.register_user(username, password)
            
            elif operation == 'authenticate_user':
                username = args.get('username')
                password = args.get('password')
                self.business_logic.authenticate_user(username, password)
            
            elif operation == 'create_document':
                title = args.get('title')
                username = args.get('username')
                self.business_logic.create_document(title, username)
            
            elif operation == 'update_document_title':
                document_id = args.get('document_id')
                title = args.get('title')
                username = args.get('username')
                self.business_logic.update_document_title(document_id, title, username)
            
            elif operation == 'update_document_content':
                document_id = args.get('document_id')
                content = args.get('content')
                base_content = args.get('base_content')
                username = args.get('username')
                if base_content:
                    self.business_logic.update_document_content_with_merge(
                        document_id, content, base_content, username
                    )
                else:
                    self.business_logic.update_document_content(
                        document_id, content, username
                    )
            
            elif operation == 'delete_document':
                document_id = args.get('document_id')
                username = args.get('username')
                self.business_logic.delete_document(document_id, username)
            
            elif operation == 'add_user_to_document':
                document_id = args.get('document_id')
                username = args.get('username')
                added_by = args.get('added_by')
                self.business_logic.add_user_to_document(document_id, username, added_by)
            
            elif operation == 'remove_user_from_document':
                document_id = args.get('document_id')
                username = args.get('username')
                removed_by = args.get('removed_by')
                self.business_logic.remove_user_from_document(document_id, username, removed_by)
            
            else:
                logger.warning(f"Unknown operation: {operation}")
        
        except Exception as e:
            logger.error(f"Error applying command: {e}")
    
    def _append_log_entry(self, command_dict):
        """Append a new entry to the log."""
        with self.lock:
            command_bytes = json.dumps(command_dict).encode('utf-8')
            
            entry = LogEntry(
                term=self.current_term,
                index=len(self.log),
                command=command_bytes,
                timestamp=datetime.now()
            )
            
            self.log.append(entry)
            
            # If leader, replicate to followers
            if self.state == LEADER:
                for peer in self.peer_addresses:
                    threading.Thread(target=self._send_append_entries, args=(peer,), daemon=True).start()
                
                # Update commit index if only one server
                if not self.peer_addresses:
                    self.commit_index = entry.index
            
            return entry.index
    
    # gRPC service methods
    def RequestVote(self, request, context):
        """Handle a RequestVote RPC."""
        with self.lock:
            # If the request term is lower, reject
            if request.term < self.current_term:
                return ds_pb2.VoteResponse(
                    server_id=self.server_id,
                    term=self.current_term,
                    vote_granted=False
                )
            
            # If the request term is higher, become follower
            if request.term > self.current_term:
                self._become_follower(request.term)
            
            # Determine if we can vote for this candidate
            vote_granted = False
            if (self.voted_for is None or self.voted_for == request.server_id) and self._is_log_up_to_date(request):
                self.voted_for = request.server_id
                vote_granted = True
                self.last_heartbeat = time.time()  # Reset timeout
            
            return ds_pb2.VoteResponse(
                server_id=self.server_id,
                term=self.current_term,
                vote_granted=vote_granted
            )
    
    def _is_log_up_to_date(self, request):
        """Check if the candidate's log is at least as up-to-date as ours."""
        last_log_index = len(self.log) - 1
        last_log_term = self.log[last_log_index].term if last_log_index >= 0 else 0
        
        if request.last_log_term != last_log_term:
            return request.last_log_term > last_log_term
        
        return request.last_log_index >= last_log_index
    
    def SendHeartbeat(self, request, context):
        """Handle an AppendEntries RPC (heartbeat)."""
        with self.lock:
            # If the request term is lower, reject
            if request.term < self.current_term:
                return ds_pb2.HeartbeatResponse(
                    server_id=self.server_id,
                    term=self.current_term,
                    success=False,
                    last_applied=self.last_applied
                )
            
            # If the request term is higher or equal, update term and become follower
            if request.term >= self.current_term:
                self._become_follower(request.term)
                self.leader_id = request.leader_id
            
            self.last_heartbeat = time.time()  # Reset timeout
            
            # Process log entries
            success = True
            if request.entries:
                # TODO: Implement log consistency check and append new entries
                pass
            
            # Update commit index
            if request.commit_index > self.commit_index:
                self.commit_index = min(request.commit_index, len(self.log) - 1)
            
            return ds_pb2.HeartbeatResponse(
                server_id=self.server_id,
                term=self.current_term,
                success=success,
                last_applied=self.last_applied
            )
    
    def ReplicateCommand(self, request, context):
        """Handle a ReplicateCommand RPC."""
        with self.lock:
            # If we're the leader, append to our log
            if self.state == LEADER:
                # TODO: Implement command replication
                pass
            
            # If we're not the leader, redirect to the leader
            else:
                context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"Not the leader. Current leader: {self.leader_id}")
            
            return ds_pb2.CommandResponse(
                server_id=self.server_id,
                term=self.current_term,
                success=True
            )
    
    # Business logic methods that will be called by the Flask API
    def register_user(self, username, password):
        """Register a new user."""
        command = {
            'operation': 'register_user',
            'args': {
                'username': username,
                'password': password
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.register_user(username, password)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}"
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later."
    
    def authenticate_user(self, username, password):
        """Authenticate a user."""
        # Read operations can be served by any server
        return self.business_logic.authenticate_user(username, password)
    
    def create_document(self, title, username):
        """Create a new document."""
        command = {
            'operation': 'create_document',
            'args': {
                'title': title,
                'username': username
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.create_document(title, username)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}", None
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later.", None
    
    def get_document(self, document_id, username):
        """Get a document by ID."""
        # Read operations can be served by any server
        return self.business_logic.get_document(document_id, username)
    
    def update_document_title(self, document_id, title, username):
        """Update a document's title."""
        command = {
            'operation': 'update_document_title',
            'args': {
                'document_id': document_id,
                'title': title,
                'username': username
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.update_document_title(document_id, title, username)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}"
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later."
    
    def update_document_content(self, document_id, content, base_content, username):
        """Update a document's content."""
        command = {
            'operation': 'update_document_content',
            'args': {
                'document_id': document_id,
                'content': content,
                'base_content': base_content,
                'username': username
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            if base_content:
                return self.business_logic.update_document_content_with_merge(
                    document_id, content, base_content, username
                )
            else:
                return self.business_logic.update_document_content(
                    document_id, content, username
                )
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}", None
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later.", None
    
    def get_user_documents(self, username):
        """Get all documents for a user."""
        # Read operations can be served by any server
        return self.business_logic.get_user_documents(username)
    
    def delete_document(self, document_id, username):
        """Delete a document."""
        command = {
            'operation': 'delete_document',
            'args': {
                'document_id': document_id,
                'username': username
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.delete_document(document_id, username)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}"
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later."
    
    def add_user_to_document(self, document_id, username, added_by):
        """Add a user to a document."""
        command = {
            'operation': 'add_user_to_document',
            'args': {
                'document_id': document_id,
                'username': username,
                'added_by': added_by
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.add_user_to_document(document_id, username, added_by)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}"
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later."
    
    def remove_user_from_document(self, document_id, username, removed_by):
        """Remove a user from a document."""
        command = {
            'operation': 'remove_user_from_document',
            'args': {
                'document_id': document_id,
                'username': username,
                'removed_by': removed_by
            }
        }
        
        # If leader, append to log and replicate
        if self.state == LEADER:
            index = self._append_log_entry(command)
            # Wait for the entry to be committed
            while self.commit_index < index and self.running:
                time.sleep(0.01)
            
            # Return the result from the business logic
            return self.business_logic.remove_user_from_document(document_id, username, removed_by)
        
        # If not leader, redirect to leader
        elif self.leader_id:
            # In a real implementation, we would forward the request to the leader
            # For now, just return an error
            return False, f"Not the leader. Current leader: {self.leader_id}"
        
        # If no leader, return an error
        else:
            return False, "No leader available. Try again later."


class LogEntry:
    """Represents a log entry in the Raft consensus algorithm."""
    
    def __init__(self, term, index, command, timestamp=None):
        self.term = term
        self.index = index
        self.command = command
        self.timestamp = timestamp or datetime.now()


def serve():
    """Start a distributed server."""
    server = DistributedServer()
    server.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()


if __name__ == '__main__':
    serve()
