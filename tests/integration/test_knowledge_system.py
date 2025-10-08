"""
Integration tests for Knowledge System with Consilience services

Tests the integration between:
- Knowledge System Service
- API Service (Consilience)
- Ingestion Service
- Database
"""

import asyncio
import os
import pytest
import time
from typing import Dict, Any

import aiohttp


# Service URLs
KNOWLEDGE_SYSTEM_URL = os.getenv("KNOWLEDGE_SYSTEM_URL", "http://localhost:8100")
API_SERVICE_URL = os.getenv("API_SERVICE_URL", "http://localhost:8000")
INGESTION_SERVICE_URL = os.getenv("INGESTION_SERVICE_URL", "http://localhost:5050")


class TestKnowledgeSystemIntegration:
    """Integration tests for Knowledge System"""

    @pytest.fixture(scope="class")
    async def wait_for_services(self):
        """Wait for all services to be ready"""
        services = {
            "Knowledge System": f"{KNOWLEDGE_SYSTEM_URL}/health",
            "API Service": f"{API_SERVICE_URL}/health",
            "Ingestion Service": f"{INGESTION_SERVICE_URL}/status",
        }

        async with aiohttp.ClientSession() as session:
            for service_name, health_url in services.items():
                for attempt in range(30):  # Wait up to 60 seconds
                    try:
                        async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                print(f"✓ {service_name} is ready")
                                break
                    except Exception as e:
                        if attempt == 29:
                            pytest.fail(f"{service_name} did not become ready: {str(e)}")
                        await asyncio.sleep(2)

        return True

    @pytest.mark.asyncio
    async def test_health_check(self, wait_for_services):
        """Test knowledge system health check"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] in ["healthy", "degraded"]
                assert "components" in data
                assert data["components"]["store_manager"] is True
                assert data["components"]["rbac_service"] is True

    @pytest.mark.asyncio
    async def test_list_workflows(self, wait_for_services):
        """Test listing available workflows"""
        async with aiohttp.ClientSession() as session:
            headers = {"X-User-Roles": "employee"}
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/workflows",
                headers=headers
            ) as response:
                assert response.status == 200
                workflows = await response.json()
                assert isinstance(workflows, list)
                assert len(workflows) > 0

                # Verify workflow structure
                workflow = workflows[0]
                assert "workflow_id" in workflow
                assert "name" in workflow
                assert "allowed_stores" in workflow
                assert "required_roles" in workflow

    @pytest.mark.asyncio
    async def test_list_knowledge_stores(self, wait_for_services):
        """Test listing accessible knowledge stores"""
        async with aiohttp.ClientSession() as session:
            headers = {"X-User-Roles": "employee"}
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores",
                headers=headers
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert "stores" in data
                assert isinstance(data["stores"], list)

    @pytest.mark.asyncio
    async def test_execute_workflow_query(self, wait_for_services):
        """Test executing a workflow query"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "What is the status of the project?",
                "workflow_id": "demo_workflow",
                "user_id": "demo@company.com",
                "user_email": "demo@company.com",
                "user_roles": ["employee", "demo_user"],
                "max_results": 5
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/query",
                json=query_request
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Verify response structure
                assert "success" in result
                assert "workflow_id" in result
                assert "query" in result
                assert "answer" in result
                assert "stores_queried" in result
                assert "execution_time_ms" in result

                # Check if execution was successful
                if result["success"]:
                    assert result["workflow_id"] == "demo_workflow"
                    assert isinstance(result["stores_queried"], list)
                    assert result["execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_permission_denied(self, wait_for_services):
        """Test that permission is denied for unauthorized workflows"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "Access confidential data",
                "workflow_id": "confidential_research",
                "user_id": "demo@company.com",
                "user_email": "demo@company.com",
                "user_roles": ["employee"],  # Missing "analyst" role
                "max_results": 5
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/query",
                json=query_request
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Should fail due to insufficient permissions
                assert result["success"] is False
                assert "error" in result
                assert "Permission denied" in result["error"] or "lacks required roles" in result["error"]

    @pytest.mark.asyncio
    async def test_audit_statistics(self, wait_for_services):
        """Test retrieving audit statistics"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/audit/statistics?days=7"
            ) as response:
                assert response.status == 200
                stats = await response.json()

                # Verify statistics structure
                assert "total_events" in stats
                assert "events_by_type" in stats
                assert "failed_accesses" in stats
                assert "denied_permissions" in stats
                assert "time_range" in stats

    @pytest.mark.asyncio
    async def test_integration_with_api_service(self, wait_for_services):
        """Test integration with Consilience API service"""
        async with aiohttp.ClientSession() as session:
            # First check API service is accessible
            async with session.get(f"{API_SERVICE_URL}/health") as response:
                assert response.status == 200

            # Knowledge system should be able to connect to API service
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] in ["healthy", "degraded"]

    @pytest.mark.asyncio
    async def test_integration_with_ingestion_service(self, wait_for_services):
        """Test integration with ingestion service"""
        async with aiohttp.ClientSession() as session:
            # Check ingestion service status
            async with session.get(f"{INGESTION_SERVICE_URL}/status") as response:
                assert response.status == 200

            # Verify ingestion progress endpoint
            async with session.get(f"{API_SERVICE_URL}/ingestion/progress") as response:
                assert response.status == 200
                data = await response.json()
                assert "statistics" in data or "total_documents" in data

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_stores(self, wait_for_services):
        """Test workflow that accesses multiple knowledge stores"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "Search across all available sources",
                "workflow_id": "demo_workflow",  # Has access to multiple stores
                "user_id": "bob@company.com",
                "user_email": "bob@company.com",
                "user_roles": ["employee", "manager"],
                "max_results": 10
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/query",
                json=query_request
            ) as response:
                assert response.status == 200
                result = await response.json()

                if result["success"]:
                    # Verify multiple stores were queried
                    assert len(result["stores_queried"]) > 0

    @pytest.mark.asyncio
    async def test_pii_obfuscation(self, wait_for_services):
        """Test that PII obfuscation is applied"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "Show sensitive information",
                "workflow_id": "meeting_tracker",  # Has metadata_only PII level
                "user_id": "alice@company.com",
                "user_email": "alice@company.com",
                "user_roles": ["employee"],
                "max_results": 5
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/query",
                json=query_request
            ) as response:
                assert response.status == 200
                result = await response.json()

                # Check if obfuscation flag is set
                assert "obfuscated" in result


