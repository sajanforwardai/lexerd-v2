"""
High Availability Manager for Group One Trading RAG
- Load balancing across multiple API instances
- Circuit breaker pattern for graceful degradation
- Health monitoring and automatic failover
- Request routing with retry logic
- Connection pooling and failover
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime as dt, timedelta
from functools import wraps
import random

import aiohttp
import redis

# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls

class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[dt] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise Exception(f"Circuit breaker '{self.name}' is OPEN")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = dt.utcnow()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True

        time_since_failure = (dt.utcnow() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.config.timeout

    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }

# ============================================================================
# LOAD BALANCER
# ============================================================================

@dataclass
class Instance:
    """API instance information."""
    id: str
    host: str
    port: int
    weight: float = 1.0
    healthy: bool = True
    failure_count: int = 0
    last_check: Optional[dt] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

class LoadBalancer:
    """Load balancer with multiple strategies."""

    def __init__(self, instances: List[Instance]):
        self.instances = instances
        self.current_index = 0
        self.request_count = 0

    def round_robin(self) -> Instance:
        """Round-robin load balancing."""
        healthy = [i for i in self.instances if i.healthy]
        if not healthy:
            raise Exception("No healthy instances available")

        instance = healthy[self.current_index % len(healthy)]
        self.current_index += 1
        return instance

    def weighted_round_robin(self) -> Instance:
        """Weighted round-robin load balancing."""
        healthy = [i for i in self.instances if i.healthy]
        if not healthy:
            raise Exception("No healthy instances available")

        total_weight = sum(i.weight for i in healthy)
        pick = random.uniform(0, total_weight)
        current = 0

        for instance in healthy:
            current += instance.weight
            if pick <= current:
                return instance

        return healthy[-1]

    def least_connections(self) -> Instance:
        """Least connections load balancing."""
        healthy = [i for i in self.instances if i.healthy]
        if not healthy:
            raise Exception("No healthy instances available")

        # In production, track active connections
        return min(healthy, key=lambda i: i.failure_count)

    def select_instance(self, strategy: str = "round_robin") -> Instance:
        """Select instance based on strategy."""
        if strategy == "round_robin":
            return self.round_robin()
        elif strategy == "weighted":
            return self.weighted_round_robin()
        elif strategy == "least_connections":
            return self.least_connections()
        else:
            return self.round_robin()

# ============================================================================
# HEALTH CHECKER
# ============================================================================

class HealthChecker:
    """Monitor instance health and trigger failover."""

    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 5,
        failure_threshold: int = 3,
    ):
        self.check_interval = check_interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.check_tasks: Dict[str, asyncio.Task] = {}

    async def check_instance(self, instance: Instance) -> bool:
        """Check if instance is healthy."""
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                async with session.get(f"{instance.url}/health") as resp:
                    if resp.status == 200:
                        instance.healthy = True
                        instance.failure_count = 0
                        instance.last_check = dt.utcnow()
                        return True
        except Exception:
            pass

        instance.failure_count += 1
        if instance.failure_count >= self.failure_threshold:
            instance.healthy = False

        instance.last_check = dt.utcnow()
        return False

    async def monitor_instances(self, instances: List[Instance]):
        """Continuously monitor instance health."""
        while True:
            tasks = [self.check_instance(inst) for inst in instances]
            await asyncio.gather(*tasks)
            await asyncio.sleep(self.check_interval)

# ============================================================================
# RETRY STRATEGY
# ============================================================================

class RetryConfig:
    """Retry configuration."""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 0.1,
        max_delay: float = 10.0,
        backoff_factor: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

class RetryStrategy:
    """Exponential backoff retry strategy."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ):
        """Execute function with exponential backoff retry."""
        last_exception = None
        delay = self.config.initial_delay

        for attempt in range(self.config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self.config.max_attempts - 1:
                    await asyncio.sleep(delay)
                    delay = min(delay * self.config.backoff_factor, self.config.max_delay)

        raise last_exception

# ============================================================================
# HA MANAGER
# ============================================================================

class HAManager:
    """Comprehensive high availability manager."""

    def __init__(
        self,
        instances: List[Instance],
        redis_client: Optional[redis.Redis] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.instances = instances
        self.redis_client = redis_client
        self.logger = logger or logging.getLogger(__name__)

        self.load_balancer = LoadBalancer(instances)
        self.health_checker = HealthChecker()
        self.retry_strategy = RetryStrategy()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            inst.id: CircuitBreaker(f"cb-{inst.id}") for inst in instances
        }

        self.monitoring_task: Optional[asyncio.Task] = None

    async def start_monitoring(self):
        """Start background health monitoring."""
        self.monitoring_task = asyncio.create_task(
            self.health_checker.monitor_instances(self.instances)
        )
        self.logger.info("HA monitoring started")

    async def stop_monitoring(self):
        """Stop background monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        self.logger.info("HA monitoring stopped")

    async def forward_request(
        self,
        method: str,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Any] = None,
        strategy: str = "round_robin",
    ) -> Dict[str, Any]:
        """Forward request to selected instance with retries and circuit breaking."""
        last_error = None

        for attempt in range(3):
            try:
                instance = self.load_balancer.select_instance(strategy)
                cb = self.circuit_breakers[instance.id]

                async def make_request():
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as session:
                        url = f"{instance.url}{path}"
                        async with session.request(
                            method,
                            url,
                            headers=headers,
                            json=data
                        ) as resp:
                            return await resp.json()

                result = await cb.call(make_request)
                return result

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Request failed (attempt {attempt + 1})",
                    error=str(e)
                )
                await asyncio.sleep(0.1 * (2 ** attempt))

        raise last_error or Exception("Request failed after retries")

    def get_status(self) -> Dict[str, Any]:
        """Get HA status and circuit breaker states."""
        return {
            "instances": [
                {
                    "id": inst.id,
                    "url": inst.url,
                    "healthy": inst.healthy,
                    "failure_count": inst.failure_count,
                    "last_check": inst.last_check.isoformat() if inst.last_check else None,
                }
                for inst in self.instances
            ],
            "circuit_breakers": [
                self.circuit_breakers[inst.id].get_state()
                for inst in self.instances
            ],
            "healthy_instances": sum(1 for inst in self.instances if inst.healthy),
            "total_instances": len(self.instances),
        }

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    import asyncio

    async def main():
        # Initialize instances
        instances = [
            Instance(id="api-1", host="localhost", port=8001),
            Instance(id="api-2", host="localhost", port=8002),
        ]

        # Create HA manager
        ha_manager = HAManager(instances)
        await ha_manager.start_monitoring()

        # Get status
        status = ha_manager.get_status()
        print("HA Status:", status)

        # Forward request
        try:
            response = await ha_manager.forward_request(
                method="GET",
                path="/health",
                strategy="round_robin"
            )
            print("Response:", response)
        except Exception as e:
            print("Error:", e)

        await ha_manager.stop_monitoring()

    asyncio.run(main())
