"""Abstract base classes for storage backend."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def create_agent(self, agent_data: Dict[str, Any]) -> str:
        """Create a new agent and return its ID."""
        pass

    @abstractmethod
    async def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an agent by ID."""
        pass

    @abstractmethod
    async def create_team(self, team_data: Dict[str, Any]) -> str:
        """Create a new team and return its ID."""
        pass

    @abstractmethod
    async def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a team by ID."""
        pass

    @abstractmethod
    async def add_team_member(self, team_id: str, agent_id: str, role: str = "member") -> bool:
        """Add an agent to a team."""
        pass

    @abstractmethod
    async def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task and return its ID."""
        pass

    @abstractmethod
    async def update_task_status(self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> bool:
        """Update task status and optionally result."""
        pass

    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task by ID."""
        pass