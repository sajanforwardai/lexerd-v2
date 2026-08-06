"""
Enterprise API Server for Group One Trading RAG
- FastAPI with JWT authentication and role-based access control
- Rate limiting (100 req/s per user, 1000 req/s global)
- Audit logging for all queries, trades, and parameter changes
- OpenTelemetry instrumentation for distributed tracing
- Structured JSON logging
"""

import os
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from enum import Enum
from functools import wraps
import hashlib
import hmac

import jwt
from fastapi import (
    FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
)
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import redis
from datetime import datetime as dt

# OpenTelemetry
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_structured_logging():
    """Configure JSON structured logging."""
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_obj = {
                "timestamp": dt.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "process_id": os.getpid(),
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_obj)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

logger = setup_structured_logging()

# ============================================================================
# OPENTELEMETRY SETUP
# ============================================================================

def setup_tracing():
    """Configure OpenTelemetry with Jaeger exporter."""
    jaeger_exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "localhost"),
        agent_port=int(os.getenv("JAEGER_PORT", 6831)),
    )
    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        BatchSpanProcessor(jaeger_exporter)
    )
    return trace.get_tracer(__name__)

tracer = setup_tracing()

# ============================================================================
# DATABASE CONNECTION POOL
# ============================================================================

class DatabasePool:
    """PostgreSQL connection pool manager."""

    def __init__(self, min_conn=5, max_conn=20):
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:changeme@localhost/group1_rag")
        self.pool = SimpleConnectionPool(min_conn, max_conn, db_url)

    def get_connection(self):
        return self.pool.getconn()

    def return_connection(self, conn):
        self.pool.putconn(conn)

    def close_all(self):
        self.pool.closeall()

db_pool = DatabasePool()

# ============================================================================
# REDIS CLIENT
# ============================================================================

redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True,
    socket_keepalive=True,
    socket_keepalive_options={
        1: 1,  # TCP_KEEPIDLE
        2: 1,  # TCP_KEEPINTVL
        3: 3,  # TCP_KEEPCNT
    }
)

# ============================================================================
# ROLE-BASED ACCESS CONTROL
# ============================================================================

class UserRole(str, Enum):
    """User roles with permission levels."""
    ADMIN = "admin"
    RISK_OFFICER = "risk_officer"
    TRADER = "trader"
    ANALYST = "analyst"
    VIEWER = "viewer"

ROLE_PERMISSIONS = {
    UserRole.ADMIN: ["read", "write", "execute", "delete", "admin"],
    UserRole.RISK_OFFICER: ["read", "write", "execute", "audit"],
    UserRole.TRADER: ["read", "write", "execute"],
    UserRole.ANALYST: ["read", "write"],
    UserRole.VIEWER: ["read"],
}

# ============================================================================
# DATA MODELS
# ============================================================================

