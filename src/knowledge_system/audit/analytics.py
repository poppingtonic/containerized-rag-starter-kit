"""
Audit Analytics

Provides analytics and reporting on audit events.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from .models import AuditStatistics, EventType

logger = logging.getLogger(__name__)


class AuditAnalytics:
    """
    Analytics and reporting for audit events.

    Features:
    - Access pattern analysis
    - Security anomaly detection
    - Compliance reporting
    - User behavior analytics
    """

    def __init__(self, db_connection_string: str):
        self.db_connection_string = db_connection_string

    async def get_statistics(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> AuditStatistics:
        """
        Get comprehensive audit statistics for a time range.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            AuditStatistics object
        """
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Total events
            cur.execute("""
                SELECT COUNT(*) as total
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s
            """, (start_time, end_time))
            total = cur.fetchone()["total"]

            # Events by type
            cur.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s
                GROUP BY event_type
                ORDER BY count DESC
            """, (start_time, end_time))
            events_by_type = {row["event_type"]: row["count"] for row in cur.fetchall()}

            # Events by user
            cur.execute("""
                SELECT user_id, COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 20
            """, (start_time, end_time))
            events_by_user = {row["user_id"]: row["count"] for row in cur.fetchall()}

            # Events by store
            cur.execute("""
                SELECT store_id, COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND store_id IS NOT NULL
                GROUP BY store_id
                ORDER BY count DESC
            """, (start_time, end_time))
            events_by_store = {row["store_id"]: row["count"] for row in cur.fetchall()}

            # Failed accesses
            cur.execute("""
                SELECT COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND result = 'failure'
            """, (start_time, end_time))
            failed_accesses = cur.fetchone()["count"]

            # Denied permissions
            cur.execute("""
                SELECT COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND result = 'denied'
            """, (start_time, end_time))
            denied_permissions = cur.fetchone()["count"]

            # Suspicious events
            cur.execute("""
                SELECT COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND suspicious = TRUE
            """, (start_time, end_time))
            suspicious_events = cur.fetchone()["count"]

            # PII accesses
            cur.execute("""
                SELECT COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND pii_accessed = TRUE
            """, (start_time, end_time))
            pii_accesses = cur.fetchone()["count"]

            # Top queries
            cur.execute("""
                SELECT query_text, COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s
                    AND event_type = 'query'
                    AND query_text IS NOT NULL
                GROUP BY query_text
                ORDER BY count DESC
                LIMIT 10
            """, (start_time, end_time))
            top_queries = [dict(row) for row in cur.fetchall()]

            # Top users
            cur.execute("""
                SELECT user_email, user_id, COUNT(*) as event_count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s AND user_id IS NOT NULL
                GROUP BY user_email, user_id
                ORDER BY event_count DESC
                LIMIT 10
            """, (start_time, end_time))
            top_users = [dict(row) for row in cur.fetchall()]

            # Security alerts
            cur.execute("""
                SELECT event_type, reason, COUNT(*) as count
                FROM audit_events
                WHERE timestamp BETWEEN %s AND %s
                    AND (suspicious = TRUE OR result = 'denied')
                GROUP BY event_type, reason
                ORDER BY count DESC
                LIMIT 10
            """, (start_time, end_time))
            security_alerts = [
                f"{row['event_type']}: {row['reason']} ({row['count']} times)"
                for row in cur.fetchall()
            ]

            cur.close()
            conn.close()

            return AuditStatistics(
                total_events=total,
                events_by_type=events_by_type,
                events_by_user=events_by_user,
                events_by_store=events_by_store,
                failed_accesses=failed_accesses,
                denied_permissions=denied_permissions,
                suspicious_events=suspicious_events,
                pii_accesses=pii_accesses,
                time_range_start=start_time,
                time_range_end=end_time,
                top_queries=top_queries,
                top_users=top_users,
                security_alerts=security_alerts
            )

        except Exception as e:
            logger.error(f"Error getting audit statistics: {str(e)}")
            raise

    async def detect_anomalies(
        self,
        user_id: str,
        lookback_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalous behavior for a user.

        Args:
            user_id: User to analyze
            lookback_days: Number of days to analyze

        Returns:
            List of detected anomalies
        """
        anomalies = []

        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)

            start_time = datetime.utcnow() - timedelta(days=lookback_days)

            # Check for unusual query volume
            cur.execute("""
                SELECT DATE(timestamp) as date, COUNT(*) as query_count
                FROM audit_events
                WHERE user_id = %s
                    AND event_type = 'query'
                    AND timestamp >= %s
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (user_id, start_time))

            daily_counts = [row["query_count"] for row in cur.fetchall()]
            if daily_counts:
                avg_count = sum(daily_counts) / len(daily_counts)
                max_count = max(daily_counts)
                if max_count > avg_count * 3:  # 3x average
                    anomalies.append({
                        "type": "unusual_query_volume",
                        "description": f"User had {max_count} queries in a day (avg: {avg_count:.1f})",
                        "severity": "medium"
                    })

            # Check for access to unusual stores
            cur.execute("""
                SELECT store_id, COUNT(*) as access_count
                FROM audit_events
                WHERE user_id = %s
                    AND timestamp >= %s
                    AND store_id IS NOT NULL
                GROUP BY store_id
            """, (user_id, start_time))

            store_accesses = {row["store_id"]: row["access_count"] for row in cur.fetchall()}
            if len(store_accesses) > 5:  # Accessing many different stores
                anomalies.append({
                    "type": "unusual_store_access_pattern",
                    "description": f"User accessed {len(store_accesses)} different stores",
                    "severity": "low"
                })

            # Check for failed access attempts
            cur.execute("""
                SELECT COUNT(*) as failed_count
                FROM audit_events
                WHERE user_id = %s
                    AND timestamp >= %s
                    AND result IN ('denied', 'failure')
            """, (user_id, start_time))

            failed_count = cur.fetchone()["failed_count"]
            if failed_count > 10:
                anomalies.append({
                    "type": "multiple_failed_accesses",
                    "description": f"User had {failed_count} failed access attempts",
                    "severity": "high"
                })

            cur.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}")

        return anomalies

    async def generate_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
        report_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Generate a compliance report.

        Args:
            start_time: Start of reporting period
            end_time: End of reporting period
            report_type: Type of report (full, summary, security)

        Returns:
            Dict with compliance report data
        """
        stats = await self.get_statistics(start_time, end_time)

        report = {
            "report_type": report_type,
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_accesses": stats.total_events,
                "unique_users": len(stats.events_by_user),
                "unique_stores": len(stats.events_by_store),
                "pii_accesses": stats.pii_accesses,
                "denied_accesses": stats.denied_permissions,
                "security_incidents": stats.suspicious_events
            },
            "access_by_store": stats.events_by_store,
            "top_users": stats.top_users[:5],
            "security_alerts": stats.security_alerts,
            "compliance_notes": []
        }

        # Add compliance-specific notes
        if stats.suspicious_events > 0:
            report["compliance_notes"].append(
                f"⚠️ {stats.suspicious_events} suspicious events detected"
            )

        if stats.pii_accesses > 0:
            report["compliance_notes"].append(
                f"ℹ️ {stats.pii_accesses} accesses to PII-containing documents"
            )

        return report
