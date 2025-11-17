from typing import List, Optional
from datetime import datetime, timedelta, timezone
from .models import SensorData


class TelemetryHandler:
    """Handles telemetry data processing and validation."""
    
    # Normal operating ranges
    VOLTAGE_MIN = 200.0
    VOLTAGE_MAX = 250.0
    CURRENT_MIN = 0.0
    CURRENT_MAX = 10.0
    TEMPERATURE_MIN = 0.0
    TEMPERATURE_MAX = 80.0
    
    def __init__(self):
        """Initialize telemetry handler."""
        pass
    
    def validate(self, data: SensorData) -> tuple[bool, Optional[str]]:
        """Validate sensor data.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.VOLTAGE_MIN <= data.voltage <= self.VOLTAGE_MAX:
            return False, f"Voltage {data.voltage}V out of range [{self.VOLTAGE_MIN}, {self.VOLTAGE_MAX}]"
        
        if not self.CURRENT_MIN <= data.current <= self.CURRENT_MAX:
            return False, f"Current {data.current}A out of range [{self.CURRENT_MIN}, {self.CURRENT_MAX}]"
        
        if not self.TEMPERATURE_MIN <= data.temperature <= self.TEMPERATURE_MAX:
            return False, f"Temperature {data.temperature}°C out of range [{self.TEMPERATURE_MIN}, {self.TEMPERATURE_MAX}]"
        
        return True, None
    
    def calculate_statistics(self, data_list: List[SensorData]) -> dict:
        """Calculate statistics for a list of sensor data.
        
        Returns:
            Dictionary with statistics for each metric
        """
        if not data_list:
            return {}
        
        voltages = [d.voltage for d in data_list]
        currents = [d.current for d in data_list]
        temperatures = [d.temperature for d in data_list]
        
        def stats(values: List[float]) -> dict:
            return {
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'count': len(values)
            }
        
        return {
            'voltage': stats(voltages),
            'current': stats(currents),
            'temperature': stats(temperatures)
        }
    
    def filter_by_time_range(self, data_list: List[SensorData], 
                            start_time: datetime, 
                            end_time: datetime) -> List[SensorData]:
        """Filter sensor data by time range."""
        return [
            d for d in data_list
            if start_time <= d.timestamp <= end_time
        ]
    
    def filter_by_device(self, data_list: List[SensorData], device_id: str) -> List[SensorData]:
        """Filter sensor data by device ID."""
        return [d for d in data_list if d.device_id == device_id]
    
    def get_recent_data(self, data_list: List[SensorData], 
                       hours: int = 24) -> List[SensorData]:
        """Get data from the last N hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [d for d in data_list if d.timestamp >= cutoff]


if __name__ == "__main__":
    pass