class User(BaseModel):
    """User model."""
    id: str
    email: str
    role: UserRole
    org_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AuthToken(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class LoginRequest(BaseModel):
    """Login request model."""
    email: str
    password: str

class AuditLog(BaseModel):
    """Audit log entry."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    org_id: str
    action: str
    resource: str
    details: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ip_address: str
    status: str = "success"

class QueryRequest(BaseModel):
    """Query request model."""
    query: str
    parameters: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    """Query response model."""
    request_id: str
    result: Dict[str, Any]
    latency_ms: float
    cached: bool = False

# ============================================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================================

class JWTHandler:
    """JWT token management."""

    def __init__(self):
        self.secret = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
        self.algorithm = "HS256"
        self.access_token_expire = 3600  # 1 hour
        self.refresh_token_expire = 604800  # 7 days

    def create_tokens(self, user_id: str, email: str, role: UserRole, org_id: str):
        """Create access and refresh tokens."""
        now = datetime.utcnow()

        # Access token
        access_payload = {
            "user_id": user_id,
            "email": email,
            "role": role.value,
            "org_id": org_id,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(seconds=self.access_token_expire),
            "jti": str(uuid.uuid4()),
        }
        access_token = jwt.encode(access_payload, self.secret, algorithm=self.algorithm)

        # Refresh token
        refresh_payload = {
            "user_id": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(seconds=self.refresh_token_expire),
            "jti": str(uuid.uuid4()),
        }
        refresh_token = jwt.encode(refresh_payload, self.secret, algorithm=self.algorithm)

        return access_token, refresh_token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

jwt_handler = JWTHandler()

# ============================================================================
# RATE LIMITING
# ============================================================================

limiter = Limiter(key_func=get_remote_address)

class RateLimitManager:
    """Advanced rate limiting with per-user and global limits."""

    def __init__(self, redis_client, user_limit=100, global_limit=1000):
        self.redis = redis_client
        self.user_limit = user_limit  # req/s per user
        self.global_limit = global_limit  # req/s global

    def check_rate_limit(self, user_id: str, org_id: str) -> bool:
        """Check if request is within rate limits."""
        now = int(dt.now().timestamp())

        # Per-user limit
        user_key = f"rate_limit:user:{user_id}:{now}"
        user_count = self.redis.incr(user_key)
        if user_count == 1:
            self.redis.expire(user_key, 1)

        if user_count > self.user_limit:
            return False

        # Global limit
        global_key = f"rate_limit:global:{now}"
        global_count = self.redis.incr(global_key)
        if global_count == 1:
            self.redis.expire(global_key, 1)

        if global_count > self.global_limit:
            return False

        return True

rate_limit_manager = RateLimitManager(redis_client)

# ============================================================================
# AUDIT LOGGING
# ============================================================================

class AuditLogger:
    """Centralized audit logging."""

    def __init__(self, db_pool, redis_client):
        self.db_pool = db_pool
        self.redis = redis_client

    def log_action(self, audit_log: AuditLog, background_tasks: BackgroundTasks):
        """Log audit action asynchronously."""
        background_tasks.add_task(self._persist_audit_log, audit_log)
        self._cache_audit_log(audit_log)

    def _cache_audit_log(self, audit_log: AuditLog):
        """Cache recent audit logs in Redis."""
        key = f"audit_log:{audit_log.user_id}:{audit_log.org_id}"
        self.redis.lpush(key, json.dumps(audit_log.dict(), default=str))
        self.redis.ltrim(key, 0, 999)  # Keep last 1000
        self.redis.expire(key, 86400)  # 24 hours

    def _persist_audit_log(self, audit_log: AuditLog):
        """Persist audit log to database."""
        conn = self.db_pool.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_logs
                    (id, user_id, org_id, action, resource, details, timestamp, ip_address, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    audit_log.id, audit_log.user_id, audit_log.org_id,
                    audit_log.action, audit_log.resource,
                    json.dumps(audit_log.details), audit_log.timestamp,
                    audit_log.ip_address, audit_log.status
                ))
                conn.commit()
                logger.info(f"Audit log persisted: {audit_log.id}")
        except Exception as e:
            logger.error(f"Failed to persist audit log: {e}")
            conn.rollback()
        finally:
            self.db_pool.return_connection(conn)

audit_logger = AuditLogger(db_pool, redis_client)

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)) -> User:
    """Extract and validate current user from JWT token."""
    payload = jwt_handler.verify_token(credentials.credentials)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    return User(
        id=payload["user_id"],
        email=payload["email"],
        role=UserRole(payload["role"]),
        org_id=payload["org_id"],
    )

async def check_permission(required_permission: str):
    """Create permission checker dependency."""
    async def _check(user: User = Depends(get_current_user)):
        if required_permission not in ROLE_PERMISSIONS.get(user.role, []):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Group One Trading RAG Enterprise API",
    version="4.0.0",
    description="Enterprise-grade RAG API with multi-user access, HA, and monitoring"
)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)
RedisInstrumentor().instrument()

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
    )

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    try:
        # Check database
        conn = db_pool.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        db_pool.return_connection(conn)

        # Check Redis
        redis_client.ping()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "instance": os.getenv("INSTANCE_NAME", "unknown"),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "detail": str(e)}
        )

@app.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes."""
    try:
        conn = db_pool.get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        db_pool.return_connection(conn)
        redis_client.ping()
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})

