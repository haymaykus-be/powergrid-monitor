import os
import asyncpg
from typing import Optional, List
from datetime import datetime
from .models import SensorData


class Database:
    """Database connection handler."""
    
    def __init__(self, dsn: Optional[str] = None):
        """Initialize database connection.
        
        Args:
            dsn: Database connection string. If None, uses DB_DSN env var.
        """
        self.dsn = dsn or os.getenv("DB_DSN", "postgresql://postgres:password@localhost:5432/powergrid")
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self, min_size: int = 1, max_size: int = 10):
        """Create database connection pool."""
        self.pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=min_size,
            max_size=max_size
        )
        await self.init_schema()
    
    async def init_schema(self):
        """Initialize database schema."""
        async with self.pool.acquire() as conn:
            # Check if table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'sensor_data'
                );
            """)
            
            # Check if TimescaleDB is available
            timescaledb_available = False
            try:
                result = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'
                    );
                """)
                timescaledb_available = result is True
            except:
                pass
            
            # Check if table is already a hypertable
            is_hypertable = False
            if table_exists:
                try:
                    result = await conn.fetchval("""
                        SELECT COUNT(*) FROM timescaledb_information.hypertables 
                        WHERE hypertable_name = 'sensor_data';
                    """)
                    is_hypertable = result is not None and result > 0
                except:
                    pass
            
            if not table_exists:
                # Create sensor_data table
                if timescaledb_available:
                    # Create with composite primary key for TimescaleDB
                    await conn.execute("""
                        CREATE TABLE sensor_data (
                            id SERIAL,
                            device_id TEXT NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL,
                            voltage DOUBLE PRECISION NOT NULL,
                            current DOUBLE PRECISION NOT NULL,
                            temperature DOUBLE PRECISION NOT NULL,
                            PRIMARY KEY (id, timestamp)
                        );
                    """)
                else:
                    # Create with simple primary key for regular PostgreSQL
                    await conn.execute("""
                        CREATE TABLE sensor_data (
                            id SERIAL PRIMARY KEY,
                            device_id TEXT NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL,
                            voltage DOUBLE PRECISION NOT NULL,
                            current DOUBLE PRECISION NOT NULL,
                            temperature DOUBLE PRECISION NOT NULL
                        );
                    """)
            
            # Try to create TimescaleDB hypertable if available and not already a hypertable
            if timescaledb_available and not is_hypertable:
                try:
                    # Check if table has the right primary key structure
                    if table_exists:
                        # Check primary key columns
                        pk_cols = await conn.fetch("""
                            SELECT a.attname
                            FROM pg_index i
                            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                            WHERE i.indrelid = 'sensor_data'::regclass
                            AND i.indisprimary;
                        """)
                        pk_column_names = [row['attname'] for row in pk_cols]
                        
                        # If timestamp is not in primary key, we can't create hypertable
                        # Skip hypertable creation for existing tables with wrong schema
                        if 'timestamp' not in pk_column_names:
                            print("Warning: Table exists with incompatible primary key. Skipping hypertable creation.")
                            print("  To use TimescaleDB, drop the table first: DROP TABLE sensor_data;")
                        else:
                            # Create hypertable
                            await conn.execute("""
                                SELECT create_hypertable('sensor_data', 'timestamp', if_not_exists => TRUE);
                            """)
                    else:
                        # New table, create hypertable
                        await conn.execute("""
                            SELECT create_hypertable('sensor_data', 'timestamp', if_not_exists => TRUE);
                        """)
                except Exception as e:
                    # TimescaleDB function not available or other error
                    if 'create_hypertable' not in str(e):
                        print(f"Warning: Could not create hypertable: {e}")
            
            # Create index on device_id and timestamp for faster queries
            # This works for both regular tables and hypertables
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_data_device_timestamp 
                ON sensor_data (device_id, timestamp DESC);
            """)
    
    async def insert_sensor_data(self, data: SensorData) -> int:
        """Insert a single sensor data record.
        
        Returns:
            ID of inserted record
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval("""
                INSERT INTO sensor_data (device_id, timestamp, voltage, current, temperature)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id;
            """, data.device_id, data.timestamp, data.voltage, data.current, data.temperature)
    
    async def insert_batch(self, data_list: List[SensorData]):
        """Insert multiple sensor data records in a batch."""
        if not data_list:
            return
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany("""
                    INSERT INTO sensor_data (device_id, timestamp, voltage, current, temperature)
                    VALUES ($1, $2, $3, $4, $5);
                """, [
                    (d.device_id, d.timestamp, d.voltage, d.current, d.temperature)
                    for d in data_list
                ])
    
    async def get_recent_data(self, device_id: Optional[str] = None, limit: int = 100) -> List[SensorData]:
        """Get recent sensor data.
        
        Args:
            device_id: Filter by device ID. If None, returns data for all devices.
            limit: Maximum number of records to return.
        
        Returns:
            List of SensorData objects
        """
        async with self.pool.acquire() as conn:
            if device_id:
                rows = await conn.fetch("""
                    SELECT device_id, timestamp, voltage, current, temperature
                    FROM sensor_data
                    WHERE device_id = $1
                    ORDER BY timestamp DESC
                    LIMIT $2;
                """, device_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT device_id, timestamp, voltage, current, temperature
                    FROM sensor_data
                    ORDER BY timestamp DESC
                    LIMIT $1;
                """, limit)
            
            return [
                SensorData(
                    device_id=row['device_id'],
                    timestamp=row['timestamp'],
                    voltage=row['voltage'],
                    current=row['current'],
                    temperature=row['temperature']
                )
                for row in rows
            ]
    
    async def get_device_stats(self, device_id: str, hours: int = 24) -> dict:
        """Get statistics for a device over the last N hours.
        
        Returns:
            Dictionary with avg, min, max for each metric
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    AVG(voltage) as avg_voltage,
                    MIN(voltage) as min_voltage,
                    MAX(voltage) as max_voltage,
                    AVG(current) as avg_current,
                    MIN(current) as min_current,
                    MAX(current) as max_current,
                    AVG(temperature) as avg_temperature,
                    MIN(temperature) as min_temperature,
                    MAX(temperature) as max_temperature
                FROM sensor_data
                WHERE device_id = $1
                AND timestamp > NOW() - INTERVAL '1 hour' * $2
            """, device_id, hours)
            
            if row:
                return {
                    'voltage': {
                        'avg': float(row['avg_voltage'] or 0),
                        'min': float(row['min_voltage'] or 0),
                        'max': float(row['max_voltage'] or 0)
                    },
                    'current': {
                        'avg': float(row['avg_current'] or 0),
                        'min': float(row['min_current'] or 0),
                        'max': float(row['max_current'] or 0)
                    },
                    'temperature': {
                        'avg': float(row['avg_temperature'] or 0),
                        'min': float(row['min_temperature'] or 0),
                        'max': float(row['max_temperature'] or 0)
                    }
                }
            return {}
    
    async def close(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None


if __name__ == "__main__":
    pass

