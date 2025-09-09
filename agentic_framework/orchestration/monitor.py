"""Execution monitoring and system health tracking."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import structlog

from ..core.task import Task, TaskStatus
from ..core.team import Team
from ..core.agent import Agent, AgentStatus
from ..messaging.base import MessageBus, Message, MessageType


logger = structlog.get_logger()


@dataclass
class SystemHealth:
    """System health metrics."""
    
    timestamp: datetime
    total_agents: int
    active_agents: int
    busy_agents: int
    error_agents: int
    total_teams: int
    active_teams: int
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_task_duration: float
    system_load: float


@dataclass
class TaskMetrics:
    """Task execution metrics."""
    
    task_id: str
    task_type: str
    status: TaskStatus
    assigned_agent_id: Optional[str]
    assigned_team_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration: Optional[float]
    success: Optional[bool]


@dataclass
class AgentMetrics:
    """Agent performance metrics."""
    
    agent_id: str
    agent_name: str
    agent_type: str
    status: AgentStatus
    current_tasks: int
    completed_tasks: int
    failed_tasks: int
    success_rate: float
    average_task_duration: float
    last_heartbeat: Optional[datetime]


class ExecutionMonitor:
    """Monitors system execution and provides metrics."""
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self._agents: Dict[str, Agent] = {}
        self._teams: Dict[str, Team] = {}
        self._tasks: Dict[str, TaskMetrics] = {}
        self._agent_metrics: Dict[str, AgentMetrics] = {}
        self._system_health_history: List[SystemHealth] = []
        self._running = False
        self._monitor_interval = 30  # seconds
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent for monitoring."""
        self._agents[agent.id] = agent
        self._agent_metrics[agent.id] = AgentMetrics(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            status=agent.status,
            current_tasks=len(agent.current_tasks),
            completed_tasks=agent.completed_tasks,
            failed_tasks=agent.failed_tasks,
            success_rate=0.0,
            average_task_duration=0.0,
            last_heartbeat=agent.last_heartbeat
        )
    
    def register_team(self, team: Team) -> None:
        """Register a team for monitoring."""
        self._teams[team.id] = team
    
    async def start(self) -> None:
        """Start the execution monitor."""
        if self._running:
            return
            
        self._running = True
        
        # Subscribe to various system events
        await self.message_bus.subscribe("system.heartbeat", self._handle_agent_heartbeat)
        await self.message_bus.subscribe("task.assigned", self._handle_task_assigned)
        await self.message_bus.subscribe("task.started", self._handle_task_started)
        await self.message_bus.subscribe("task.completed", self._handle_task_completed)
        await self.message_bus.subscribe("task.failed", self._handle_task_failed)
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
        logger.info("Execution monitor started")
    
    async def stop(self) -> None:
        """Stop the execution monitor."""
        self._running = False
        
        await self.message_bus.unsubscribe("system.heartbeat")
        await self.message_bus.unsubscribe("task.assigned")
        await self.message_bus.unsubscribe("task.started")
        await self.message_bus.unsubscribe("task.completed")
        await self.message_bus.unsubscribe("task.failed")
        
        logger.info("Execution monitor stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Update system health metrics
                health = self._calculate_system_health()
                self._system_health_history.append(health)
                
                # Keep only recent history (last 24 hours)
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                self._system_health_history = [
                    h for h in self._system_health_history
                    if h.timestamp > cutoff_time
                ]
                
                # Update agent metrics
                self._update_agent_metrics()
                
                # Check for alerts
                await self._check_alerts(health)
                
                await asyncio.sleep(self._monitor_interval)
                
            except Exception as e:
                logger.error("Error in monitoring loop", error=str(e))
                await asyncio.sleep(self._monitor_interval)
    
    def _calculate_system_health(self) -> SystemHealth:
        """Calculate current system health metrics."""
        now = datetime.utcnow()
        
        # Agent statistics
        total_agents = len(self._agents)
        active_agents = sum(1 for agent in self._agents.values() 
                          if agent.status == AgentStatus.ACTIVE)
        busy_agents = sum(1 for agent in self._agents.values() 
                        if agent.status == AgentStatus.BUSY)
        error_agents = sum(1 for agent in self._agents.values() 
                         if agent.status == AgentStatus.ERROR)
        
        # Team statistics
        total_teams = len(self._teams)
        active_teams = sum(1 for team in self._teams.values() 
                         if len(team.active_tasks) > 0)
        
        # Task statistics
        total_tasks = len(self._tasks)
        pending_tasks = sum(1 for task in self._tasks.values() 
                          if task.status == TaskStatus.PENDING)
        in_progress_tasks = sum(1 for task in self._tasks.values() 
                              if task.status == TaskStatus.IN_PROGRESS)
        completed_tasks = sum(1 for task in self._tasks.values() 
                            if task.status == TaskStatus.COMPLETED)
        failed_tasks = sum(1 for task in self._tasks.values() 
                         if task.status == TaskStatus.FAILED)
        
        # Calculate average task duration
        completed_with_duration = [
            task for task in self._tasks.values()
            if task.status == TaskStatus.COMPLETED and task.duration is not None
        ]
        average_task_duration = (
            sum(task.duration for task in completed_with_duration) / len(completed_with_duration)
            if completed_with_duration else 0.0
        )
        
        # Calculate system load
        max_capacity = sum(agent.max_concurrent_tasks for agent in self._agents.values())
        current_load = sum(len(agent.current_tasks) for agent in self._agents.values())
        system_load = current_load / max_capacity if max_capacity > 0 else 0.0
        
        return SystemHealth(
            timestamp=now,
            total_agents=total_agents,
            active_agents=active_agents,
            busy_agents=busy_agents,
            error_agents=error_agents,
            total_teams=total_teams,
            active_teams=active_teams,
            total_tasks=total_tasks,
            pending_tasks=pending_tasks,
            in_progress_tasks=in_progress_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            average_task_duration=average_task_duration,
            system_load=system_load
        )
    
    def _update_agent_metrics(self) -> None:
        """Update agent performance metrics."""
        for agent_id, agent in self._agents.items():
            if agent_id in self._agent_metrics:
                metrics = self._agent_metrics[agent_id]
                
                # Update basic stats
                metrics.status = agent.status
                metrics.current_tasks = len(agent.current_tasks)
                metrics.completed_tasks = agent.completed_tasks
                metrics.failed_tasks = agent.failed_tasks
                metrics.last_heartbeat = agent.last_heartbeat
                
                # Calculate success rate
                total_tasks = metrics.completed_tasks + metrics.failed_tasks
                metrics.success_rate = (
                    metrics.completed_tasks / total_tasks if total_tasks > 0 else 0.0
                )
                
                # Calculate average task duration for this agent
                agent_tasks = [
                    task for task in self._tasks.values()
                    if task.assigned_agent_id == agent_id and task.duration is not None
                ]
                metrics.average_task_duration = (
                    sum(task.duration for task in agent_tasks) / len(agent_tasks)
                    if agent_tasks else 0.0
                )
    
    async def _check_alerts(self, health: SystemHealth) -> None:
        """Check for system alerts and send notifications."""
        alerts = []
        
        # High system load alert
        if health.system_load > 0.9:
            alerts.append({
                "type": "high_load",
                "severity": "critical",
                "message": f"System load is {health.system_load:.2%}"
            })
        elif health.system_load > 0.7:
            alerts.append({
                "type": "high_load",
                "severity": "warning",
                "message": f"System load is {health.system_load:.2%}"
            })
        
        # Agent errors
        if health.error_agents > 0:
            alerts.append({
                "type": "agent_errors",
                "severity": "critical",
                "message": f"{health.error_agents} agents in error state"
            })
        
        # Task failures
        failure_rate = health.failed_tasks / max(health.total_tasks, 1)
        if failure_rate > 0.2:  # 20% failure rate
            alerts.append({
                "type": "high_failure_rate",
                "severity": "critical",
                "message": f"Task failure rate is {failure_rate:.2%}"
            })
        
        # Send alerts
        for alert in alerts:
            message = Message.create(
                sender_id="monitor",
                message_type="system.alert",
                content=alert
            )
            await self.message_bus.publish("system.alerts", message)
    
    async def _handle_agent_heartbeat(self, message: Message) -> None:
        """Handle agent heartbeat messages."""
        try:
            agent_id = message.content.get("agent_id")
            if agent_id in self._agents:
                agent = self._agents[agent_id]
                agent.last_heartbeat = datetime.utcnow()
                agent.status = AgentStatus(message.content.get("status", AgentStatus.ACTIVE))
                agent.current_tasks = set(message.content.get("current_tasks", []))
                
        except Exception as e:
            logger.error("Error handling heartbeat", error=str(e))
    
    async def _handle_task_assigned(self, message: Message) -> None:
        """Handle task assignment events."""
        try:
            task_data = message.content.get("task", {})
            if "id" in task_data:
                self._tasks[task_data["id"]] = TaskMetrics(
                    task_id=task_data["id"],
                    task_type=task_data.get("task_type", "unknown"),
                    status=TaskStatus.PENDING,
                    assigned_agent_id=task_data.get("assigned_agent_id"),
                    assigned_team_id=task_data.get("assigned_team_id"),
                    created_at=datetime.fromisoformat(task_data.get("created_at", datetime.utcnow().isoformat())),
                    started_at=None,
                    completed_at=None,
                    duration=None,
                    success=None
                )
                
        except Exception as e:
            logger.error("Error handling task assignment", error=str(e))
    
    async def _handle_task_started(self, message: Message) -> None:
        """Handle task start events."""
        try:
            task_id = message.content.get("task_id")
            if task_id in self._tasks:
                self._tasks[task_id].status = TaskStatus.IN_PROGRESS
                self._tasks[task_id].started_at = datetime.utcnow()
                
        except Exception as e:
            logger.error("Error handling task start", error=str(e))
    
    async def _handle_task_completed(self, message: Message) -> None:
        """Handle task completion events."""
        try:
            task_id = message.content.get("task_id")
            if task_id in self._tasks:
                task_metrics = self._tasks[task_id]
                task_metrics.status = TaskStatus.COMPLETED
                task_metrics.completed_at = datetime.utcnow()
                task_metrics.success = True
                
                if task_metrics.started_at:
                    task_metrics.duration = (task_metrics.completed_at - task_metrics.started_at).total_seconds()
                
        except Exception as e:
            logger.error("Error handling task completion", error=str(e))
    
    async def _handle_task_failed(self, message: Message) -> None:
        """Handle task failure events."""
        try:
            task_id = message.content.get("task_id")
            if task_id in self._tasks:
                task_metrics = self._tasks[task_id]
                task_metrics.status = TaskStatus.FAILED
                task_metrics.completed_at = datetime.utcnow()
                task_metrics.success = False
                
                if task_metrics.started_at:
                    task_metrics.duration = (task_metrics.completed_at - task_metrics.started_at).total_seconds()
                
        except Exception as e:
            logger.error("Error handling task failure", error=str(e))
    
    def get_system_health(self) -> SystemHealth:
        """Get current system health."""
        return self._calculate_system_health()
    
    def get_agent_metrics(self, agent_id: Optional[str] = None) -> Dict[str, AgentMetrics]:
        """Get agent metrics."""
        if agent_id:
            return {agent_id: self._agent_metrics[agent_id]} if agent_id in self._agent_metrics else {}
        return self._agent_metrics.copy()
    
    def get_task_metrics(self, task_id: Optional[str] = None) -> Dict[str, TaskMetrics]:
        """Get task metrics."""
        if task_id:
            return {task_id: self._tasks[task_id]} if task_id in self._tasks else {}
        return self._tasks.copy()
    
    def get_health_history(self, hours: int = 1) -> List[SystemHealth]:
        """Get system health history for the specified number of hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [h for h in self._system_health_history if h.timestamp > cutoff_time]