@app.get("/metrics")
async def metrics_endpoint():
    """Metrics endpoint for Prometheus."""
    # This would be populated by the monitoring module
    return {
        "requests_total": redis_client.get("metrics:requests_total") or 0,
        "requests_errors": redis_client.get("metrics:requests_errors") or 0,
        "latency_p99_ms": redis_client.get("metrics:latency_p99_ms") or 0,
    }

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/login", response_model=AuthToken)
async def login(request: LoginRequest, background_tasks: BackgroundTasks):
    """Authenticate user and return JWT tokens."""
    with tracer.start_as_current_span("login"):
        # In production, verify credentials against secure password hash
        # This is a simplified example
        user_id = str(uuid.uuid4())

        access_token, refresh_token = jwt_handler.create_tokens(
            user_id=user_id,
            email=request.email,
            role=UserRole.TRADER,  # Default role
            org_id="org-1"  # Extract from request context
        )

        # Log authentication attempt
        audit_log = AuditLog(
            user_id=user_id,
            org_id="org-1",
            action="LOGIN",
            resource="auth",
            details={"email": request.email},
            ip_address="",  # Extract from request
            status="success"
        )
        audit_logger.log_action(audit_log, background_tasks)

        return AuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600
        )

@app.post("/auth/refresh", response_model=AuthToken)
async def refresh_token(credentials: HTTPAuthCredentials = Depends(security)):
    """Refresh access token using refresh token."""
    payload = jwt_handler.verify_token(credentials.credentials)

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token, new_refresh = jwt_handler.create_tokens(
        user_id=payload["user_id"],
        email=payload.get("email", ""),
        role=UserRole.TRADER,
        org_id=payload.get("org_id", "")
    )

    return AuthToken(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=3600
    )

# ============================================================================
# QUERY ENDPOINTS
# ============================================================================

@app.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """Execute a RAG query with caching and audit logging."""
    request_id = str(uuid.uuid4())

    with tracer.start_as_current_span("query_execution") as span:
        span.set_attribute("request_id", request_id)
        span.set_attribute("user_id", user.id)

        # Check rate limits
        if not rate_limit_manager.check_rate_limit(user.id, user.org_id):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # Check cache
        cache_key = f"query_cache:{user.org_id}:{hashlib.md5(req.query.encode()).hexdigest()}"
        cached_result = redis_client.get(cache_key)

        if cached_result:
            logger.info(f"Cache hit for query: {request_id}")
            return QueryResponse(
                request_id=request_id,
                result=json.loads(cached_result),
                latency_ms=0.1,
                cached=True
            )

        # Execute query (placeholder)
        start_time = dt.now()
        result = {
            "status": "success",
            "data": {
                "insights": "Sample RAG insights from retrieval and reasoning pipeline",
                "confidence": 0.95,
                "sources": 5,
            }
        }
        latency_ms = (dt.now() - start_time).total_seconds() * 1000

        # Cache result
        redis_client.setex(cache_key, 3600, json.dumps(result))

        # Log audit
        audit_log = AuditLog(
            user_id=user.id,
            org_id=user.org_id,
            action="QUERY_EXECUTE",
            resource="query",
            details={
                "query": req.query[:100],  # Truncate for privacy
                "request_id": request_id,
                "latency_ms": latency_ms,
            },
            ip_address="",
            status="success"
        )
        audit_logger.log_action(audit_log, background_tasks)

        return QueryResponse(
            request_id=request_id,
            result=result,
            latency_ms=latency_ms,
            cached=False
        )

@app.get("/audit/logs")
async def get_audit_logs(
    user: User = Depends(get_current_user),
    limit: int = 100
):
    """Retrieve audit logs for current user."""
    if user.role != UserRole.ADMIN and user.role != UserRole.RISK_OFFICER:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    key = f"audit_log:{user.id}:{user.org_id}"
    logs = redis_client.lrange(key, 0, limit - 1)

    return {
        "logs": [json.loads(log) for log in logs],
        "count": len(logs)
    }

# ============================================================================
# SHUTDOWN
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    db_pool.close_all()
    redis_client.close()
    logger.info("Application shutdown complete")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 4))

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=port,
        workers=workers,
        log_config=None,  # Use our structured logging
    )
