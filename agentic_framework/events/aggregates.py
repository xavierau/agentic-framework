"""Event-sourced aggregates for state reconstruction."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import structlog

from .event_store import EventStore, EventRecord
from .event_types import Event


logger = structlog.get_logger()


class EventSourcedAggregate(BaseModel, ABC):
    """
    Base class for event-sourced aggregates.
    
    Aggregates reconstruct their state by replaying events and can generate
    new events based on business logic.
    """
    
    id: str
    version: int = 0
    uncommitted_events: List[Event] = Field(default_factory=list, exclude=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        extra = "forbid"
    
    @classmethod
    async def reconstruct(cls, aggregate_id: str, event_store: EventStore) -> 'EventSourcedAggregate':
        """Reconstruct aggregate state from events."""
        
        # Try to load from snapshot first
        snapshot = await event_store.get_latest_snapshot(aggregate_id)
        
        if snapshot:
            # Start from snapshot
            aggregate = cls.from_snapshot(aggregate_id, snapshot.state_data)
            aggregate.version = snapshot.version
            from_sequence = snapshot.version
            
            logger.debug(
                "Loaded aggregate from snapshot",
                aggregate_id=aggregate_id,
                aggregate_type=cls.__name__,
                snapshot_version=snapshot.version
            )
        else:
            # Start from empty state
            aggregate = cls(id=aggregate_id)
            from_sequence = 0
        
        # Replay events since snapshot
        events = await event_store.get_events_for_aggregate(aggregate_id, from_sequence)
        
        for event_record in events:
            event = cls._event_record_to_event(event_record)
            aggregate.apply_event(event)
            aggregate.version = event_record.sequence_number
        
        # Clear uncommitted events (these are historical)
        aggregate.uncommitted_events = []
        
        logger.debug(
            "Aggregate reconstructed",
            aggregate_id=aggregate_id,
            aggregate_type=cls.__name__,
            final_version=aggregate.version,
            events_replayed=len(events)
        )
        
        return aggregate
    
    @classmethod
    def from_snapshot(cls, aggregate_id: str, snapshot_data: Dict[str, Any]) -> 'EventSourcedAggregate':
        """Create aggregate instance from snapshot data."""
        snapshot_data['id'] = aggregate_id
        return cls(**snapshot_data)
    
    @staticmethod
    def _event_record_to_event(event_record: EventRecord) -> Event:
        """Convert an EventRecord to an Event object."""
        # This is a simplified conversion - in practice you might want
        # a more sophisticated event type registry
        from .event_types import (
            AgentCreated, AgentCapabilityAdded, AgentStatusChanged,
            TeamCreated, TeamMemberAdded, TeamLeadAssigned,
            TaskCreated, TaskAssigned, TaskStarted, TaskCompleted, TaskFailed
        )
        
        event_type_map = {
            'AgentCreated': AgentCreated,
            'AgentCapabilityAdded': AgentCapabilityAdded,
            'AgentStatusChanged': AgentStatusChanged,
            'TeamCreated': TeamCreated,
            'TeamMemberAdded': TeamMemberAdded,
            'TeamLeadAssigned': TeamLeadAssigned,
            'TaskCreated': TaskCreated,
            'TaskAssigned': TaskAssigned,
            'TaskStarted': TaskStarted,
            'TaskCompleted': TaskCompleted,
            'TaskFailed': TaskFailed,
        }
        
        # Always create a generic event since the specific event constructors
        # have different signatures and we've already stored the payload
        from .event_types import Event
        return Event(
            event_id=str(event_record.id),
            event_type=event_record.event_type,
            aggregate_id=event_record.aggregate_id,
            aggregate_type=event_record.aggregate_type,
            payload=event_record.payload,
            metadata=event_record.metadata,
            timestamp=event_record.timestamp,
            sequence_number=event_record.sequence_number
        )
    
    def apply_event(self, event: Event) -> None:
        """Apply an event to update the aggregate state."""
        
        # Update timestamps
        if not self.created_at:
            self.created_at = event.timestamp
        self.updated_at = event.timestamp
        
        # Delegate to specific event handler
        handler_name = f"_apply_{event.event_type}"
        handler = getattr(self, handler_name, None)
        
        if handler:
            handler(event)
        else:
            # Log warning about missing handler
            logger.warning(
                "No handler for event type",
                aggregate_id=self.id,
                aggregate_type=type(self).__name__,
                event_type=event.event_type
            )
    
    def add_event(self, event: Event) -> None:
        """Add an event to the uncommitted events list."""
        self.uncommitted_events.append(event)
        self.apply_event(event)  # Apply to local state immediately
    
    def get_uncommitted_events(self) -> List[Event]:
        """Get events that haven't been persisted yet."""
        return self.uncommitted_events.copy()
    
    def mark_events_committed(self) -> None:
        """Mark all uncommitted events as committed."""
        self.uncommitted_events.clear()
    
    def to_snapshot(self) -> Dict[str, Any]:
        """Create snapshot data for persistence."""
        # Use Pydantic's dict method but exclude internal fields
        data = self.model_dump(exclude={
            'version', 'uncommitted_events', 'created_at', 'updated_at'
        })
        
        # Add metadata
        data['_snapshot_created_at'] = datetime.now(timezone.utc).isoformat()
        data['_snapshot_version'] = self.version
        
        return data
    
    @abstractmethod
    def _apply_initial_event(self, event: Event) -> None:
        """Apply the initial creation event for this aggregate type."""
        pass


