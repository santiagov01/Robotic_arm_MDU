#!/usr/bin/env python3
"""
CAN Bus Send and Receive Example
Demonstrates various ways to send and receive CAN messages using python-can library
"""

import can
import time
import threading
from typing import Optional

# CAN Configuration
CAN_INTERFACE = 'socketcan'  # Change to 'virtual', 'pcan', 'kvaser', etc. as needed
CAN_CHANNEL = 'can0'         # Change to your CAN channel
BITRATE = 500000             # 500 kbit/s

# Node IDs
NODE_1_ID = 0x101
NODE_2_ID = 0x102
NODE_3_ID = 0x103
MASTER_ID = 0x100


class CANManager:
    """Manages CAN bus communication with multiple nodes"""
    
    def __init__(self, interface: str, channel: str, bitrate: int):
        """
        Initialize CAN bus interface
        
        Args:
            interface: CAN interface type (socketcan, virtual, pcan, etc.)
            channel: CAN channel name
            bitrate: CAN bus bitrate
        """
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.bus: Optional[can.Bus] = None
        self.running = False
        self.receive_thread = None
        
    def connect(self):
        """Establish CAN bus connection"""
        try:
            self.bus = can.Bus(
                interface=self.interface,
                channel=self.channel,
                bitrate=self.bitrate
            )
            print(f"✓ Connected to CAN bus: {self.channel}")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to CAN bus: {e}")
            return False
    
    def disconnect(self):
        """Close CAN bus connection"""
        self.running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        if self.bus:
            self.bus.shutdown()
            print("✓ CAN bus disconnected")
    
    # ==================== SENDING METHODS ====================
    
    def send_message(self, arbitration_id: int, data: list, is_extended: bool = False):
        """
        Send a standard CAN message
        
        Args:
            arbitration_id: CAN message ID
            data: List of bytes to send (max 8 bytes)
            is_extended: Use extended frame format (29-bit ID)
        """
        try:
            message = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=is_extended
            )
            self.bus.send(message)
            print(f"→ Sent: ID=0x{arbitration_id:X}, Data={[hex(b) for b in data]}")
        except Exception as e:
            print(f"✗ Send error: {e}")
    
    def send_remote_frame(self, arbitration_id: int, dlc: int = 0):
        """
        Send a Remote Transmission Request (RTR) frame
        
        Args:
            arbitration_id: CAN message ID
            dlc: Data Length Code (0-8)
        """
        try:
            message = can.Message(
                arbitration_id=arbitration_id,
                is_remote_frame=True,
                dlc=dlc
            )
            self.bus.send(message)
            print(f"→ Sent RTR: ID=0x{arbitration_id:X}, DLC={dlc}")
        except Exception as e:
            print(f"✗ RTR send error: {e}")
    
    def send_periodic_message(self, arbitration_id: int, data: list, period: float):
        """
        Send a periodic CAN message
        
        Args:
            arbitration_id: CAN message ID
            data: List of bytes to send
            period: Period in seconds between messages
        
        Returns:
            CyclicSendTask object that can be used to stop the task
        """
        try:
            message = can.Message(
                arbitration_id=arbitration_id,
                data=data
            )
            task = self.bus.send_periodic(message, period)
            print(f"→ Started periodic: ID=0x{arbitration_id:X}, Period={period}s")
            return task
        except Exception as e:
            print(f"✗ Periodic send error: {e}")
            return None
    
    # ==================== RECEIVING METHODS ====================
    
    def receive_message(self, timeout: float = 1.0):
        """
        Receive a single CAN message (blocking)
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Received message or None
        """
        try:
            message = self.bus.recv(timeout=timeout)
            if message:
                self._print_message(message)
            return message
        except Exception as e:
            print(f"✗ Receive error: {e}")
            return None
    
    def receive_with_filter(self, can_id: int, mask: int = 0x7FF, timeout: float = 1.0):
        """
        Receive messages with a filter applied
        
        Args:
            can_id: CAN ID to filter for
            mask: Bit mask for filtering
            timeout: Timeout in seconds
        """
        try:
            filters = [{"can_id": can_id, "can_mask": mask}]
            self.bus.set_filters(filters)
            print(f"← Filter set: ID=0x{can_id:X}, Mask=0x{mask:X}")
            
            message = self.bus.recv(timeout=timeout)
            if message:
                self._print_message(message)
            return message
        except Exception as e:
            print(f"✗ Filtered receive error: {e}")
            return None
    
    def receive_continuous(self, callback=None):
        """
        Start continuous message reception in a separate thread
        
        Args:
            callback: Optional callback function called for each message
        """
        self.running = True
        self.receive_thread = threading.Thread(
            target=self._receive_loop,
            args=(callback,),
            daemon=True
        )
        self.receive_thread.start()
        print("← Started continuous reception")
    
    def _receive_loop(self, callback=None):
        """Internal loop for continuous reception"""
        while self.running:
            try:
                message = self.bus.recv(timeout=0.5)
                if message:
                    self._print_message(message)
                    if callback:
                        callback(message)
            except Exception as e:
                if self.running:
                    print(f"✗ Reception loop error: {e}")
    
    def _print_message(self, message: can.Message):
        """Print received message in a formatted way"""
        msg_type = "RTR" if message.is_remote_frame else "DATA"
        extended = "EXT" if message.is_extended_id else "STD"
        data_hex = [hex(b) for b in message.data] if not message.is_remote_frame else []
        
        print(f"← Recv: [{msg_type}][{extended}] ID=0x{message.arbitration_id:X}, "
              f"DLC={message.dlc}, Data={data_hex}, Timestamp={message.timestamp:.3f}")


