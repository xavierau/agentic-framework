#!/usr/bin/env python3
"""
Quick test script to verify the InMemoryMessageBus works correctly.
"""
import asyncio
import sys
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agentic_framework.messaging.memory_bus import InMemoryMessageBus
from agentic_framework.messaging.base import Message

async def test_memory_bus():
    """Test the InMemoryMessageBus functionality."""
    print("🧪 Testing InMemoryMessageBus")
    print("=" * 30)
    
    bus = InMemoryMessageBus()
    messages_received = []
    
    # Handler function
    async def handle_message(message):
        print(f"📨 Received message: {message.message_type} from {message.sender_id}")
        messages_received.append(message)
    
    try:
        # Connect to the bus
        print("🔗 Connecting to message bus...")
        await bus.connect()
        print("✅ Connected successfully")
        
        # Subscribe to a channel
        print("📡 Subscribing to test channel...")
        await bus.subscribe("test.channel", handle_message)
        print("✅ Subscribed successfully")
        
        # Publish a message
        print("📤 Publishing test message...")
        test_message = Message.create(
            sender_id="test-sender",
            message_type="test.message",
            content={"data": "Hello World!"}
        )
        await bus.publish("test.channel", test_message)
        
        # Wait a bit for message processing
        print("⏳ Waiting for message processing...")
        await asyncio.sleep(0.5)
        
        # Check if message was received
        if messages_received:
            print("✅ Message received successfully!")
            print(f"   Message ID: {messages_received[0].id}")
            print(f"   Content: {messages_received[0].content}")
        else:
            print("❌ No messages received")
            return False
        
        # Test stats
        stats = bus.get_stats()
        print(f"\n📊 Bus Stats:")
        print(f"   Connected: {stats['connected']}")
        print(f"   Channels: {stats['channels']}")
        print(f"   Handlers: {stats['total_handlers']}")
        print(f"   Queue Size: {stats['queue_size']}")
        
        # Wait for queue to be empty
        print("⏳ Waiting for queue to empty...")
        empty = await bus.wait_for_empty_queue(timeout=2.0)
        if empty:
            print("✅ Queue emptied successfully")
        else:
            print("⚠️ Queue did not empty in time")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        # Disconnect
        print("🔌 Disconnecting...")
        await bus.disconnect()
        print("✅ Disconnected")

if __name__ == "__main__":
    success = asyncio.run(test_memory_bus())
    if success:
        print("\n🎉 InMemoryMessageBus test PASSED!")
    else:
        print("\n💥 InMemoryMessageBus test FAILED!")
        sys.exit(1)