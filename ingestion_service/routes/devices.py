"""Device and sensor data API routes."""
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ingestion_service import state
from common.models import SensorData

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceStatsResponse(BaseModel):
    """Device statistics response model."""
    device_id: str
    hours: int
    voltage: dict
    current: dict
    temperature: dict


@router.get("")
@router.get("/")
async def list_devices(limit: int = Query(default=100, ge=1, le=1000)):
    """List all unique devices with recent activity."""
    if not state.db:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        async with state.db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT DISTINCT device_id, MAX(timestamp) as last_seen
                FROM sensor_data
                GROUP BY device_id
                ORDER BY last_seen DESC
                LIMIT $1;
            """, limit)
            
            devices = [
                {
                    "device_id": row["device_id"],
                    "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None
                }
                for row in rows
            ]
            
            return {
                "devices": devices,
                "count": len(devices)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching devices: {str(e)}")


@router.get("/{device_id}")
async def get_device_data(
    device_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    hours: Optional[int] = Query(default=None, ge=1, le=720)
):
    """Get recent sensor data for a specific device."""
    if not state.db:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        data = await state.db.get_recent_data(device_id=device_id, limit=limit)
        
        # Filter by hours if specified
        if hours:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            data = [d for d in data if d.timestamp >= cutoff]
        
        return {
            "device_id": device_id,
            "count": len(data),
            "data": [d.to_dict() for d in data]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching device data: {str(e)}")


@router.get("/{device_id}/stats")
async def get_device_stats(
    device_id: str,
    hours: int = Query(default=24, ge=1, le=720)
):
    """Get statistics for a device over the last N hours."""
    if not state.db:
        raise HTTPException(status_code=503, detail="Database not connected")
    
    try:
        stats = await state.db.get_device_stats(device_id=device_id, hours=hours)
        
        if not stats:
            raise HTTPException(status_code=404, detail=f"No data found for device {device_id}")
        
        return DeviceStatsResponse(
            device_id=device_id,
            hours=hours,
            voltage=stats.get("voltage", {}),
            current=stats.get("current", {}),
            temperature=stats.get("temperature", {})
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching device stats: {str(e)}")

