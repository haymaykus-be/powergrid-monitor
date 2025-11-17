from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SensorData:
    """Sensor data model."""
    device_id: str
    timestamp: datetime
    voltage: float
    current: float
    temperature: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "voltage": self.voltage,
            "current": self.current,
            "temperature": self.temperature
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SensorData":
        """Create from dictionary."""
        timestamp = data["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        return cls(
            device_id=data["device_id"],
            timestamp=timestamp,
            voltage=float(data["voltage"]),
            current=float(data["current"]),
            temperature=float(data["temperature"])
        )


@dataclass
class AnomalyAlert:
    """Anomaly detection alert."""
    device_id: str
    timestamp: datetime
    metric: str  # 'voltage', 'current', or 'temperature'
    value: float
    expected_range: tuple[float, float]
    severity: str  # 'low', 'medium', 'high'
    description: str


@dataclass
class MaintenancePrediction:
    """Predictive maintenance prediction."""
    device_id: str
    predicted_failure_date: Optional[datetime]
    confidence: float  # 0.0 to 1.0
    risk_factors: list[str]
    recommended_actions: list[str]


if __name__ == "__main__":
    pass

