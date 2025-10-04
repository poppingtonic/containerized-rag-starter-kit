"""
Audit Logger

Handles recording and storage of audit events.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from .models import AuditEvent, AuditLevel, EventType

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Audit logging service with multiple backends.

    Supports:
    - PostgreSQL database
    - File-based logging
    - External SIEM systems
    - Real-time streaming to analytics
    """

    def __init__(
        self,
        db_connection_string: Optional[str] = None,
        log_file_path: Optional[str] = None,
        siem_endpoint: Optional[str] = None,
        default_audit_level: AuditLevel = AuditLevel.DETAILED
    ):
        self.db_connection_string = db_connection_string
        self.log_file_path = log_file_path
        self.siem_endpoint = siem_endpoint
        self.default_audit_level = default_audit_level
        self._initialized = False
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._background_task: Optional[asyncio.Task] = None

    async def initialize(self) -> bool:
        """Initialize audit logger and create database tables"""
        if self.db_connection_string:
            try:
                conn = psycopg2.connect(self.db_connection_string)
                cur = conn.cursor()

                # Create audit_events table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id VARCHAR(255) PRIMARY KEY,
                        event_type VARCHAR(100) NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        user_id VARCHAR(255),
                        user_email VARCHAR(255),
                        user_roles TEXT[],
                        resource_type VARCHAR(100),
                        resource_id VARCHAR(255),
                        store_id VARCHAR(255),
                        action VARCHAR(255),
                        result VARCHAR(50),
                        reason TEXT,
                        query_text TEXT,
                        query_results_count INTEGER,
                        ip_address VARCHAR(50),
                        user_agent TEXT,
                        session_id VARCHAR(255),
                        workflow_id VARCHAR(255),
                        suspicious BOOLEAN DEFAULT FALSE,
                        pii_accessed BOOLEAN DEFAULT FALSE,
                        sensitive_data BOOLEAN DEFAULT FALSE,
                        metadata JSONB,
                        audit_level VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for common queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_events(timestamp DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_user
                    ON audit_events(user_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_event_type
                    ON audit_events(event_type)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_store
                    ON audit_events(store_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_suspicious
                    ON audit_events(suspicious) WHERE suspicious = TRUE
                """)

                conn.commit()
                cur.close()
                conn.close()

                logger.info("Audit logger initialized successfully")
                self._initialized = True

                # Start background processing
                self._background_task = asyncio.create_task(self._process_events())

                return True

            except Exception as e:
                logger.error(f"Failed to initialize audit logger: {str(e)}")
                return False

        return True

    async def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event asynchronously.

        Args:
            event: AuditEvent to log
        """
        # Add to queue for background processing
        await self._event_queue.put(event)

    async def log_query(
        self,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        query_text: str,
        store_id: str,
        results_count: int,
        workflow_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method for logging query events"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.QUERY,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_email=user_email,
            user_roles=user_roles,
            store_id=store_id,
            query_text=query_text,
            query_results_count=results_count,
            workflow_id=workflow_id,
            ip_address=context.get("ip_address") if context else None,
            user_agent=context.get("user_agent") if context else None,
            session_id=context.get("session_id") if context else None,
            audit_level=self.default_audit_level
        )
        await self.log_event(event)

    async def log_access(
        self,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        resource_type: str,
        resource_id: str,
        store_id: str,
        result: str,
        reason: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method for logging access events"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.DOCUMENT_ACCESS,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_email=user_email,
            user_roles=user_roles,
            resource_type=resource_type,
            resource_id=resource_id,
            store_id=store_id,
            result=result,
            reason=reason,
            ip_address=context.get("ip_address") if context else None,
            user_agent=context.get("user_agent") if context else None,
            session_id=context.get("session_id") if context else None,
            audit_level=self.default_audit_level
        )
        await self.log_event(event)

    async def log_permission_check(
        self,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        resource_type: str,
        resource_id: str,
        action: str,
        allowed: bool,
        reason: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method for logging permission checks"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PERMISSION_DENIED if not allowed else EventType.PERMISSION_CHECK,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_email=user_email,
            user_roles=user_roles,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result="denied" if not allowed else "allowed",
            reason=reason,
            suspicious=not allowed,
            ip_address=context.get("ip_address") if context else None,
            audit_level=self.default_audit_level
        )
        await self.log_event(event)

    async def log_security_event(
        self,
        event_type: EventType,
        user_id: Optional[str],
        description: str,
        suspicious: bool = True,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Convenience method for logging security events"""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_email=context.get("user_email") if context else None,
            reason=description,
            suspicious=suspicious,
            ip_address=context.get("ip_address") if context else None,
            user_agent=context.get("user_agent") if context else None,
            audit_level=AuditLevel.FORENSIC,
            metadata=context or {}
        )
        await self.log_event(event)

    async def _process_events(self) -> None:
        """Background task to process audit events"""
        while True:
            try:
                event = await self._event_queue.get()

                # Write to database
                if self.db_connection_string:
                    await self._write_to_database(event)

                # Write to log file
                if self.log_file_path:
                    await self._write_to_file(event)

                # Send to SIEM
                if self.siem_endpoint:
                    await self._send_to_siem(event)

                self._event_queue.task_done()

            except Exception as e:
                logger.error(f"Error processing audit event: {str(e)}")

    async def _write_to_database(self, event: AuditEvent) -> None:
        """Write event to PostgreSQL database"""
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO audit_events (
                    event_id, event_type, timestamp, user_id, user_email, user_roles,
                    resource_type, resource_id, store_id, action, result, reason,
                    query_text, query_results_count, ip_address, user_agent,
                    session_id, workflow_id, suspicious, pii_accessed,
                    sensitive_data, metadata, audit_level
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                event.event_id, event.event_type.value, event.timestamp,
                event.user_id, event.user_email, event.user_roles,
                event.resource_type, event.resource_id, event.store_id,
                event.action, event.result, event.reason,
                event.query_text, event.query_results_count,
                event.ip_address, event.user_agent, event.session_id,
                event.workflow_id, event.suspicious, event.pii_accessed,
                event.sensitive_data, json.dumps(event.metadata),
                event.audit_level.value
            ))

            conn.commit()
            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error writing audit event to database: {str(e)}")

    async def _write_to_file(self, event: AuditEvent) -> None:
        """Write event to log file"""
        try:
            with open(self.log_file_path, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Error writing audit event to file: {str(e)}")

    async def _send_to_siem(self, event: AuditEvent) -> None:
        """Send event to external SIEM system"""
        # Placeholder - would implement HTTP POST to SIEM endpoint
        pass

    async def shutdown(self) -> None:
        """Shutdown audit logger and flush events"""
        if self._background_task:
            await self._event_queue.join()
            self._background_task.cancel()
        logger.info("Audit logger shut down")
