"""SQLite-based event store for persistence and state reconstruction."""

import json
import sqlite3
import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import structlog

from .event_types import Event


logger = structlog.get_logger()


@dataclass
class EventRecord:
    """Represents a persisted event record."""
    
    id: int
    event_type: str
    aggregate_id: str
    aggregate_type: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    sequence_number: int


@dataclass  
class SnapshotRecord:
    """Represents a persisted aggregate snapshot."""
    
    aggregate_id: str
    aggregate_type: str
    state_data: Dict[str, Any]
    version: int
    timestamp: datetime


class EventStore(ABC):
    """Abstract base class for event stores."""
    
    @abstractmethod
    async def append_event(self, event: Event) -> int:
        """Append an event and return its sequence number."""
        pass
    
    @abstractmethod
    async def get_events_for_aggregate(
        self,
        aggregate_id: str,
        from_sequence: int = 0
    ) -> List[EventRecord]:
        """Get all events for an aggregate starting from a sequence number."""
        pass
    
    @abstractmethod
    async def get_events_since(self, sequence_number: int) -> List[EventRecord]:
        """Get all events since a specific sequence number."""
        pass
    
    @abstractmethod
    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        state_data: Dict[str, Any],
        version: int
    ) -> None:
        """Save a snapshot of aggregate state."""
        pass
    
    @abstractmethod
    async def get_latest_snapshot(self, aggregate_id: str) -> Optional[SnapshotRecord]:
        """Get the latest snapshot for an aggregate."""
        pass