class EventSourcedAgent(EventSourcedAggregate):
    """Event-sourced agent aggregate."""
    
    name: str = ""
    agent_type: str = ""
    capabilities: List[str] = Field(default_factory=list)
    status: str = "inactive"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def _apply_AgentCreated(self, event: Event) -> None:
        """Apply AgentCreated event."""
        payload = event.payload
        self.name = payload.get('name', '')
        self.agent_type = payload.get('agent_type', '')
        self.capabilities = payload.get('capabilities', [])
        self.status = 'active'
        
        logger.debug(
            "Applied AgentCreated",
            agent_id=self.id,
            name=self.name,
            agent_type=self.agent_type
        )
    
    def _apply_AgentCapabilityAdded(self, event: Event) -> None:
        """Apply AgentCapabilityAdded event."""
        capability = event.payload.get('capability')
        if capability and capability not in self.capabilities:
            self.capabilities.append(capability)
            
            logger.debug(
                "Applied AgentCapabilityAdded",
                agent_id=self.id,
                capability=capability
            )
    
    def _apply_AgentStatusChanged(self, event: Event) -> None:
        """Apply AgentStatusChanged event."""
        new_status = event.payload.get('new_status')
        if new_status:
            old_status = self.status
            self.status = new_status
            
            logger.debug(
                "Applied AgentStatusChanged",
                agent_id=self.id,
                old_status=old_status,
                new_status=new_status
            )
    
    def _apply_initial_event(self, event: Event) -> None:
        """Apply initial AgentCreated event."""
        if event.event_type == 'AgentCreated':
            self._apply_AgentCreated(event)


class EventSourcedTeam(EventSourcedAggregate):
    """Event-sourced team aggregate."""
    
    name: str = ""
    description: Optional[str] = None
    lead_id: Optional[str] = None
    member_ids: List[str] = Field(default_factory=list)
    child_team_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def _apply_TeamCreated(self, event: Event) -> None:
        """Apply TeamCreated event."""
        payload = event.payload
        self.name = payload.get('name', '')
        self.description = payload.get('description')
        
        logger.debug(
            "Applied TeamCreated",
            team_id=self.id,
            name=self.name
        )
    
    def _apply_TeamMemberAdded(self, event: Event) -> None:
        """Apply TeamMemberAdded event."""
        agent_id = event.payload.get('agent_id')
        role = event.payload.get('role', 'member')
        
        if agent_id and agent_id not in self.member_ids:
            self.member_ids.append(agent_id)
            
            # Set as lead if role is lead
            if role == 'lead':
                self.lead_id = agent_id
            
            logger.debug(
                "Applied TeamMemberAdded",
                team_id=self.id,
                agent_id=agent_id,
                role=role
            )
    
    def _apply_TeamLeadAssigned(self, event: Event) -> None:
        """Apply TeamLeadAssigned event."""
        lead_agent_id = event.payload.get('lead_agent_id')
        if lead_agent_id:
            self.lead_id = lead_agent_id
            
            # Ensure lead is also a member
            if lead_agent_id not in self.member_ids:
                self.member_ids.append(lead_agent_id)
            
            logger.debug(
                "Applied TeamLeadAssigned",
                team_id=self.id,
                lead_agent_id=lead_agent_id
            )
    
    def _apply_initial_event(self, event: Event) -> None:
        """Apply initial TeamCreated event."""
        if event.event_type == 'TeamCreated':
            self._apply_TeamCreated(event)


class EventSourcedTask(EventSourcedAggregate):
    """Event-sourced task aggregate."""
    
    title: str = ""
    task_type: str = ""
    priority: int = 2
    required_capabilities: List[str] = Field(default_factory=list)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    assigned_team_id: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    executor_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    workflow_id: Optional[str] = None
    
    def _apply_TaskCreated(self, event: Event) -> None:
        """Apply TaskCreated event."""
        payload = event.payload
        self.title = payload.get('title', '')
        self.task_type = payload.get('task_type', '')
        self.priority = payload.get('priority', 2)
        self.required_capabilities = payload.get('required_capabilities', [])
        self.input_data = payload.get('input_data', {})
        self.workflow_id = payload.get('workflow_id')
        self.status = 'pending'
        
        logger.debug(
            "Applied TaskCreated",
            task_id=self.id,
            title=self.title,
            task_type=self.task_type
        )
    
    def _apply_TaskAssigned(self, event: Event) -> None:
        """Apply TaskAssigned event."""
        payload = event.payload
        assignee_id = payload.get('assignee_id')
        assignee_type = payload.get('assignee_type')
        
        if assignee_type == 'Agent':
            self.assigned_agent_id = assignee_id
        elif assignee_type == 'Team':
            self.assigned_team_id = assignee_id
        
        logger.debug(
            "Applied TaskAssigned",
            task_id=self.id,
            assignee_id=assignee_id,
            assignee_type=assignee_type
        )
    
    def _apply_TaskStarted(self, event: Event) -> None:
        """Apply TaskStarted event."""
        self.executor_id = event.payload.get('executor_id')
        self.status = 'in_progress'
        
        logger.debug(
            "Applied TaskStarted",
            task_id=self.id,
            executor_id=self.executor_id
        )
    
    def _apply_TaskCompleted(self, event: Event) -> None:
        """Apply TaskCompleted event."""
        self.result = event.payload.get('result', {})
        self.status = 'completed'
        
        logger.debug(
            "Applied TaskCompleted",
            task_id=self.id
        )
    
    def _apply_TaskFailed(self, event: Event) -> None:
        """Apply TaskFailed event."""
        self.error_message = event.payload.get('error_message')
        self.status = 'failed'
        
        logger.debug(
            "Applied TaskFailed",
            task_id=self.id,
            error_message=self.error_message
        )
    
    def _apply_initial_event(self, event: Event) -> None:
        """Apply initial TaskCreated event."""
        if event.event_type == 'TaskCreated':
            self._apply_TaskCreated(event)