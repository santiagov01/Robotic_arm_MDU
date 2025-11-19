#!/usr/bin/env python3
"""
CAN Interface Manager for Jetson Orin
Manages receiving and sending data from/to multiple CAN nodes using python-can library.
"""

import can
import threading
import queue
import time
from typing import List, Dict, Callable
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class CANManager:
    """
    Manages CAN bus communication with multiple nodes.
    Supports receiving data from specific nodes and sending processed responses.
    """
    
    def __init__(self, interface: str = "can0", bitrate: int = 500000):
        """
        Initialize the CAN Manager.
        
        Args:
            interface: CAN interface name (default: "can0")
            bitrate: CAN bus bitrate (default: 500000)
        """
        self.interface = interface
        self.bitrate = bitrate
        self.bus = None
        
        # Shared queues
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
        # Task-specific queues
        self.task_queues: Dict[str, queue.Queue] = {}
        
        # Thread control
        self.stop_event = threading.Event()
        self.threads: List[threading.Thread] = []
        
    def initialize(self):
        """Initialize the CAN bus interface."""
        try:
            self.bus = can.interface.Bus(
                channel=self.interface,
                interface="socketcan",
                bitrate=self.bitrate
            )
            logger.info(f"CAN bus initialized on {self.interface} at {self.bitrate} bps")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize CAN bus: {e}")
            return False
    
    def _read_can_bus(self):
        """
        Thread task: Continuously read CAN messages from the bus.
        Stores all incoming messages in the incoming_queue.
        """
        logger.info("CAN bus reader thread started")
        
        while not self.stop_event.is_set():
            message = self.bus.recv(timeout=0.1)
            if message is None:
                continue
            
            self.incoming_queue.put(message)
            logger.debug(f"Received: ID=0x{message.arbitration_id:X}, Data={message.data.hex()}")
    
    def _send_can_bus(self):
        """
        Thread task: Send CAN messages from the outgoing_queue to the bus.
        """
        logger.info("CAN bus sender thread started")
        
        while not self.stop_event.is_set():
            try:
                msg = self.outgoing_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            try:
                self.bus.send(msg)
                logger.info(f"Sent: ID=0x{msg.arbitration_id:X}, Data={msg.data.hex()}")
            except can.CanError as e:
                logger.error(f"Error sending message: {e}")
            
            self.outgoing_queue.task_done()
    
    def _dispatcher(self, node_filters: Dict[str, List[int]]):
        """
        Thread task: Route incoming messages to appropriate task queues based on CAN IDs.
        
        Args:
            node_filters: Dictionary mapping task names to lists of CAN IDs they handle
        """
        logger.info("Message dispatcher thread started")
        
        while not self.stop_event.is_set():
            try:
                msg = self.incoming_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            
            # Route message to appropriate task queue(s)
            routed = False
            for task_name, can_ids in node_filters.items():
                if msg.arbitration_id in can_ids:
                    if task_name in self.task_queues:
                        self.task_queues[task_name].put(msg)
                        routed = True
            
            if not routed:
                logger.debug(f"Unhandled message ID: 0x{msg.arbitration_id:X}")
            
            self.incoming_queue.task_done()
    
    def add_processing_task(self, 
                           task_name: str, 
                           input_node_ids: List[int],
                           processing_func: Callable,
                           output_node_ids: List[int] = None):
        """
        Add a processing task that receives data from specific nodes and sends to others.
        
        Args:
            task_name: Unique name for this task
            input_node_ids: List of CAN IDs to receive data from
            processing_func: Function that processes received data and returns response data
                            Signature: func(msg: can.Message) -> bytes or None
            output_node_ids: List of CAN IDs to send responses to (optional)
        """
        # Create queue for this task
        self.task_queues[task_name] = queue.Queue()
        
        def task_worker():
            logger.info(f"Task '{task_name}' started - Monitoring IDs: {[hex(id) for id in input_node_ids]}")
            
            while not self.stop_event.is_set():
                try:
                    msg = self.task_queues[task_name].get(timeout=0.1)
                except queue.Empty:
                    continue
                
                logger.info(f"[{task_name}] Processing message from ID=0x{msg.arbitration_id:X}, Data={msg.data.hex()}")
                
                try:
                    # Process the received message
                    result = processing_func(msg)
                    
                    if result is not None and output_node_ids:
                        # Send response to output nodes
                        for output_id in output_node_ids:
                            response = can.Message(
                                arbitration_id=output_id,
                                data=result,
                                is_extended_id=False
                            )
                            self.outgoing_queue.put(response)
                            logger.info(f"[{task_name}] Queued response to ID=0x{output_id:X}, Data={result.hex()}")
                
                except Exception as e:
                    logger.error(f"[{task_name}] Error processing message: {e}")
                
                self.task_queues[task_name].task_done()
        
        return task_worker
    
    def start(self, node_filters: Dict[str, List[int]], processing_tasks: List[Callable]):
        """
        Start all CAN bus threads and processing tasks.
        
        Args:
            node_filters: Dictionary mapping task names to lists of CAN IDs
            processing_tasks: List of processing task worker functions
        """
        if not self.bus:
            logger.error("CAN bus not initialized. Call initialize() first.")
            return False
        
        # Start core threads
        self.threads.append(threading.Thread(target=self._read_can_bus, daemon=True))
        self.threads.append(threading.Thread(target=self._send_can_bus, daemon=True))
        self.threads.append(threading.Thread(target=self._dispatcher, args=(node_filters,), daemon=True))
        
        # Start processing tasks
        for task_func in processing_tasks:
            self.threads.append(threading.Thread(target=task_func, daemon=True))
        
        # Launch all threads
        for thread in self.threads:
            thread.start()
        
        logger.info(f"All threads started successfully ({len(self.threads)} threads)")
        return True
    
    def stop(self):
        """Stop all threads and close the CAN bus."""
        logger.info("Stopping CAN manager...")
        self.stop_event.set()
        
        for thread in self.threads:
            thread.join(timeout=2.0)
        
        if self.bus:
            self.bus.shutdown()
        
        logger.info("CAN manager stopped")


