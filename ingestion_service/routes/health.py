"""Health check API routes."""
import sys
from pathlib import Path
from fastapi import APIRouter

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ingestion_service import state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "queued_messages": state.message_queue.qsize() if state.message_queue else 0,
        "mqtt_connected": state.mqtt_handler.is_connected() if state.mqtt_handler else False,
        "database_connected": state.db.pool is not None if state.db else False
    }

