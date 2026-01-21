"""Bitcoin Agents lifecycle management service.

Handles background jobs for death checking, alerts, and stats aggregation.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from app.lib.logger import configure_logger
from app.tools.bitcoin_agents import (
    get_agent_state,
    get_computed_state,
    get_global_stats,
    check_and_process_deaths,
)

logger = configure_logger(__name__)

# Alert thresholds
HUNGER_WARNING_THRESHOLD = 30  # Warn when hunger < 30
HUNGER_CRITICAL_THRESHOLD = 10  # Critical when hunger < 10
HEALTH_WARNING_THRESHOLD = 50  # Warn when health < 50


class LifecycleService:
    """Service for managing Bitcoin Agent lifecycles."""

    def __init__(self, network: str = "mainnet"):
        self.network = network
        # Track warned agents to avoid spam
        self._warned_agents: Dict[int, datetime] = {}

    async def check_all_agents_for_death(self) -> Dict[str, Any]:
        """Background job: Check all agents for death.

        Should be run hourly or more frequently.

        Returns:
            Summary of the check including deaths processed
        """
        logger.info(f"Running death check job on {self.network}")

        try:
            result = await check_and_process_deaths(self.network)

            logger.info(
                f"Death check complete: {result['deaths_processed']} deaths processed",
                extra={"result": result},
            )

            return result

        except Exception as e:
            logger.error(f"Death check job failed: {e}", exc_info=e)
            return {
                "error": str(e),
                "checked": 0,
                "deaths_processed": 0,
            }

    async def get_hungry_agents(self, threshold: int = HUNGER_WARNING_THRESHOLD) -> List[Dict[str, Any]]:
        """Get all agents with hunger below threshold.

        Used for alert system.

        Args:
            threshold: Hunger level threshold (default 30)

        Returns:
            List of agents needing attention
        """
        try:
            # TODO: Implement actual query
            # 1. Get all alive agents from cache/db
            # 2. For each, get computed state
            # 3. Filter by hunger < threshold

            hungry_agents: List[Dict[str, Any]] = []
            logger.debug(f"Found {len(hungry_agents)} hungry agents (hunger < {threshold})")
            return hungry_agents

        except Exception as e:
            logger.error(f"Failed to get hungry agents: {e}", exc_info=e)
            return []

    async def get_critical_agents(self) -> List[Dict[str, Any]]:
        """Get agents in critical condition (very low hunger or health).

        Returns:
            List of agents needing immediate attention
        """
        try:
            # TODO: Implement actual query
            critical_agents: List[Dict[str, Any]] = []

            # Filter for critical hunger or low health
            logger.debug(f"Found {len(critical_agents)} critical agents")
            return critical_agents

        except Exception as e:
            logger.error(f"Failed to get critical agents: {e}", exc_info=e)
            return []

    async def send_hunger_alerts(self) -> Dict[str, int]:
        """Send alerts for hungry agents.

        Should be run periodically (e.g., every 6 hours).
        Avoids spamming by tracking warned agents.

        Returns:
            Summary of alerts sent
        """
        logger.info(f"Running hunger alert job on {self.network}")

        warnings_sent = 0
        critical_sent = 0

        try:
            # Get critical agents first
            critical = await self.get_critical_agents()
            for agent in critical:
                agent_id = agent.get("agent_id")
                if agent_id and self._should_alert(agent_id, critical=True):
                    await self._send_critical_alert(agent)
                    critical_sent += 1
                    self._mark_alerted(agent_id)

            # Get warning-level agents
            hungry = await self.get_hungry_agents(HUNGER_WARNING_THRESHOLD)
            for agent in hungry:
                agent_id = agent.get("agent_id")
                if agent_id and self._should_alert(agent_id, critical=False):
                    await self._send_warning_alert(agent)
                    warnings_sent += 1
                    self._mark_alerted(agent_id)

            logger.info(
                f"Alert job complete: {critical_sent} critical, {warnings_sent} warnings",
            )

            return {
                "critical_alerts": critical_sent,
                "warning_alerts": warnings_sent,
            }

        except Exception as e:
            logger.error(f"Alert job failed: {e}", exc_info=e)
            return {
                "error": str(e),
                "critical_alerts": 0,
                "warning_alerts": 0,
            }

    async def aggregate_stats(self) -> Dict[str, Any]:
        """Aggregate and cache global statistics.

        Should be run periodically to update cached stats.

        Returns:
            Current statistics
        """
        try:
            stats = await get_global_stats(self.network)

            logger.info(
                f"Stats aggregated: {stats.get('total-agents', 0)} total, "
                f"{stats.get('alive-count', 0)} alive, "
                f"{stats.get('total-deaths', 0)} deaths",
            )

            return {
                "total_agents": stats.get("total-agents", 0),
                "alive_count": stats.get("alive-count", 0),
                "total_deaths": stats.get("total-deaths", 0),
                "total_feedings": stats.get("total-feedings", 0),
                "aggregated_at": datetime.utcnow().isoformat(),
                "network": self.network,
            }

        except Exception as e:
            logger.error(f"Stats aggregation failed: {e}", exc_info=e)
            return {"error": str(e)}

    def _should_alert(self, agent_id: int, critical: bool) -> bool:
        """Check if we should send an alert for this agent.

        Avoids spamming by enforcing cooldown periods.
        """
        from datetime import timedelta

        if agent_id not in self._warned_agents:
            return True

        last_warned = self._warned_agents[agent_id]
        cooldown = timedelta(hours=1) if critical else timedelta(hours=6)

        return datetime.utcnow() - last_warned > cooldown

    def _mark_alerted(self, agent_id: int):
        """Mark an agent as having been alerted."""
        self._warned_agents[agent_id] = datetime.utcnow()

    async def _send_warning_alert(self, agent: Dict[str, Any]):
        """Send a warning alert for a hungry agent.

        TODO: Implement actual notification (email, push, etc.)
        """
        logger.info(
            f"HUNGER WARNING: Agent {agent.get('agent_id')} ({agent.get('name')}) "
            f"has low hunger: {agent.get('computed_hunger')}%"
        )

    async def _send_critical_alert(self, agent: Dict[str, Any]):
        """Send a critical alert for an agent in danger.

        TODO: Implement actual notification (email, push, etc.)
        """
        logger.warning(
            f"CRITICAL: Agent {agent.get('agent_id')} ({agent.get('name')}) "
            f"is in critical condition! Hunger: {agent.get('computed_hunger')}%, "
            f"Health: {agent.get('computed_health')}%"
        )


# Singleton instances per network
_services: Dict[str, LifecycleService] = {}


def get_lifecycle_service(network: str = "mainnet") -> LifecycleService:
    """Get or create the lifecycle service for a network."""
    if network not in _services:
        _services[network] = LifecycleService(network)
    return _services[network]


# =============================================================================
# Background Job Registration
# =============================================================================


async def death_check_job():
    """Background job function for death checking.

    Register this with the job management system.
    """
    mainnet_service = get_lifecycle_service("mainnet")
    testnet_service = get_lifecycle_service("testnet")

    mainnet_result = await mainnet_service.check_all_agents_for_death()
    testnet_result = await testnet_service.check_all_agents_for_death()

    return {
        "mainnet": mainnet_result,
        "testnet": testnet_result,
    }


async def hunger_alert_job():
    """Background job function for hunger alerts.

    Register this with the job management system.
    """
    mainnet_service = get_lifecycle_service("mainnet")
    testnet_service = get_lifecycle_service("testnet")

    mainnet_result = await mainnet_service.send_hunger_alerts()
    testnet_result = await testnet_service.send_hunger_alerts()

    return {
        "mainnet": mainnet_result,
        "testnet": testnet_result,
    }


async def stats_aggregation_job():
    """Background job function for stats aggregation.

    Register this with the job management system.
    """
    mainnet_service = get_lifecycle_service("mainnet")
    testnet_service = get_lifecycle_service("testnet")

    mainnet_result = await mainnet_service.aggregate_stats()
    testnet_result = await testnet_service.aggregate_stats()

    return {
        "mainnet": mainnet_result,
        "testnet": testnet_result,
    }
