"""Sensor data query API routes."""
import sys
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, HTTPException

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ingestion_service import state
from common.models import SensorData

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("")
@router.get("/")
async def query_data(
    device_id: Optional[str] = Query(default=None, description="Filter by device ID"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records"),
    hours: Optional[int] = Query(default=None, ge=1, le=720, description="Filter by last N hours"),
    start_time: Optional[str] = Query(default=None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(default=None, description="End time (ISO format)")
):
    """Query sensor data with optional filters."""
    if not state.db:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        # Get data from database
        data = await state.db.get_recent_data(device_id=device_id, limit=limit * 2)  # Get more to filter
        
        # Apply time filters
        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            data = [d for d in data if d.timestamp >= cutoff]
        
        if start_time:
            try:
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                data = [d for d in data if d.timestamp >= start]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_time format. Use ISO format.")
        
        if end_time:
            try:
                end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                data = [d for d in data if d.timestamp <= end]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_time format. Use ISO format.")
        
        # Limit results
        data = data[:limit]
        
        return {
            "count": len(data),
            "filters": {
                "device_id": device_id,
                "hours": hours,
                "start_time": start_time,
                "end_time": end_time
            },
            "data": [d.to_dict() for d in data]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying data: {str(e)}")

