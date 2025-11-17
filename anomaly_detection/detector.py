"""
Anomaly Detection Module
Detects anomalies in power grid sensor data.
"""
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta
import statistics

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.models import SensorData, AnomalyAlert
from common.database import Database


class AnomalyDetector:
    """Detects anomalies in sensor data using statistical methods."""
    
    # Thresholds for anomaly detection
    VOLTAGE_NOMINAL = 230.0
    VOLTAGE_STD_DEV = 5.0
    VOLTAGE_ANOMALY_THRESHOLD = 3.0  # 3 standard deviations
    
    CURRENT_NOMINAL = 4.0
    CURRENT_STD_DEV = 1.0
    CURRENT_ANOMALY_THRESHOLD = 3.0
    
    TEMPERATURE_NOMINAL = 35.0
    TEMPERATURE_STD_DEV = 5.0
    TEMPERATURE_ANOMALY_THRESHOLD = 3.0
    
    # Absolute safety ranges
    VOLTAGE_MIN_SAFE = 200.0
    VOLTAGE_MAX_SAFE = 250.0
    TEMPERATURE_MAX_SAFE = 70.0
    
    def __init__(self, database: Optional[Database] = None):
        """Initialize anomaly detector.
        
        Args:
            database: Optional database instance for historical data analysis
        """
        self.database = database
    
    def detect_anomaly(self, sensor_data: SensorData, 
                      historical_data: Optional[List[SensorData]] = None) -> Optional[AnomalyAlert]:
        """Detect anomalies in a single sensor reading.
        
        Args:
            sensor_data: Current sensor reading
            historical_data: Optional historical data for context
        
        Returns:
            AnomalyAlert if anomaly detected, None otherwise
        """
        alerts = []
        
        # Check voltage
        voltage_alert = self._check_voltage(sensor_data, historical_data)
        if voltage_alert:
            alerts.append(voltage_alert)
        
        # Check current
        current_alert = self._check_current(sensor_data, historical_data)
        if current_alert:
            alerts.append(current_alert)
        
        # Check temperature
        temp_alert = self._check_temperature(sensor_data, historical_data)
        if temp_alert:
            alerts.append(temp_alert)
        
        # Return the most severe alert if any
        if alerts:
            # Sort by severity (high > medium > low)
            severity_order = {'high': 3, 'medium': 2, 'low': 1}
            alerts.sort(key=lambda a: severity_order.get(a.severity, 0), reverse=True)
            return alerts[0]
        
        return None
    
    def _check_voltage(self, data: SensorData, historical: Optional[List[SensorData]]) -> Optional[AnomalyAlert]:
        """Check voltage for anomalies."""
        voltage = data.voltage
        
        # Check absolute safety limits
        if voltage < self.VOLTAGE_MIN_SAFE or voltage > self.VOLTAGE_MAX_SAFE:
            severity = 'high'
            description = f"Critical voltage {voltage}V outside safe range [{self.VOLTAGE_MIN_SAFE}, {self.VOLTAGE_MAX_SAFE}]V"
        else:
            # Statistical check
            if historical:
                voltages = [d.voltage for d in historical]
                mean = statistics.mean(voltages)
                std_dev = statistics.stdev(voltages) if len(voltages) > 1 else self.VOLTAGE_STD_DEV
            else:
                mean = self.VOLTAGE_NOMINAL
                std_dev = self.VOLTAGE_STD_DEV
            
            deviation = abs(voltage - mean) / std_dev if std_dev > 0 else 0
            
            if deviation >= self.VOLTAGE_ANOMALY_THRESHOLD:
                if deviation >= 4.0:
                    severity = 'high'
                elif deviation >= 3.0:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                description = f"Voltage {voltage}V deviates {deviation:.2f}σ from mean {mean:.2f}V"
            else:
                return None
        
        return AnomalyAlert(
            device_id=data.device_id,
            timestamp=data.timestamp,
            metric='voltage',
            value=voltage,
            expected_range=(self.VOLTAGE_MIN_SAFE, self.VOLTAGE_MAX_SAFE),
            severity=severity,
            description=description
        )
    
    def _check_current(self, data: SensorData, historical: Optional[List[SensorData]]) -> Optional[AnomalyAlert]:
        """Check current for anomalies."""
        current = data.current
        
        if historical:
            currents = [d.current for d in historical]
            mean = statistics.mean(currents)
            std_dev = statistics.stdev(currents) if len(currents) > 1 else self.CURRENT_STD_DEV
        else:
            mean = self.CURRENT_NOMINAL
            std_dev = self.CURRENT_STD_DEV
        
        deviation = abs(current - mean) / std_dev if std_dev > 0 else 0
        
        if deviation >= self.CURRENT_ANOMALY_THRESHOLD:
            if deviation >= 4.0:
                severity = 'high'
            elif deviation >= 3.0:
                severity = 'medium'
            else:
                severity = 'low'
            
            description = f"Current {current}A deviates {deviation:.2f}σ from mean {mean:.2f}A"
            
            return AnomalyAlert(
                device_id=data.device_id,
                timestamp=data.timestamp,
                metric='current',
                value=current,
                expected_range=(0.0, 10.0),
                severity=severity,
                description=description
            )
        
        return None
    
    def _check_temperature(self, data: SensorData, historical: Optional[List[SensorData]]) -> Optional[AnomalyAlert]:
        """Check temperature for anomalies."""
        temperature = data.temperature
        
        # Check absolute safety limit
        if temperature > self.TEMPERATURE_MAX_SAFE:
            severity = 'high'
            description = f"Critical temperature {temperature}°C exceeds safe limit {self.TEMPERATURE_MAX_SAFE}°C"
        else:
            # Statistical check
            if historical:
                temperatures = [d.temperature for d in historical]
                mean = statistics.mean(temperatures)
                std_dev = statistics.stdev(temperatures) if len(temperatures) > 1 else self.TEMPERATURE_STD_DEV
            else:
                mean = self.TEMPERATURE_NOMINAL
                std_dev = self.TEMPERATURE_STD_DEV
            
            deviation = abs(temperature - mean) / std_dev if std_dev > 0 else 0
            
            if deviation >= self.TEMPERATURE_ANOMALY_THRESHOLD:
                if deviation >= 4.0 or temperature > 60:
                    severity = 'high'
                elif deviation >= 3.0:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                description = f"Temperature {temperature}°C deviates {deviation:.2f}σ from mean {mean:.2f}°C"
            else:
                return None
        
        return AnomalyAlert(
            device_id=data.device_id,
            timestamp=data.timestamp,
            metric='temperature',
            value=temperature,
            expected_range=(0.0, self.TEMPERATURE_MAX_SAFE),
            severity=severity,
            description=description
        )
    
    async def detect_anomalies_batch(self, sensor_data_list: List[SensorData]) -> List[AnomalyAlert]:
        """Detect anomalies in a batch of sensor readings.
        
        Uses historical data from database if available.
        """
        alerts = []
        
        # Group by device_id for historical context
        device_groups = {}
        for data in sensor_data_list:
            if data.device_id not in device_groups:
                device_groups[data.device_id] = []
            device_groups[data.device_id].append(data)
        
        for device_id, device_data in device_groups.items():
            # Get historical data for this device if database available
            historical = None
            if self.database:
                try:
                    historical = await self.database.get_recent_data(device_id=device_id, limit=100)
                except Exception as e:
                    print(f"Error fetching historical data for {device_id}: {e}")
            
            # Detect anomalies for each reading
            for data in device_data:
                alert = self.detect_anomaly(data, historical)
                if alert:
                    alerts.append(alert)
                    # Add current reading to historical context for next iteration
                    if historical is not None:
                        historical.append(data)
                        # Keep only recent data
                        historical = historical[-100:]
        
        return alerts


if __name__ == "__main__":
    pass