def message_callback(message: can.Message):
    """
    Example callback function for processing received messages
    
    Args:
        message: Received CAN message
    """
    # Process messages based on arbitration ID
    if message.arbitration_id == NODE_1_ID:
        # Handle Node 1 messages
        if len(message.data) >= 2:
            value = (message.data[0] << 8) | message.data[1]
            print(f"  ➜ Node 1 sensor value: {value}")
    
    elif message.arbitration_id == NODE_2_ID:
        # Handle Node 2 messages
        if len(message.data) >= 1:
            status = message.data[0]
            print(f"  ➜ Node 2 status: {status}")
    
    elif message.arbitration_id == NODE_3_ID:
        # Handle Node 3 messages
        print(f"  ➜ Node 3 response received")


def example_basic_send_receive(can_manager: CANManager):
    """Example 1: Basic send and receive"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Send and Receive")
    print("="*60)
    
    # Send some messages to different nodes
    can_manager.send_message(NODE_1_ID, [0x01, 0x02, 0x03, 0x04])
    time.sleep(0.1)
    
    can_manager.send_message(NODE_2_ID, [0xAA, 0xBB, 0xCC])
    time.sleep(0.1)
    
    can_manager.send_message(NODE_3_ID, [0xFF])
    time.sleep(0.1)
    
    # Receive messages with timeout
    print("\nWaiting for responses...")
    for _ in range(3):
        can_manager.receive_message(timeout=2.0)


def example_filtered_receive(can_manager: CANManager):
    """Example 2: Receive with filters"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Filtered Reception")
    print("="*60)
    
    # Send messages to multiple nodes
    can_manager.send_message(NODE_1_ID, [0x11, 0x22])
    can_manager.send_message(NODE_2_ID, [0x33, 0x44])
    can_manager.send_message(NODE_3_ID, [0x55, 0x66])
    
    # Only receive from NODE_1
    print("\nFiltering for NODE_1 only (0x101)...")
    can_manager.receive_with_filter(NODE_1_ID, mask=0x7FF, timeout=2.0)
    
    # Clear filters (set to receive all)
    can_manager.bus.set_filters(None)


def example_remote_frame(can_manager: CANManager):
    """Example 3: Remote frames"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Remote Transmission Request (RTR)")
    print("="*60)
    
    # Request data from nodes using RTR
    can_manager.send_remote_frame(NODE_1_ID, dlc=4)
    time.sleep(0.1)
    
    can_manager.send_remote_frame(NODE_2_ID, dlc=2)
    time.sleep(0.1)
    
    # Wait for responses
    print("\nWaiting for RTR responses...")
    for _ in range(2):
        can_manager.receive_message(timeout=2.0)


def example_periodic_messages(can_manager: CANManager):
    """Example 4: Periodic messages"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Periodic Messages")
    print("="*60)
    
    # Send periodic heartbeat to NODE_1
    heartbeat_task = can_manager.send_periodic_message(
        MASTER_ID, 
        [0xBE, 0xAT],  # Heartbeat pattern
        period=0.5     # Every 500ms
    )
    
    # Let it run for a few seconds
    print("Sending heartbeat for 3 seconds...")
    time.sleep(3)
    
    # Stop the periodic task
    if heartbeat_task:
        heartbeat_task.stop()
        print("→ Stopped periodic messages")


def example_continuous_reception(can_manager: CANManager):
    """Example 5: Continuous reception with callback"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Continuous Reception with Callback")
    print("="*60)
    
    # Start continuous reception
    can_manager.receive_continuous(callback=message_callback)
    
    # Send some test messages
    print("\nSending test messages...")
    time.sleep(0.5)
    
    can_manager.send_message(NODE_1_ID, [0x12, 0x34])  # 16-bit value: 0x1234
    time.sleep(0.2)
    
    can_manager.send_message(NODE_2_ID, [0x05])  # Status: 5
    time.sleep(0.2)
    
    can_manager.send_message(NODE_3_ID, [0x00, 0x00, 0x00, 0x00])
    time.sleep(0.2)
    
    # Continue receiving for a bit
    print("\nListening for 3 seconds...")
    time.sleep(3)
    
    # Stop continuous reception
    can_manager.running = False


def example_extended_frames(can_manager: CANManager):
    """Example 6: Extended CAN frames (29-bit IDs)"""
    print("\n" + "="*60)
    print("EXAMPLE 6: Extended Frame Format (29-bit ID)")
    print("="*60)
    
    # Send extended frame
    extended_id = 0x18FF5001  # 29-bit extended ID
    can_manager.send_message(
        extended_id,
        [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08],
        is_extended=True
    )
    
    time.sleep(0.1)
    can_manager.receive_message(timeout=2.0)


def main():
    """Main function demonstrating all examples"""
    print("="*60)
    print("CAN Bus Communication Examples")
    print("python-can library demonstration")
    print("="*60)
    
    # Create CAN manager
    can_manager = CANManager(CAN_INTERFACE, CAN_CHANNEL, BITRATE)
    
    # Connect to CAN bus
    if not can_manager.connect():
        print("Cannot proceed without CAN connection")
        return
    
    try:
        # Run examples
        example_basic_send_receive(can_manager)
        time.sleep(1)
        
        example_filtered_receive(can_manager)
        time.sleep(1)
        
        example_remote_frame(can_manager)
        time.sleep(1)
        
        example_periodic_messages(can_manager)
        time.sleep(1)
        
        example_continuous_reception(can_manager)
        time.sleep(1)
        
        example_extended_frames(can_manager)
        
        print("\n" + "="*60)
        print("All examples completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    finally:
        # Clean up
        can_manager.disconnect()


if __name__ == "__main__":
    main()