# -----------------------
# EXAMPLE USAGE
# -----------------------
def example_processing_task_1(msg: can.Message) -> bytes:
    """
    Example processing function for Task 1.
    Receives data from nodes 0x100, 0x101, 0x102
    Processes by inverting each byte (XOR with 0xFF)
    """
    processed_data = bytes([b ^ 0xFF for b in msg.data])
    return processed_data


def example_processing_task_2(msg: can.Message) -> bytes:
    """
    Example processing function for Task 2.
    Receives data from nodes 0x200, 0x201
    Processes by adding 1 to each byte (mod 256)
    """
    processed_data = bytes([(b + 1) % 256 for b in msg.data])
    return processed_data


if __name__ == "__main__":
    # Create CAN manager instance
    manager = CANManager(interface="can0", bitrate=500000)
    
    # Initialize CAN bus
    if not manager.initialize():
        logger.error("Failed to initialize CAN bus. Exiting.")
        exit(1)
    
    # Define which CAN IDs each task should monitor
    node_filters = {
        "task_1": [0x100, 0x101, 0x102],  # Task 1 monitors these nodes
        "task_2": [0x200, 0x201],          # Task 2 monitors these nodes
    }
    
    # Create processing tasks
    task_1_worker = manager.add_processing_task(
        task_name="task_1",
        input_node_ids=[0x100, 0x101, 0x102],
        processing_func=example_processing_task_1,
        output_node_ids=[0x300]  # Send processed data to node 0x300
    )
    
    task_2_worker = manager.add_processing_task(
        task_name="task_2",
        input_node_ids=[0x200, 0x201],
        processing_func=example_processing_task_2,
        output_node_ids=[0x400, 0x401]  # Send processed data to nodes 0x400 and 0x401
    )
    
    # Start all tasks
    processing_tasks = [task_1_worker, task_2_worker]
    manager.start(node_filters, processing_tasks)
    
    logger.info("CAN Manager running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nShutdown requested...")
    finally:
        manager.stop()
        logger.info("Shutdown complete.")
