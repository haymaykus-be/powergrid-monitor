"""
Predictive Maintenance Module
Predicts maintenance needs for power grid equipment.
"""
import sys
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import statistics

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.models import SensorData, MaintenancePrediction
from common.database import Database


class MaintenancePredictor:
    """Predicts maintenance requirements based on sensor data trends."""
    
    # Thresholds for maintenance prediction
    TEMPERATURE_TREND_THRESHOLD = 0.5  # °C per day increase
    VOLTAGE_VARIANCE_THRESHOLD = 10.0  # High variance indicates issues
    CURRENT_SPIKE_THRESHOLD = 2.0  # Current spikes indicate load issues
    
    # Maintenance intervals (days)
    PREVENTIVE_MAINTENANCE_INTERVAL = 90  # Recommended every 90 days
    CRITICAL_THRESHOLD_DAYS = 30  # Critical if predicted within 30 days
    
    def __init__(self, database: Optional[Database] = None):
        """Initialize maintenance predictor.
        
        Args:
            database: Optional database instance for historical data analysis
        """
        self.database = database
    
    async def predict_maintenance(self, device_id: str, 
                                 lookback_days: int = 30) -> MaintenancePrediction:
        """Predict maintenance needs for a device.
        
        Args:
            device_id: Device identifier
            lookback_days: Number of days of historical data to analyze
        
        Returns:
            MaintenancePrediction with risk assessment
        """
        # Get historical data
        historical_data = []
        if self.database:
            try:
                historical_data = await self.database.get_recent_data(device_id=device_id, limit=1000)
                # Filter to lookback period
                cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
                historical_data = [d for d in historical_data if d.timestamp >= cutoff]
            except Exception as e:
                print(f"Error fetching historical data for {device_id}: {e}")
        
        if not historical_data:
            return MaintenancePrediction(
                device_id=device_id,
                predicted_failure_date=None,
                confidence=0.0,
                risk_factors=["Insufficient historical data"],
                recommended_actions=["Collect more sensor data for analysis"]
            )
        
        # Analyze trends and patterns
        risk_factors = []
        recommended_actions = []
        confidence = 0.0
        predicted_failure_date = None
        
        # Analyze temperature trend
        temp_trend = self._analyze_temperature_trend(historical_data)
        if temp_trend['increasing'] and temp_trend['rate'] > self.TEMPERATURE_TREND_THRESHOLD:
            risk_factors.append(f"Temperature increasing at {temp_trend['rate']:.2f}°C/day")
            recommended_actions.append("Check cooling systems and ventilation")
            confidence += 0.3
        
        # Analyze voltage stability
        voltage_stability = self._analyze_voltage_stability(historical_data)
        if voltage_stability['variance'] > self.VOLTAGE_VARIANCE_THRESHOLD:
            risk_factors.append(f"High voltage variance ({voltage_stability['variance']:.2f}V)")
            recommended_actions.append("Inspect electrical connections and components")
            confidence += 0.2
        
        # Analyze current patterns
        current_analysis = self._analyze_current_patterns(historical_data)
        if current_analysis['has_spikes']:
            risk_factors.append("Detected current spikes indicating load issues")
            recommended_actions.append("Review load distribution and circuit protection")
            confidence += 0.2
        
        # Check for anomalies in recent data
        recent_data = [d for d in historical_data 
                      if d.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)]
        if recent_data:
            recent_temp = statistics.mean([d.temperature for d in recent_data])
            if recent_temp > 60:
                risk_factors.append(f"High recent temperature ({recent_temp:.1f}°C)")
                recommended_actions.append("Immediate thermal inspection recommended")
                confidence += 0.3
        
        # Calculate predicted failure date based on trends
        if temp_trend['increasing'] and temp_trend['rate'] > 0:
            # Simple linear extrapolation: if temp continues increasing, estimate when it hits critical threshold
            current_temp = historical_data[-1].temperature if historical_data else 35.0
            critical_temp = 70.0
            days_to_critical = (critical_temp - current_temp) / temp_trend['rate'] if temp_trend['rate'] > 0 else None
            
            if days_to_critical and 0 < days_to_critical < 365:
                predicted_failure_date = datetime.now(timezone.utc) + timedelta(days=int(days_to_critical))
                confidence = min(confidence + 0.2, 0.9)
        
        # If no specific prediction, use preventive maintenance schedule
        if predicted_failure_date is None:
            # Check last maintenance (would need maintenance log in real system)
            # For now, recommend based on risk factors
            if confidence > 0.5:
                predicted_failure_date = datetime.now(timezone.utc) + timedelta(days=self.CRITICAL_THRESHOLD_DAYS)
            else:
                predicted_failure_date = datetime.now(timezone.utc) + timedelta(days=self.PREVENTIVE_MAINTENANCE_INTERVAL)
                recommended_actions.append("Schedule routine preventive maintenance")
        
        # Cap confidence
        confidence = min(confidence, 0.95)
        
        # Add general recommendations if no specific issues
        if not risk_factors:
            risk_factors.append("No significant risk factors detected")
            recommended_actions.append("Continue routine monitoring")
            confidence = 0.1
        
        return MaintenancePrediction(
            device_id=device_id,
            predicted_failure_date=predicted_failure_date,
            confidence=confidence,
            risk_factors=risk_factors,
            recommended_actions=recommended_actions
        )
    
    def _analyze_temperature_trend(self, data: List[SensorData]) -> dict:
        """Analyze temperature trend over time."""
        if len(data) < 2:
            return {'increasing': False, 'rate': 0.0}
        
        # Sort by timestamp
        sorted_data = sorted(data, key=lambda x: x.timestamp)
        
        # Calculate daily average temperatures
        daily_temps = {}
        for d in sorted_data:
            day = d.timestamp.date()
            if day not in daily_temps:
                daily_temps[day] = []
            daily_temps[day].append(d.temperature)
        
        daily_avgs = {day: statistics.mean(temps) for day, temps in daily_temps.items()}
        
        if len(daily_avgs) < 2:
            return {'increasing': False, 'rate': 0.0}
        
        # Calculate trend (simple linear regression slope)
        days = sorted(daily_avgs.keys())
        temps = [daily_avgs[day] for day in days]
        
        # Calculate average daily change
        temp_changes = []
        for i in range(1, len(temps)):
            days_diff = (days[i] - days[i-1]).days
            if days_diff > 0:
                temp_changes.append((temps[i] - temps[i-1]) / days_diff)
        
        if temp_changes:
            avg_rate = statistics.mean(temp_changes)
            return {'increasing': avg_rate > 0, 'rate': avg_rate}
        
        return {'increasing': False, 'rate': 0.0}
    
    def _analyze_voltage_stability(self, data: List[SensorData]) -> dict:
        """Analyze voltage stability (variance)."""
        if not data:
            return {'variance': 0.0, 'mean': 0.0}
        
        voltages = [d.voltage for d in data]
        mean = statistics.mean(voltages)
        variance = statistics.variance(voltages) if len(voltages) > 1 else 0.0
        
        return {'variance': variance, 'mean': mean}
    
    def _analyze_current_patterns(self, data: List[SensorData]) -> dict:
        """Analyze current patterns for spikes."""
        if not data:
            return {'has_spikes': False, 'max_current': 0.0}
        
        currents = [d.current for d in data]
        mean = statistics.mean(currents)
        std_dev = statistics.stdev(currents) if len(currents) > 1 else 0.0
        
        # Check for spikes (values > mean + 2*std_dev)
        threshold = mean + 2 * std_dev if std_dev > 0 else mean + self.CURRENT_SPIKE_THRESHOLD
        has_spikes = any(c > threshold for c in currents)
        
        return {
            'has_spikes': has_spikes,
            'max_current': max(currents),
            'mean': mean,
            'std_dev': std_dev
        }
    
    async def predict_batch(self, device_ids: List[str]) -> List[MaintenancePrediction]:
        """Predict maintenance for multiple devices."""
        predictions = []
        for device_id in device_ids:
            prediction = await self.predict_maintenance(device_id)
            predictions.append(prediction)
        return predictions


if __name__ == "__main__":
    pass


