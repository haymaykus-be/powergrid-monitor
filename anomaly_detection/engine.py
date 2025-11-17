"""
Anomaly Detection Engine
Uses IsolationForest to detect anomalies in sensor data from TimescaleDB.
Publishes alerts to Redis.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import redis.asyncio as aioredis

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from common.database import Database
from common.models import SensorData, AnomalyAlert


class AnomalyDetectionEngine:
    """Anomaly detection engine using IsolationForest."""
    
    def __init__(self, 
                 database: Database,
                 redis_client: Optional[aioredis.Redis] = None,
                 contamination: float = 0.1,
                 lookback_hours: int = 24,
                 batch_size: int = 1000):
        """Initialize anomaly detection engine.
        
        Args:
            database: Database instance for fetching sensor data
            redis_client: Redis client for publishing alerts
            contamination: Expected proportion of outliers (0.0 to 0.5)
            lookback_hours: Hours of historical data to use for training
            batch_size: Number of recent records to analyze per run
        """
        self.database = database
        self.redis_client = redis_client
        self.contamination = contamination
        self.lookback_hours = lookback_hours
        self.batch_size = batch_size
        
        self.isolation_forest: Optional[IsolationForest] = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    async def fetch_training_data(self, device_id: Optional[str] = None) -> List[SensorData]:
        """Fetch historical data for training the model.
        
        Args:
            device_id: Optional device ID to filter by. If None, uses all devices.
        
        Returns:
            List of SensorData for training
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        
        # Fetch recent data
        all_data = await self.database.get_recent_data(device_id=device_id, limit=self.batch_size * 10)
        
        # Filter by time range
        training_data = [
            d for d in all_data 
            if d.timestamp >= cutoff_time
        ]
        
        return training_data
    
    def prepare_features(self, sensor_data_list: List[SensorData]) -> np.ndarray:
        """Prepare feature matrix from sensor data.
        
        Args:
            sensor_data_list: List of sensor readings
        
        Returns:
            Feature matrix (n_samples, n_features)
        """
        features = []
        for data in sensor_data_list:
            # Extract features: voltage, current, temperature, and derived features
            feature_vector = [
                data.voltage,
                data.current,
                data.temperature,
                data.voltage * data.current,  # Power approximation
                abs(data.voltage - 230.0),  # Voltage deviation from nominal
                abs(data.current - 4.0),  # Current deviation from nominal
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def train_model(self, training_data: List[SensorData]):
        """Train IsolationForest model on historical data.
        
        Args:
            training_data: Historical sensor data for training
        """
        if len(training_data) < 10:
            print(f"Warning: Insufficient training data ({len(training_data)} samples). Need at least 10.")
            return
        
        # Prepare features
        X = self.prepare_features(training_data)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train IsolationForest
        self.isolation_forest = IsolationForest(
            contamination=self.contamination,
            random_state=42,
            n_estimators=100
        )
        self.isolation_forest.fit(X_scaled)
        self.is_trained = True
        
        print(f"Model trained on {len(training_data)} samples")
    
    def detect_anomalies(self, sensor_data_list: List[SensorData]) -> List[AnomalyAlert]:
        """Detect anomalies in sensor data using trained model.
        
        Args:
            sensor_data_list: List of sensor readings to analyze
        
        Returns:
            List of AnomalyAlert objects for detected anomalies
        """
        if not self.is_trained or self.isolation_forest is None:
            return []
        
        if not sensor_data_list:
            return []
        
        # Prepare features
        X = self.prepare_features(sensor_data_list)
        X_scaled = self.scaler.transform(X)
        
        # Predict anomalies (-1 for anomaly, 1 for normal)
        predictions = self.isolation_forest.predict(X_scaled)
        anomaly_scores = self.isolation_forest.score_samples(X_scaled)
        
        # Create alerts for anomalies
        alerts = []
        for i, (data, is_anomaly, score) in enumerate(zip(sensor_data_list, predictions, anomaly_scores)):
            if is_anomaly == -1:  # Anomaly detected
                # Determine severity based on score (more negative = more severe)
                if score < -0.5:
                    severity = 'high'
                elif score < -0.3:
                    severity = 'medium'
                else:
                    severity = 'low'
                
                # Determine which metric is most anomalous
                voltage_dev = abs(data.voltage - 230.0)
                current_dev = abs(data.current - 4.0)
                temp_dev = abs(data.temperature - 35.0)
                
                if voltage_dev > current_dev and voltage_dev > temp_dev:
                    metric = 'voltage'
                    value = data.voltage
                    expected_range = (200.0, 250.0)
                    description = f"IsolationForest detected voltage anomaly: {data.voltage}V (score: {score:.3f})"
                elif current_dev > temp_dev:
                    metric = 'current'
                    value = data.current
                    expected_range = (0.0, 10.0)
                    description = f"IsolationForest detected current anomaly: {data.current}A (score: {score:.3f})"
                else:
                    metric = 'temperature'
                    value = data.temperature
                    expected_range = (0.0, 80.0)
                    description = f"IsolationForest detected temperature anomaly: {data.temperature}°C (score: {score:.3f})"
                
                alert = AnomalyAlert(
                    device_id=data.device_id,
                    timestamp=data.timestamp,
                    metric=metric,
                    value=value,
                    expected_range=expected_range,
                    severity=severity,
                    description=description
                )
                alerts.append(alert)
        
        return alerts
    
    async def publish_alert(self, alert: AnomalyAlert):
        """Publish anomaly alert to Redis.
        
        Args:
            alert: AnomalyAlert to publish
        """
        if not self.redis_client:
            print(f"Warning: Redis client not available. Alert not published: {alert.description}")
            return
        
        try:
            # Serialize alert to JSON
            alert_dict = {
                'device_id': alert.device_id,
                'timestamp': alert.timestamp.isoformat(),
                'metric': alert.metric,
                'value': alert.value,
                'expected_range': list(alert.expected_range),
                'severity': alert.severity,
                'description': alert.description
            }
            
            alert_json = json.dumps(alert_dict)
            
            # Publish to Redis list
            await self.redis_client.lpush('alerts:anomalies', alert_json)
            
            # Also publish to a channel for real-time subscribers (optional)
            await self.redis_client.publish('alerts:anomalies:channel', alert_json)
            
            print(f"Published alert to Redis: {alert.device_id} - {alert.description}")
        except Exception as e:
            print(f"Error publishing alert to Redis: {e}")
    
    async def run_detection_cycle(self):
        """Run a single detection cycle: fetch data, detect anomalies, publish alerts."""
        try:
            # Fetch recent data for analysis
            recent_data = await self.database.get_recent_data(limit=self.batch_size)
            
            if not recent_data:
                print("No recent data available for analysis")
                return
            
            # Ensure model is trained
            if not self.is_trained:
                print("Training model on historical data...")
                training_data = await self.fetch_training_data()
                if training_data:
                    self.train_model(training_data)
                else:
                    print("No training data available. Skipping detection cycle.")
                    return
            
            # Detect anomalies
            alerts = self.detect_anomalies(recent_data)
            
            # Publish alerts to Redis
            for alert in alerts:
                await self.publish_alert(alert)
            
            if alerts:
                print(f"Detection cycle complete: {len(alerts)} anomalies detected and published")
            else:
                print(f"Detection cycle complete: No anomalies detected in {len(recent_data)} records")
        
        except Exception as e:
            print(f"Error in detection cycle: {e}")
            import traceback
            traceback.print_exc()
    
    async def run_continuous(self, interval_seconds: int = 60):
        """Run continuous anomaly detection.
        
        Args:
            interval_seconds: Seconds between detection cycles
        """
        print(f"Starting continuous anomaly detection (interval: {interval_seconds}s)")
        
        # Initial training
        print("Initial training...")
        training_data = await self.fetch_training_data()
        if training_data:
            self.train_model(training_data)
        else:
            print("Warning: No training data available. Will retry in next cycle.")
        
        # Continuous detection loop
        while True:
            try:
                await self.run_detection_cycle()
            except Exception as e:
                print(f"Error in detection cycle: {e}")
            
            await asyncio.sleep(interval_seconds)


async def create_redis_client(redis_url: Optional[str] = None) -> Optional[aioredis.Redis]:
    """Create Redis client.
    
    Args:
        redis_url: Redis connection URL (e.g., redis://localhost:6379/0)
    
    Returns:
        Redis client or None if connection fails
    """
    if not redis_url:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    try:
        client = aioredis.from_url(redis_url, decode_responses=True)
        # Test connection
        await client.ping()
        print(f"Connected to Redis at {redis_url}")
        return client
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        return None


async def main():
    """Main entry point for anomaly detection engine."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Anomaly Detection Engine')
    parser.add_argument('--db-dsn', type=str, 
                       default=os.getenv("DB_DSN", "postgresql://postgres:password@localhost:5432/powergrid"),
                       help='Database connection string')
    parser.add_argument('--redis-url', type=str,
                       default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                       help='Redis connection URL')
    parser.add_argument('--contamination', type=float, default=0.1,
                       help='Expected proportion of outliers (0.0 to 0.5)')
    parser.add_argument('--lookback-hours', type=int, default=24,
                       help='Hours of historical data for training')
    parser.add_argument('--interval', type=int, default=60,
                       help='Seconds between detection cycles')
    parser.add_argument('--batch-size', type=int, default=1000,
                       help='Number of recent records to analyze per cycle')
    parser.add_argument('--once', action='store_true',
                       help='Run detection once instead of continuously')
    
    args = parser.parse_args()
    
    # Initialize database
    db = Database(dsn=args.db_dsn)
    await db.connect()
    print("Database connected")
    
    # Initialize Redis
    redis_client = await create_redis_client(args.redis_url)
    if not redis_client:
        print("Warning: Running without Redis. Alerts will not be published.")
    
    # Create engine
    engine = AnomalyDetectionEngine(
        database=db,
        redis_client=redis_client,
        contamination=args.contamination,
        lookback_hours=args.lookback_hours,
        batch_size=args.batch_size
    )
    
    try:
        if args.once:
            # Run once
            await engine.run_detection_cycle()
        else:
            # Run continuously
            await engine.run_continuous(interval_seconds=args.interval)
    except KeyboardInterrupt:
        print("\nShutting down anomaly detection engine...")
    finally:
        await db.close()
        if redis_client:
            await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())