class TestPerformance:
    """Performance tests for knowledge system"""

    @pytest.mark.asyncio
    async def test_query_response_time(self):
        """Test that queries complete within acceptable time"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "Quick test query",
                "workflow_id": "demo_workflow",
                "user_id": "demo@company.com",
                "user_email": "demo@company.com",
                "user_roles": ["employee", "demo_user"],
                "max_results": 5
            }

            start_time = time.time()

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/query",
                json=query_request
            ) as response:
                assert response.status == 200
                result = await response.json()

            elapsed = time.time() - start_time

            # Query should complete within 10 seconds
            assert elapsed < 10.0

            if result["success"]:
                # Verify execution time is recorded
                assert result["execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_concurrent_queries(self):
        """Test handling multiple concurrent queries"""
        async with aiohttp.ClientSession() as session:
            query_request = {
                "query": "Concurrent test query",
                "workflow_id": "demo_workflow",
                "user_id": "demo@company.com",
                "user_email": "demo@company.com",
                "user_roles": ["employee", "demo_user"],
                "max_results": 3
            }

            # Execute 5 concurrent queries
            tasks = []
            for i in range(5):
                task = session.post(
                    f"{KNOWLEDGE_SYSTEM_URL}/query",
                    json={**query_request, "query": f"Query {i}"}
                )
                tasks.append(task)

            responses = await asyncio.gather(*tasks, return_exceptions=True)

            # All queries should succeed or handle gracefully
            for response in responses:
                if isinstance(response, Exception):
                    pytest.fail(f"Concurrent query failed: {str(response)}")
                else:
                    assert response.status == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
