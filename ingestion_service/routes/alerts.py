"""Anomaly alerts API routes."""
import sys
import os
from pathlib import Path
from typing import Optional
import json
from fastapi import APIRouter, Query, HTTPException

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
@router.get("/")
async def get_alerts(
    limit: int = Query(default=10, ge=1, le=100, description="Number of alerts to retrieve")
):
    """Get recent anomaly alerts from Redis."""
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Get alerts from Redis list (without removing them)
        alerts = []
        for i in range(limit):
            alert_json = r.lindex("alerts:anomalies", i)
            if alert_json:
                try:
                    alerts.append(json.loads(alert_json))
                except json.JSONDecodeError:
                    continue
            else:
                break
        
        return {
            "count": len(alerts),
            "alerts": alerts
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Redis client not available")
    except Exception as e:
        # If Redis is not available, return empty list
        return {
            "count": 0,
            "alerts": [],
            "note": "Redis not available or no alerts found"
        }


@router.get("/count")
async def get_alert_count():
    """Get the count of alerts in Redis."""
    try:
        import redis
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        r = redis.from_url(redis_url, decode_responses=True)
        
        count = r.llen("alerts:anomalies")
        return {
            "count": count
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="Redis client not available")
    except Exception as e:
        return {
            "count": 0,
            "note": "Redis not available"
        }

