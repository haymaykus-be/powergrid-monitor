import asyncio
import json
import sys
from pathlib import Path
import paho.mqtt.client as mqtt
from typing import Callable, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.models import SensorData


class MQTTHandler:
    """Handles MQTT connections and message processing."""
    
    def __init__(self, host: str = "localhost", port: int = 1883, topic: str = "grid/sensors/#"):
        """Initialize MQTT handler.
        
        Args:
            host: MQTT broker host
            port: MQTT broker port
            topic: Topic pattern to subscribe to
        """
        self.host = host
        self.port = port
        self.topic = topic
        self.client: Optional[mqtt.Client] = None
        self.message_callback: Optional[Callable[[SensorData], None]] = None
        self.connected = False
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None
    
    def set_message_callback(self, callback: Callable[[SensorData], None], event_loop: Optional[asyncio.AbstractEventLoop] = None):
        """Set callback function for received messages.
        
        Args:
            callback: Async callback function for processing messages
            event_loop: Optional event loop reference (will try to get current if not provided)
        """
        self.message_callback = callback
        if event_loop:
            self.event_loop = event_loop
        else:
            try:
                self.event_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass  # Will try to get it when message arrives
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Handle MQTT connection."""
        if reason_code == 0:
            self.connected = True
            print(f"Connected to MQTT broker at {self.host}:{self.port}")
            client.subscribe(self.topic)
            print(f"Subscribed to topic: {self.topic}")
        else:
            print(f"Failed to connect to MQTT broker. Reason code: {reason_code}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, reason_code, properties):
        """Handle MQTT disconnection."""
        self.connected = False
        print(f"Disconnected from MQTT broker. Reason code: {reason_code}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            payload = json.loads(msg.payload.decode())
            sensor_data = SensorData.from_dict(payload)
            
            if self.message_callback:
                # Get event loop (MQTT callbacks run in separate thread)
                loop = self.event_loop
                if loop is None:
                    try:
                        # Try to get the running loop (won't work from MQTT thread)
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        # Get the event loop from the main thread
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            print("Warning: No event loop available for MQTT callback")
                            return
                
                # Schedule callback in event loop using thread-safe method
                if loop.is_running():
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._async_callback(sensor_data))
                    )
                else:
                    # Loop not running, schedule it
                    asyncio.run_coroutine_threadsafe(
                        self._async_callback(sensor_data), loop
                    )
        except json.JSONDecodeError as e:
            print(f"Error decoding MQTT message: {e}")
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    async def _async_callback(self, sensor_data: SensorData):
        """Async wrapper for message callback."""
        if self.message_callback:
            if asyncio.iscoroutinefunction(self.message_callback):
                await self.message_callback(sensor_data)
            else:
                self.message_callback(sensor_data)
    
    def connect(self):
        """Connect to MQTT broker."""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def is_connected(self) -> bool:
        """Check if connected to MQTT broker."""
        return self.connected


if __name__ == "__main__":
    pass

