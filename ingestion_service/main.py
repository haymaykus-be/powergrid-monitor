import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import Counter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.database import Database
from common.models import SensorData
from common.telemetry import TelemetryHandler
from ingestion_service.mqtt_handler import MQTTHandler
from ingestion_service.routes import (
    health_router,
    metrics_router,
    devices_router,
    data_router,
    alerts_router
)
from ingestion_service import state

# Configuration
DB_DSN = os.getenv("DB_DSN")
BROKER_HOST = os.getenv("BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("BROKER_PORT", "1883"))

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    # Initialize database
    state.db = Database(dsn=DB_DSN)
    await state.db.connect()
    print("Database connected and schema initialized")
    
    # Initialize MQTT handler
    state.mqtt_handler = MQTTHandler(host=BROKER_HOST, port=BROKER_PORT)
    loop = asyncio.get_running_loop()
    state.mqtt_handler.set_message_callback(process_mqtt_message, event_loop=loop)
    
    if state.mqtt_handler.connect():
        print("MQTT handler connected")
    else:
        print("Warning: MQTT handler failed to connect")
    
    # Start queue consumer
    asyncio.create_task(consume_queue())
    print("Ingestion service started")
    
    yield
    
    # Shutdown
    if state.mqtt_handler:
        state.mqtt_handler.disconnect()
    if state.db:
        await state.db.close()
    print("Ingestion service stopped")

# FastAPI app
app = FastAPI(title="Grid Ingestion Service", lifespan=lifespan)

# Include API routes
app.include_router(health_router)
app.include_router(metrics_router)
app.include_router(devices_router)
app.include_router(data_router)
app.include_router(alerts_router)

# Prometheus metrics - check if already registered to avoid duplication
from prometheus_client import REGISTRY

def get_or_create_counter(name, description):
    """Get existing counter or create new one."""
    try:
        # Try to get existing metric
        collector = REGISTRY._names_to_collectors.get(name)
        if collector:
            return collector
    except (KeyError, AttributeError):
        pass
    # Create new counter
    return Counter(name, description)

INGEST_COUNT = get_or_create_counter('mqtt_ingest_total', 'Total MQTT messages ingested')
INGEST_ERROR_COUNT = get_or_create_counter('mqtt_ingest_errors_total', 'Total MQTT message processing errors')
VALIDATION_ERROR_COUNT = get_or_create_counter('validation_errors_total', 'Total validation errors')

# OpenTelemetry setup - only set if not already set
# Console exporter is disabled by default (set ENABLE_TRACING=1 to enable)
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "0").lower() in ("1", "true", "yes")

try:
    current_provider = trace.get_tracer_provider()
    # Check if it's already a TracerProvider (not NoOp)
    if not hasattr(current_provider, 'add_span_processor'):
        if ENABLE_TRACING:
            from opentelemetry.sdk.resources import Resource
            provider = TracerProvider(
                resource=Resource.create({"service.name": "powergrid-ingestion"})
            )
            processor = SimpleSpanProcessor(ConsoleSpanExporter())
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
except:
    # No provider set, create one
    if ENABLE_TRACING:
        from opentelemetry.sdk.resources import Resource
        provider = TracerProvider(
            resource=Resource.create({"service.name": "powergrid-ingestion"})
        )
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Global components
telemetry_handler = TelemetryHandler()

# Initialize shared state
state.message_queue = asyncio.Queue()


async def process_mqtt_message(sensor_data: SensorData):
    """Process incoming MQTT message."""
    with tracer.start_as_current_span("process_mqtt_message") as span:
        span.set_attribute("device_id", sensor_data.device_id)
        
        # Validate data
        is_valid, error_msg = telemetry_handler.validate(sensor_data)
        if not is_valid:
            VALIDATION_ERROR_COUNT.inc()
            span.set_attribute("validation_error", error_msg)
            print(f"Validation error for {sensor_data.device_id}: {error_msg}")
            return
        
        # Queue for batch processing
        await state.message_queue.put(sensor_data)


async def consume_queue():
    """Consume messages from queue and batch insert to database."""
    batch = []
    batch_size = 100
    batch_timeout = 2.0  # seconds
    
    while True:
        try:
            # Wait for messages with timeout
            try:
                sensor_data = await asyncio.wait_for(state.message_queue.get(), timeout=batch_timeout)
                batch.append(sensor_data)
            except asyncio.TimeoutError:
                pass  # Timeout reached, process batch if any
            
            # Process batch if we have enough messages or timeout occurred
            if len(batch) >= batch_size or (batch and state.message_queue.empty()):
                if batch:
                    with tracer.start_as_current_span("batch_insert") as span:
                        span.set_attribute("batch_size", len(batch))
                        try:
                            await state.db.insert_batch(batch)
                            INGEST_COUNT.inc(len(batch))
                            print(f"Inserted batch of {len(batch)} records")
                        except Exception as e:
                            INGEST_ERROR_COUNT.inc(len(batch))
                            span.record_exception(e)
                            print(f"Error inserting batch: {e}")
                        finally:
                            batch.clear()
        except Exception as e:
            print(f"Error in consume_queue: {e}")
            await asyncio.sleep(1)


def main():
    """Main entry point for ingestion service."""
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)


if __name__ == "__main__":
    main()
