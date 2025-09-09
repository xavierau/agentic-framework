"""SQLAlchemy ORM models for the agentic framework."""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import uuid4, UUID

from sqlalchemy import (
    Column, String, DateTime, Text, JSON, ForeignKey, Table, Boolean, Integer
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func


Base = declarative_base()


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"


# Association table for team membership
team_members = Table(
    'team_members',
    Base.metadata,
    Column('team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('agent_id', String, ForeignKey('agents.id'), primary_key=True),
    Column('role', String, default='member'),
    Column('joined_at', DateTime, default=func.now())
)


# Association table for team composition (team as member of another team)
team_composition = Table(
    'team_composition',
    Base.metadata,
    Column('parent_team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('child_team_id', String, ForeignKey('teams.id'), primary_key=True),
    Column('role', String, default='member'),
    Column('added_at', DateTime, default=func.now())
)


class Agent(Base):
    """Agent model representing individual agents in the system."""
    
    __tablename__ = 'agents'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    agent_type = Column(String(50), nullable=False)
    capabilities = Column(JSON, default=list)
    status = Column(String(20), default=AgentStatus.ACTIVE)
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    teams = relationship("Team", secondary=team_members, back_populates="members")
    led_teams = relationship("Team", back_populates="lead")
    assigned_tasks = relationship("Task", back_populates="assignee")
    
    def __repr__(self):
        return f"<Agent(id='{self.id}', name='{self.name}', type='{self.agent_type}')>"


class Team(Base):
    """Team model representing groups of agents."""
    
    __tablename__ = 'teams'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    lead_id = Column(String, ForeignKey('agents.id'))
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    lead = relationship("Agent", back_populates="led_teams")
    members = relationship("Agent", secondary=team_members, back_populates="teams")
    tasks = relationship("Task", back_populates="assigned_team")
    
    # Team composition relationships
    parent_teams = relationship(
        "Team",
        secondary=team_composition,
        primaryjoin=id == team_composition.c.child_team_id,
        secondaryjoin=id == team_composition.c.parent_team_id,
        back_populates="child_teams"
    )
    
    child_teams = relationship(
        "Team",
        secondary=team_composition,
        primaryjoin=id == team_composition.c.parent_team_id,
        secondaryjoin=id == team_composition.c.child_team_id,
        back_populates="parent_teams"
    )
    
    def __repr__(self):
        return f"<Team(id='{self.id}', name='{self.name}')>"


class Task(Base):
    """Task model representing work to be completed."""
    
    __tablename__ = 'tasks'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    title = Column(String(200), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), nullable=False)
    priority = Column(Integer, default=1)
    
    # Task hierarchy
    parent_task_id = Column(String, ForeignKey('tasks.id'))
    
    # Assignment
    assigned_team_id = Column(String, ForeignKey('teams.id'))
    assigned_agent_id = Column(String, ForeignKey('agents.id'))
    
    # Status and lifecycle
    status = Column(String(20), default=TaskStatus.PENDING)
    input_data = Column(JSON, default=dict)
    result_data = Column(JSON, default=dict)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    parent_task = relationship("Task", remote_side=[id], backref="subtasks")
    assigned_team = relationship("Team", back_populates="tasks")
    assignee = relationship("Agent", back_populates="assigned_tasks")
    messages = relationship("Message", back_populates="task")
    
    def __repr__(self):
        return f"<Task(id='{self.id}', title='{self.title}', status='{self.status}')>"


class Message(Base):
    """Message model for communication between agents and teams."""
    
    __tablename__ = 'messages'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    message_type = Column(String(50), nullable=False)
    sender_id = Column(String, ForeignKey('agents.id'))
    receiver_id = Column(String, ForeignKey('agents.id'))
    team_id = Column(String, ForeignKey('teams.id'))
    task_id = Column(String, ForeignKey('tasks.id'))
    
    content = Column(JSON, nullable=False)
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=func.now())
    processed_at = Column(DateTime)
    
    # Relationships
    sender = relationship("Agent", foreign_keys=[sender_id])
    receiver = relationship("Agent", foreign_keys=[receiver_id])
    team = relationship("Team")
    task = relationship("Task", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id='{self.id}', type='{self.message_type}', sender='{self.sender_id}')>"