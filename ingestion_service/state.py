"""Shared application state."""
from typing import Optional
from common.database import Database
from ingestion_service.mqtt_handler import MQTTHandler
import asyncio

# Global application state
db: Optional[Database] = None
mqtt_handler: Optional[MQTTHandler] = None
message_queue: Optional[asyncio.Queue] = None

