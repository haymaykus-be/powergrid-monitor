import asyncio
import argparse
import json
import random
import sys
import time
from datetime import datetime
import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
SENSOR_COUNT = 1000

# Global state
client = None
use_mqtt = True
dry_run = False

def setup_mqtt_client(host=BROKER_HOST, port=BROKER_PORT):
    """Setup and connect MQTT client."""
    global client, use_mqtt, BROKER_HOST, BROKER_PORT
    
    BROKER_HOST = host
    BROKER_PORT = port
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    connected = False
    connection_error = None

    # Connection callbacks
    def on_connect(client, userdata, flags, reason_code, properties):
        nonlocal connected, connection_error
        if reason_code == 0:
            connected = True
            print(f"Connected to MQTT broker at {BROKER_HOST}:{BROKER_PORT}")
        else:
            connection_error = f"Failed to connect. Reason code: {reason_code}"
            print(f"Failed to connect to MQTT broker. Reason code: {reason_code}")

    def on_disconnect(client, userdata, reason_code, properties):
        nonlocal connected
        connected = False
        print(f"Disconnected from MQTT broker. Reason code: {reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Attempt to connect with error handling
    try:
        print(f"Connecting to MQTT broker at {BROKER_HOST}:{BROKER_PORT}...")
        client.connect(BROKER_HOST, BROKER_PORT, 60)
        client.loop_start()
        
        # Wait for connection to be established (max 5 seconds)
        for _ in range(50):
            if connected:
                return True
            if connection_error:
                break
            time.sleep(0.1)
        
        if not connected:
            print("Connection timeout.")
            client.loop_stop()
            client.disconnect()
            return False
            
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        if client:
            try:
                client.loop_stop()
                client.disconnect()
            except:
                pass
        return False
    
    return False

# Simulated sensor device
async def simulate_sensor(sensor_id: int):
    device_id = f"sensor_{sensor_id}"
    topic = f"grid/sensors/{device_id}"
    
    while True:
        timestamp = datetime.utcnow().isoformat()
        voltage = random.gauss(230, 2)  # ~230V nominal with ±2V noise
        current = random.gauss(4, 0.5)  # ~4A nominal
        temperature = random.gauss(35, 3)  # ~35°C
        
        # Inject anomalies (1% chance)
        if random.random() < 0.01:
            voltage += random.choice([-20, 25])  # sudden voltage drop/spike
            temperature += random.choice([10, -8])

        payload = {
            "device_id": device_id,
            "timestamp": timestamp,
            "voltage": round(voltage, 2),
            "current": round(current, 2),
            "temperature": round(temperature, 2)
        }

        if use_mqtt and client:
            try:
                result = client.publish(topic, json.dumps(payload))
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"Warning: Failed to publish message for {device_id}")
            except Exception as e:
                print(f"Error publishing message for {device_id}: {e}")
        else:
            # Dry-run mode: just print the data
            if dry_run or sensor_id < 5:  # Only print first 5 sensors to avoid spam
                print(f"[{topic}] {json.dumps(payload)}")
        
        await asyncio.sleep(random.uniform(1, 3))  # emulate varied reporting rate

async def main():
    global use_mqtt, dry_run
    
    parser = argparse.ArgumentParser(description='Power Grid Sensor Simulator')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Run in dry-run mode (no MQTT, prints data to console)')
    parser.add_argument('--sensors', type=int, default=SENSOR_COUNT,
                       help=f'Number of sensors to simulate (default: {SENSOR_COUNT})')
    parser.add_argument('--host', type=str, default=BROKER_HOST,
                       help=f'MQTT broker host (default: {BROKER_HOST})')
    parser.add_argument('--port', type=int, default=BROKER_PORT,
                       help=f'MQTT broker port (default: {BROKER_PORT})')
    
    args = parser.parse_args()
    dry_run = args.dry_run
    sensor_count = args.sensors
    
    if not dry_run:
        # Try to connect to MQTT broker
        use_mqtt = setup_mqtt_client(args.host, args.port)
        if not use_mqtt:
            print("\n⚠️  MQTT broker not available. Switching to dry-run mode.")
            print("   To use MQTT, start a broker with: docker compose up -d mqtt-broker")
            print("   Or run with --dry-run to suppress this message.\n")
            dry_run = True
            use_mqtt = False
    else:
        use_mqtt = False
        print("Running in dry-run mode (no MQTT broker required)")
    
    print(f"Starting simulation for {sensor_count} sensors...")
    tasks = [simulate_sensor(i) for i in range(sensor_count)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down simulator...")
        if client:
            client.loop_stop()
            client.disconnect()
