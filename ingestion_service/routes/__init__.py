"""API Routes Package."""

from .health import router as health_router
from .metrics import router as metrics_router
from .devices import router as devices_router
from .data import router as data_router
from .alerts import router as alerts_router

__all__ = [
    "health_router",
    "metrics_router",
    "devices_router",
    "data_router",
    "alerts_router"
]