class SQLiteEventStore(EventStore):
    """SQLite implementation of the event store."""
    
    def __init__(self, database_path: str = "events.db"):
        self.database_path = database_path
        self._lock = asyncio.Lock()
        
    async def initialize(self) -> None:
        """Initialize the database schema."""
        async with self._lock:
            await self._run_in_executor(self._create_tables)
            logger.info("Event store initialized", database=self.database_path)
    
    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.database_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    aggregate_id TEXT NOT NULL,
                    aggregate_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_events_aggregate 
                ON events(aggregate_id, sequence_number);
                
                CREATE INDEX IF NOT EXISTS idx_events_sequence 
                ON events(sequence_number);
                
                CREATE INDEX IF NOT EXISTS idx_events_type 
                ON events(event_type);
                
                CREATE TABLE IF NOT EXISTS snapshots (
                    aggregate_id TEXT PRIMARY KEY,
                    aggregate_type TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    definition_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_workflows_active 
                ON workflows(name, is_active);
            """)
    
    async def append_event(self, event: Event) -> int:
        """Append an event and return its sequence number."""
        async with self._lock:
            return await self._run_in_executor(self._append_event_sync, event)
    
    def _append_event_sync(self, event: Event) -> int:
        """Synchronous event append for thread execution."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (
                    event_type, aggregate_id, aggregate_type, 
                    payload, metadata, timestamp, sequence_number
                )
                VALUES (?, ?, ?, ?, ?, ?, 
                    COALESCE((SELECT MAX(sequence_number) FROM events), 0) + 1)
                """,
                (
                    event.event_type,
                    event.aggregate_id,
                    event.aggregate_type,
                    json.dumps(event.payload),
                    json.dumps(event.metadata),
                    event.timestamp.isoformat(),
                )
            )
            
            # Get the sequence number that was assigned
            sequence_number = cursor.execute(
                "SELECT sequence_number FROM events WHERE id = ?",
                (cursor.lastrowid,)
            ).fetchone()[0]
            
            logger.debug(
                "Event appended",
                event_type=event.event_type,
                aggregate_id=event.aggregate_id,
                sequence_number=sequence_number
            )
            
            return sequence_number
    
    async def get_events_for_aggregate(
        self,
        aggregate_id: str,
        from_sequence: int = 0
    ) -> List[EventRecord]:
        """Get all events for an aggregate starting from a sequence number."""
        async with self._lock:
            return await self._run_in_executor(
                self._get_events_for_aggregate_sync, 
                aggregate_id, 
                from_sequence
            )
    
    def _get_events_for_aggregate_sync(
        self, 
        aggregate_id: str, 
        from_sequence: int
    ) -> List[EventRecord]:
        """Synchronous aggregate events retrieval for thread execution."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, event_type, aggregate_id, aggregate_type,
                       payload, metadata, timestamp, sequence_number
                FROM events
                WHERE aggregate_id = ? AND sequence_number > ?
                ORDER BY sequence_number ASC
                """,
                (aggregate_id, from_sequence)
            )
            
            events = []
            for row in cursor.fetchall():
                events.append(EventRecord(
                    id=row[0],
                    event_type=row[1],
                    aggregate_id=row[2],
                    aggregate_type=row[3],
                    payload=json.loads(row[4]),
                    metadata=json.loads(row[5]),
                    timestamp=datetime.fromisoformat(row[6]),
                    sequence_number=row[7]
                ))
            
            return events
    
    async def get_events_since(self, sequence_number: int) -> List[EventRecord]:
        """Get all events since a specific sequence number."""
        async with self._lock:
            return await self._run_in_executor(
                self._get_events_since_sync,
                sequence_number
            )
    
    def _get_events_since_sync(self, sequence_number: int) -> List[EventRecord]:
        """Synchronous events since sequence retrieval for thread execution."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                SELECT id, event_type, aggregate_id, aggregate_type,
                       payload, metadata, timestamp, sequence_number
                FROM events
                WHERE sequence_number > ?
                ORDER BY sequence_number ASC
                """,
                (sequence_number,)
            )
            
            events = []
            for row in cursor.fetchall():
                events.append(EventRecord(
                    id=row[0],
                    event_type=row[1],
                    aggregate_id=row[2],
                    aggregate_type=row[3],
                    payload=json.loads(row[4]),
                    metadata=json.loads(row[5]),
                    timestamp=datetime.fromisoformat(row[6]),
                    sequence_number=row[7]
                ))
            
            return events
    
    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        state_data: Dict[str, Any],
        version: int
    ) -> None:
        """Save a snapshot of aggregate state."""
        async with self._lock:
            await self._run_in_executor(
                self._save_snapshot_sync,
                aggregate_id,
                aggregate_type,
                state_data,
                version
            )
    
    def _save_snapshot_sync(
        self,
        aggregate_id: str,
        aggregate_type: str,
        state_data: Dict[str, Any],
        version: int
    ) -> None:
        """Synchronous snapshot save for thread execution."""
        with sqlite3.connect(self.database_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO snapshots (
                    aggregate_id, aggregate_type, state_data, version, timestamp
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    aggregate_id,
                    aggregate_type,
                    json.dumps(state_data),
                    version,
                    datetime.now(timezone.utc).isoformat()
                )
            )
            
            logger.debug(
                "Snapshot saved",
                aggregate_id=aggregate_id,
                aggregate_type=aggregate_type,
                version=version
            )
    
    async def get_latest_snapshot(self, aggregate_id: str) -> Optional[SnapshotRecord]:
        """Get the latest snapshot for an aggregate."""
        async with self._lock:
            return await self._run_in_executor(
                self._get_latest_snapshot_sync,
                aggregate_id
            )
    
    def _get_latest_snapshot_sync(self, aggregate_id: str) -> Optional[SnapshotRecord]:
        """Synchronous snapshot retrieval for thread execution."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                """
                SELECT aggregate_id, aggregate_type, state_data, version, timestamp
                FROM snapshots
                WHERE aggregate_id = ?
                """,
                (aggregate_id,)
            )
            
            row = cursor.fetchone()
            if row:
                return SnapshotRecord(
                    aggregate_id=row[0],
                    aggregate_type=row[1],
                    state_data=json.loads(row[2]),
                    version=row[3],
                    timestamp=datetime.fromisoformat(row[4])
                )
            
            return None
    
    async def _run_in_executor(self, func, *args):
        """Run a synchronous function in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)
    
    async def get_next_sequence_number(self) -> int:
        """Get the next sequence number that would be assigned."""
        async with self._lock:
            return await self._run_in_executor(self._get_next_sequence_number_sync)
    
    def _get_next_sequence_number_sync(self) -> int:
        """Synchronous next sequence number retrieval."""
        with sqlite3.connect(self.database_path) as conn:
            cursor = conn.execute(
                "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM events"
            )
            return cursor.fetchone()[0]