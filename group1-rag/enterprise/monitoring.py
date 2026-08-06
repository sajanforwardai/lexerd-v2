"""
Monitoring & Observability Module for Group One Trading RAG
- Prometheus metrics collection and export
- Structured logging with JSON format
- Performance tracking (latency, throughput, errors)
- Custom business metrics (trades, queries, cache hit rate)
"""

import json
import logging
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime as dt
from functools import wraps
from contextlib import contextmanager
import os

from prometheus_client import (
    Counter, Histogram, Gauge, CollectorRegistry,
    generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client.core import CollectorRegistry
import redis

# ============================================================================
# STRUCTURED LOGGING
# ============================================================================

class StructuredLogger:
    """JSON-based structured logging for enterprise systems."""

    def __init__(self, name: str, redis_client: Optional[redis.Redis] = None):
        self.name = name
        self.redis_client = redis_client
        self.logger = logging.getLogger(name)

    def _format_log(
        self,
        level: str,
        message: str,
        **context
    ) -> str:
        """Format log entry as JSON."""
        log_entry = {
            "timestamp": dt.utcnow().isoformat(),
            "level": level,
            "logger": self.name,
            "message": message,
            "context": context,
            "hostname": os.getenv("HOSTNAME", "unknown"),
            "instance": os.getenv("INSTANCE_NAME", "unknown"),
        }
        return json.dumps(log_entry)

    def info(self, message: str, **context):
        """Log info level message."""
        log_str = self._format_log("INFO", message, **context)
        self.logger.info(log_str)
        if self.redis_client:
            self._send_to_redis("info", message, context)

    def warn(self, message: str, **context):
        """Log warning level message."""
        log_str = self._format_log("WARN", message, **context)
        self.logger.warning(log_str)
        if self.redis_client:
            self._send_to_redis("warn", message, context)

    def error(self, message: str, **context):
        """Log error level message."""
        log_str = self._format_log("ERROR", message, **context)
        self.logger.error(log_str)
        if self.redis_client:
            self._send_to_redis("error", message, context)

    def _send_to_redis(self, level: str, message: str, context: Dict[str, Any]):
        """Send log to Redis for aggregation."""
        try:
            key = f"logs:{level}:{dt.utcnow().strftime('%Y-%m-%d')}"
            log_data = json.dumps({"message": message, "context": context})
            self.redis_client.lpush(key, log_data)
            self.redis_client.expire(key, 604800)  # 7 days
        except Exception as e:
            self.logger.error(f"Failed to send log to Redis: {e}")

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

class MetricsCollector:
    """Centralized metrics collection for Prometheus."""

    def __init__(self, namespace: str = "group1_rag", subsystem: str = "api"):
        self.registry = CollectorRegistry()
        self.namespace = namespace
        self.subsystem = subsystem

        # HTTP metrics
        self.http_requests_total = Counter(
            f"{namespace}_{subsystem}_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
            registry=self.registry
        )

        self.http_request_duration_seconds = Histogram(
            f"{namespace}_{subsystem}_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry
        )

        self.http_request_size_bytes = Histogram(
            f"{namespace}_{subsystem}_http_request_size_bytes",
            "HTTP request size in bytes",
            ["method", "endpoint"],
            registry=self.registry
        )

        self.http_response_size_bytes = Histogram(
            f"{namespace}_{subsystem}_http_response_size_bytes",
            "HTTP response size in bytes",
            ["method", "endpoint"],
            registry=self.registry
        )

        # Query metrics
        self.queries_total = Counter(
            f"{namespace}_{subsystem}_queries_total",
            "Total RAG queries executed",
            ["org_id", "status"],
            registry=self.registry
        )

        self.query_latency_seconds = Histogram(
            f"{namespace}_{subsystem}_query_latency_seconds",
            "Query execution latency",
            ["org_id"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry
        )

        self.cache_hits_total = Counter(
            f"{namespace}_{subsystem}_cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=self.registry
        )

        self.cache_misses_total = Counter(
            f"{namespace}_{subsystem}_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=self.registry
        )

        # Database metrics
        self.db_connections_active = Gauge(
            f"{namespace}_{subsystem}_db_connections_active",
            "Active database connections",
            registry=self.registry
        )

        self.db_query_duration_seconds = Histogram(
            f"{namespace}_{subsystem}_db_query_duration_seconds",
            "Database query duration",
            ["query_type"],
            registry=self.registry
        )

        self.db_errors_total = Counter(
            f"{namespace}_{subsystem}_db_errors_total",
            "Total database errors",
            ["error_type"],
            registry=self.registry
        )

        # Authentication metrics
        self.auth_attempts_total = Counter(
            f"{namespace}_{subsystem}_auth_attempts_total",
            "Total authentication attempts",
            ["status"],
            registry=self.registry
        )

        self.auth_tokens_issued = Counter(
            f"{namespace}_{subsystem}_auth_tokens_issued",
            "Total tokens issued",
            ["token_type"],
            registry=self.registry
        )

        # Rate limiting metrics
        self.rate_limit_exceeded_total = Counter(
            f"{namespace}_{subsystem}_rate_limit_exceeded_total",
            "Total rate limit violations",
            ["user_id"],
            registry=self.registry
        )

        # Business metrics
        self.trades_executed_total = Counter(
            f"{namespace}_{subsystem}_trades_executed_total",
            "Total trades executed",
            ["strategy", "status"],
            registry=self.registry
        )

        self.trade_pnl = Histogram(
            f"{namespace}_{subsystem}_trade_pnl",
            "Trade profit/loss",
            ["strategy"],
            registry=self.registry
        )

        # System health
        self.system_up = Gauge(
            f"{namespace}_{subsystem}_up",
            "System health status",
            registry=self.registry
        )

        self.process_uptime_seconds = Gauge(
            f"{namespace}_{subsystem}_process_uptime_seconds",
            "Process uptime in seconds",
            registry=self.registry
        )

    def generate_metrics(self) -> bytes:
        """Generate Prometheus metrics output."""
        return generate_latest(self.registry)

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================

@dataclass
class PerformanceMetric:
    """Performance metric data class."""
    operation: str
    duration_ms: float
    success: bool
    org_id: str
    user_id: Optional[str] = None
    error_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class PerformanceTracker:
    """Track and report performance metrics."""

    def __init__(self, metrics: MetricsCollector, logger: StructuredLogger):
        self.metrics = metrics
        self.logger = logger
        self.start_times = {}

    @contextmanager
    def track_operation(self, operation: str, org_id: str, user_id: Optional[str] = None):
        """Context manager for tracking operation duration."""
        start_time = time.time()
        operation_id = f"{operation}:{id(self)}"
        self.start_times[operation_id] = start_time

        try:
            yield operation_id
            success = True
            error_type = None
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            duration = (time.time() - start_time) * 1000  # Convert to ms
            metric = PerformanceMetric(
                operation=operation,
                duration_ms=duration,
                success=success,
                org_id=org_id,
                user_id=user_id,
                error_type=error_type
            )
            self.log_metric(metric)
            del self.start_times[operation_id]

    def log_metric(self, metric: PerformanceMetric):
        """Log performance metric."""
        self.logger.info(
            f"Operation completed: {metric.operation}",
            operation=metric.operation,
            duration_ms=metric.duration_ms,
            success=metric.success,
            error_type=metric.error_type
        )

        # Update Prometheus metrics
        if "query" in metric.operation.lower():
            self.metrics.queries_total.labels(
                org_id=metric.org_id,
                status="success" if metric.success else "error"
            ).inc()
            if metric.success:
                self.metrics.query_latency_seconds.labels(
                    org_id=metric.org_id
                ).observe(metric.duration_ms / 1000)

def performance_tracking(operation: str):
    """Decorator for automatic performance tracking."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = kwargs.get('_tracker')
            org_id = kwargs.get('org_id', 'unknown')

            if tracker:
                with tracker.track_operation(operation, org_id):
                    return await func(*args, **kwargs)
            return await func(*args, **kwargs)

        return async_wrapper
    return decorator

# ============================================================================
# ALERTING RULES
# ============================================================================

@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    metric: str
    threshold: float
    duration: int  # seconds
    severity: str  # critical, warning, info
    description: str

class AlertManager:
    """Manage and evaluate alert rules."""

    ALERT_RULES = [
        AlertRule(
            name="HighErrorRate",
            metric="http_requests_total",
            threshold=0.1,  # 10% error rate
            duration=300,
            severity="critical",
            description="Error rate exceeded 10% for 5 minutes"
        ),
        AlertRule(
            name="HighLatency",
            metric="query_latency_seconds",
            threshold=5.0,  # P99 > 5 seconds
            duration=300,
            severity="warning",
            description="Query latency P99 exceeded 5 seconds for 5 minutes"
        ),
        AlertRule(
            name="RateLimitExceeded",
            metric="rate_limit_exceeded_total",
            threshold=100,
            duration=60,
            severity="warning",
            description="More than 100 rate limit violations in 1 minute"
        ),
        AlertRule(
            name="DatabaseConnectionPoolExhausted",
            metric="db_connections_active",
            threshold=19,  # max_conn - 1
            duration=60,
            severity="critical",
            description="Database connection pool nearly exhausted"
        ),
        AlertRule(
            name="CacheMissRate",
            metric="cache_misses_total",
            threshold=0.5,  # 50% miss rate
            duration=600,
            severity="info",
            description="Cache miss rate exceeded 50% for 10 minutes"
        ),
    ]

    def __init__(self, logger: StructuredLogger):
        self.logger = logger
        self.active_alerts = {}

    def check_rule(self, rule: AlertRule, current_value: float) -> bool:
        """Check if alert rule is triggered."""
        if current_value > rule.threshold:
            if rule.name not in self.active_alerts:
                self.logger.warn(
                    f"Alert triggered: {rule.name}",
                    alert_name=rule.name,
                    severity=rule.severity,
                    description=rule.description,
                    current_value=current_value,
                    threshold=rule.threshold
                )
                self.active_alerts[rule.name] = {
                    "triggered_at": dt.utcnow(),
                    "rule": rule
                }
            return True
        else:
            if rule.name in self.active_alerts:
                self.logger.info(
                    f"Alert resolved: {rule.name}",
                    alert_name=rule.name
                )
                del self.active_alerts[rule.name]
            return False

# ============================================================================
# DASHBOARD CONFIGURATION
# ============================================================================

class DashboardGenerator:
    """Generate Grafana dashboard JSON configuration."""

    @staticmethod
    def generate_dashboard() -> Dict[str, Any]:
        """Generate RAG monitoring dashboard configuration."""
        return {
            "dashboard": {
                "title": "Group One Trading RAG Enterprise",
                "tags": ["rag", "enterprise", "trading"],
                "timezone": "browser",
                "panels": [
                    {
                        "title": "Request Rate",
                        "targets": [{
                            "expr": "rate(group1_rag_api_http_requests_total[5m])"
                        }]
                    },
                    {
                        "title": "P99 Latency",
                        "targets": [{
                            "expr": "histogram_quantile(0.99, rate(group1_rag_api_http_request_duration_seconds_bucket[5m]))"
                        }]
                    },
                    {
                        "title": "Error Rate",
                        "targets": [{
                            "expr": "rate(group1_rag_api_http_requests_total{status=~'5..'}[5m])"
                        }]
                    },
                    {
                        "title": "Query Cache Hit Rate",
                        "targets": [{
                            "expr": "rate(group1_rag_api_cache_hits_total[5m]) / (rate(group1_rag_api_cache_hits_total[5m]) + rate(group1_rag_api_cache_misses_total[5m]))"
                        }]
                    },
                    {
                        "title": "Active Database Connections",
                        "targets": [{
                            "expr": "group1_rag_api_db_connections_active"
                        }]
                    },
                    {
                        "title": "Trade Execution Count",
                        "targets": [{
                            "expr": "rate(group1_rag_api_trades_executed_total[5m])"
                        }]
                    },
                ]
            }
        }

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize monitoring components
    metrics = MetricsCollector()
    logger = StructuredLogger("group1_rag")
    tracker = PerformanceTracker(metrics, logger)
    alerts = AlertManager(logger)

    # Example usage
    logger.info("System startup", version="4.0.0")
    metrics.http_requests_total.labels(method="GET", endpoint="/query", status="200").inc()
    metrics.query_latency_seconds.labels(org_id="org-1").observe(2.5)

    # Export metrics
    metrics_output = metrics.generate_metrics()
    print(metrics_output.decode('utf-8'))
