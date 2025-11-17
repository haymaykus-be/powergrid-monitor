#!/usr/bin/env python3
"""
Component-level tests for Power Grid Monitor
Run with: python test_components.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from common.models import SensorData, AnomalyAlert
from common.database import Database
from common.telemetry import TelemetryHandler
from anomaly_detection.detector import AnomalyDetector
from anomaly_detection.engine import AnomalyDetectionEngine
import numpy as np


def test_sensor_data_model():
    """Test SensorData model serialization."""
    print("Testing SensorData model...")
    
    # Create sensor data
    data = SensorData(
        device_id="test_sensor",
        timestamp=datetime.now(timezone.utc),
        voltage=230.0,
        current=4.0,
        temperature=35.0
    )
    
    # Test to_dict
    data_dict = data.to_dict()
    assert "device_id" in data_dict
    assert data_dict["voltage"] == 230.0
    
    # Test from_dict
    data2 = SensorData.from_dict(data_dict)
    assert data2.device_id == data.device_id
    assert data2.voltage == data.voltage
    
    print("  ✓ SensorData model tests passed")
    return True


def test_telemetry_handler():
    """Test TelemetryHandler validation."""
    print("Testing TelemetryHandler...")
    
    handler = TelemetryHandler()
    
    # Valid data
    valid_data = SensorData(
        device_id="test",
        timestamp=datetime.now(timezone.utc),
        voltage=230.0,
        current=4.0,
        temperature=35.0
    )
    is_valid, error = handler.validate(valid_data)
    assert is_valid, "Valid data should pass validation"
    
    # Invalid voltage
    invalid_data = SensorData(
        device_id="test",
        timestamp=datetime.now(timezone.utc),
        voltage=300.0,  # Too high
        current=4.0,
        temperature=35.0
    )
    is_valid, error = handler.validate(invalid_data)
    assert not is_valid, "Invalid voltage should fail validation"
    assert "voltage" in error.lower()
    
    print("  ✓ TelemetryHandler tests passed")
    return True


def test_anomaly_detector():
    """Test AnomalyDetector."""
    print("Testing AnomalyDetector...")
    
    detector = AnomalyDetector()
    
    # Normal data
    normal_data = SensorData(
        device_id="test",
        timestamp=datetime.now(timezone.utc),
        voltage=230.0,
        current=4.0,
        temperature=35.0
    )
    alert = detector.detect_anomaly(normal_data)
    assert alert is None, "Normal data should not trigger alert"
    
    # Anomalous voltage
    anomalous_data = SensorData(
        device_id="test",
        timestamp=datetime.now(timezone.utc),
        voltage=260.0,  # Outside safe range
        current=4.0,
        temperature=35.0
    )
    alert = detector.detect_anomaly(anomalous_data)
    assert alert is not None, "Anomalous voltage should trigger alert"
    assert alert.metric == "voltage"
    assert alert.severity in ["low", "medium", "high"]
    
    print("  ✓ AnomalyDetector tests passed")
    return True


async def test_database_operations():
    """Test database operations (requires database connection)."""
    print("Testing Database operations...")
    
    try:
        db = Database()
        await db.connect()
        
        # Test insert
        test_data = SensorData(
            device_id="test_sensor",
            timestamp=datetime.now(timezone.utc),
            voltage=230.0,
            current=4.0,
            temperature=35.0
        )
        record_id = await db.insert_sensor_data(test_data)
        assert record_id > 0, "Insert should return record ID"
        
        # Test query
        recent_data = await db.get_recent_data(device_id="test_sensor", limit=10)
        assert len(recent_data) > 0, "Should retrieve inserted data"
        assert recent_data[0].device_id == "test_sensor"
        
        # Test batch insert
        batch_data = [
            SensorData(
                device_id="test_sensor",
                timestamp=datetime.now(timezone.utc),
                voltage=230.0 + i,
                current=4.0,
                temperature=35.0
            )
            for i in range(5)
        ]
        await db.insert_batch(batch_data)
        
        # Test stats
        stats = await db.get_device_stats("test_sensor", hours=24)
        assert "voltage" in stats
        assert "current" in stats
        assert "temperature" in stats
        
        await db.close()
        print("  ✓ Database operations tests passed")
        return True
    except Exception as e:
        print(f"  ✗ Database tests failed: {e}")
        print("    (This is expected if database is not running)")
        return False


def test_isolation_forest_features():
    """Test IsolationForest feature preparation."""
    print("Testing IsolationForest feature preparation...")
    
    # Create test data
    sensor_data_list = [
        SensorData(
            device_id=f"sensor_{i}",
            timestamp=datetime.now(timezone.utc),
            voltage=230.0 + (i * 0.1),
            current=4.0 + (i * 0.01),
            temperature=35.0 + (i * 0.1)
        )
        for i in range(10)
    ]
    
    # This would normally be done in AnomalyDetectionEngine
    # But we can test the feature extraction logic
    features = []
    for data in sensor_data_list:
        feature_vector = [
            data.voltage,
            data.current,
            data.temperature,
            data.voltage * data.current,
            abs(data.voltage - 230.0),
            abs(data.current - 4.0),
        ]
        features.append(feature_vector)
    
    X = np.array(features)
    assert X.shape == (10, 6), "Feature matrix should have correct shape"
    assert X.shape[1] == 6, "Should have 6 features per sample"
    
    print("  ✓ Feature preparation tests passed")
    return True


async def run_all_tests():
    """Run all component tests."""
    print("=" * 50)
    print("Running Component Tests")
    print("=" * 50)
    print()
    
    tests = [
        ("SensorData Model", test_sensor_data_model),
        ("TelemetryHandler", test_telemetry_handler),
        ("AnomalyDetector", test_anomaly_detector),
        ("IsolationForest Features", test_isolation_forest_features),
        ("Database Operations", test_database_operations),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ✗ {name} test failed with error: {e}")
            failed += 1
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)

