"""
Ingestion Service Main Module
Main entry point for the data ingestion service.
"""


def main():
    """Main entry point for ingestion service."""
    pass


if __name__ == "__main__":
    main()

import asyncio
import json
import os
import paho.mqtt.client as mqtt
import asyncpg
from fastapi import FastAPI
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

DB_DSN = os.getenv("DB_DSN", "postgresql://postgres:password@localhost:5432/powergrid")
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))

app = FastAPI(title="Grid Ingestion Service")

# Prometheus metrics
INGEST_COUNT = Counter('mqtt_ingest_total', 'Total MQTT messages ingested')

# OpenTelemetry setup
provider = TracerProvider()
processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Global queue for MQTT messages
message_queue = asyncio.Queue()
db_pool = None

# MQTT client setup
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker")
    client.subscribe("grid/sensors/#")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        asyncio.run_coroutine_threadsafe(message_queue.put(payload), asyncio.get_event_loop())
    except Exception as e:
        print(f"Error processing message: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id SERIAL PRIMARY KEY,
                device_id TEXT,
                timestamp TIMESTAMPTZ,
                voltage DOUBLE PRECISION,
                current DOUBLE PRECISION,
                temperature DOUBLE PRECISION
            );
        """)
        await conn.execute("""
            SELECT create_hypertable('sensor_data', 'timestamp', if_not_exists => TRUE);
        """)

async def consume_queue():
    while True:
        batch = []
        while not message_queue.empty():
            batch.append(await message_queue.get())

        if batch:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany("""
                        INSERT INTO sensor_data (device_id, timestamp, voltage, current, temperature)
                        VALUES ($1, $2, $3, $4, $5);
                    """, [
                        (m["device_id"], m["timestamp"], m["voltage"], m["current"], m["temperature"]) 
                        for m in batch
                    ])
            INGEST_COUNT.inc(len(batch))
        await asyncio.sleep(2)

@app.get("/health")
async def health():
    return {"status": "ok", "queued_messages": message_queue.qsize()}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def start_mqtt():
    mqtt_client.connect(BROKER_HOST, BROKER_PORT, 60)
    mqtt_client.loop_start()

@app.on_event("startup")
async def startup_event():
    await init_db()
    await start_mqtt()
    asyncio.create_task(consume_queue())

@app.on_event("shutdown")
async def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    await db_pool.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
