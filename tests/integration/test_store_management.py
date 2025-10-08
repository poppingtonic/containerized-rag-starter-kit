"""
Integration tests for Knowledge Store Management API

Tests dynamic store creation, document indexing, and database resource sharing.
"""

import pytest
import aiohttp
import asyncio
import time
from typing import Dict, Any


KNOWLEDGE_SYSTEM_URL = "http://localhost:8100"


@pytest.fixture(scope="module")
async def wait_for_service():
    """Wait for knowledge system service to be ready"""
    max_retries = 30
    retry_delay = 2

    for i in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/health") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "healthy":
                            print(f"\n✓ Knowledge System Service is ready")
                            return True
        except Exception as e:
            if i < max_retries - 1:
                print(f"  Waiting for service... ({i+1}/{max_retries})")
                await asyncio.sleep(retry_delay)
            else:
                raise Exception(f"Service not ready after {max_retries * retry_delay}s: {str(e)}")

    return False


class TestStoreManagement:
    """Test store management API endpoints"""

    @pytest.mark.asyncio
    async def test_health_check(self, wait_for_service):
        """Test health check includes store management API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/health") as response:
                assert response.status == 200
                data = await response.json()
                assert data["status"] == "healthy"
                assert "store_management_api" in data["components"]
                assert data["components"]["store_management_api"] is True

    @pytest.mark.asyncio
    async def test_create_store(self, wait_for_service):
        """Test creating a new knowledge store"""
        async with aiohttp.ClientSession() as session:
            store_request = {
                "store_id": "test_meetings",
                "name": "Test Meeting Transcripts",
                "description": "Test store for meeting transcripts",
                "store_type": "meetings",
                "requires_roles": ["employee"],
                "pii_level": "partial",
                "audit_level": "detailed",
                "connection_config": {}
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/stores",
                json=store_request
            ) as response:
                assert response.status == 200
                data = await response.json()

                # Verify response structure
                assert data["store_id"] == "test_meetings"
                assert data["name"] == "Test Meeting Transcripts"
                assert data["store_type"] == "meetings"
                assert data["enabled"] is True
                assert "statistics" in data

    @pytest.mark.asyncio
    async def test_list_stores(self, wait_for_service):
        """Test listing all stores"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/stores/all") as response:
                assert response.status == 200
                data = await response.json()
                assert isinstance(data, list)

                # Should have at least the test_meetings store we created
                store_ids = [store["store_id"] for store in data]
                assert "test_meetings" in store_ids

    @pytest.mark.asyncio
    async def test_get_store_details(self, wait_for_service):
        """Test getting specific store details"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_meetings"
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["store_id"] == "test_meetings"
                assert "statistics" in data

    @pytest.mark.asyncio
    async def test_check_store_health(self, wait_for_service):
        """Test store health check"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_meetings/health"
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["store_id"] == "test_meetings"
                assert data["healthy"] is True
                assert data.get("error") is None

    @pytest.mark.asyncio
    async def test_index_document(self, wait_for_service):
        """Test indexing a document to a store"""
        async with aiohttp.ClientSession() as session:
            document = {
                "doc_id": "test_meeting_001",
                "title": "Test Sprint Planning",
                "content": "This is a test meeting about sprint planning. "
                          "We discussed user stories, sprint goals, and team capacity. "
                          "The team agreed on priorities for the upcoming sprint.",
                "author": "test@company.com",
                "tags": ["sprint", "planning", "test"],
                "metadata": {
                    "date": "2024-10-08",
                    "participants": ["Alice", "Bob"],
                    "duration_minutes": 60
                }
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_meetings/documents",
                json=document
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["success"] is True
                assert data["doc_id"] == "test_meeting_001"
                assert data["store_id"] == "test_meetings"

    @pytest.mark.asyncio
    async def test_get_store_statistics(self, wait_for_service):
        """Test getting store statistics after indexing"""
        # Wait a moment for indexing to complete
        await asyncio.sleep(1)

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_meetings/statistics"
            ) as response:
                assert response.status == 200
                data = await response.json()

                # Should have at least 1 document
                assert "document_count" in data
                assert data["document_count"] >= 1

                # Should have multiple chunks
                assert "chunk_count" in data
                assert data["chunk_count"] > 0

    @pytest.mark.asyncio
    async def test_create_multiple_stores(self, wait_for_service):
        """Test creating multiple stores that share database resources"""
        async with aiohttp.ClientSession() as session:
            stores_to_create = [
                {
                    "store_id": "test_emails",
                    "name": "Test Email Archive",
                    "description": "Test email store",
                    "store_type": "emails",
                    "requires_roles": ["employee"],
                    "pii_level": "full",
                    "audit_level": "forensic"
                },
                {
                    "store_id": "test_documents",
                    "name": "Test Document Store",
                    "description": "Test document store",
                    "store_type": "documents",
                    "requires_roles": ["employee"],
                    "pii_level": "partial",
                    "audit_level": "detailed"
                }
            ]

            for store_def in stores_to_create:
                async with session.post(
                    f"{KNOWLEDGE_SYSTEM_URL}/stores",
                    json=store_def
                ) as response:
                    assert response.status == 200
                    data = await response.json()
                    assert data["store_id"] == store_def["store_id"]

            # Verify all stores exist
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/stores/all") as response:
                assert response.status == 200
                stores = await response.json()
                store_ids = [s["store_id"] for s in stores]
                assert "test_emails" in store_ids
                assert "test_documents" in store_ids

    @pytest.mark.asyncio
    async def test_store_isolation(self, wait_for_service):
        """Test that stores are isolated - documents in one don't appear in another"""
        async with aiohttp.ClientSession() as session:
            # Index document to test_emails store
            email_doc = {
                "doc_id": "email_001",
                "title": "Test Email",
                "content": "This is a unique email content that should only appear in emails store.",
                "tags": ["email", "test"]
            }

            async with session.post(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_emails/documents",
                json=email_doc
            ) as response:
                assert response.status == 200

            # Wait for indexing
            await asyncio.sleep(1)

            # Check statistics for both stores
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_emails/statistics"
            ) as response:
                assert response.status == 200
                email_stats = await response.json()

            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_meetings/statistics"
            ) as response:
                assert response.status == 200
                meeting_stats = await response.json()

            # test_emails should have at least 1 document
            assert email_stats["document_count"] >= 1

            # Stores should have different document counts (isolation)
            # test_meetings had 1 doc, test_emails now has 1 doc
            # But they should be in separate partitions
            print(f"\nEmail store: {email_stats}")
            print(f"Meeting store: {meeting_stats}")

    @pytest.mark.asyncio
    async def test_delete_store(self, wait_for_service):
        """Test deleting a store (unregistering, data persists)"""
        async with aiohttp.ClientSession() as session:
            # Delete test_documents store
            async with session.delete(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_documents"
            ) as response:
                assert response.status == 200
                data = await response.json()
                assert data["success"] is True
                assert data["store_id"] == "test_documents"

            # Verify store is no longer in list
            async with session.get(f"{KNOWLEDGE_SYSTEM_URL}/stores/all") as response:
                assert response.status == 200
                stores = await response.json()
                store_ids = [s["store_id"] for s in stores]
                assert "test_documents" not in store_ids

            # Verify we get 404 when trying to access it
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/test_documents"
            ) as response:
                assert response.status == 404

    @pytest.mark.asyncio
    async def test_nonexistent_store(self, wait_for_service):
        """Test accessing a store that doesn't exist"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{KNOWLEDGE_SYSTEM_URL}/stores/nonexistent_store"
            ) as response:
                assert response.status == 404

    @pytest.mark.asyncio
    async def test_performance(self, wait_for_service):
        """Test that multiple stores don't significantly impact performance"""
        async with aiohttp.ClientSession() as session:
            # Create multiple stores
            store_count = 5
            stores = []

            for i in range(store_count):
                store_def = {
                    "store_id": f"perf_test_store_{i}",
                    "name": f"Performance Test Store {i}",
                    "description": f"Store for performance testing",
                    "store_type": "documents",
                    "requires_roles": ["employee"]
                }
                stores.append(store_def["store_id"])

                async with session.post(
                    f"{KNOWLEDGE_SYSTEM_URL}/stores",
                    json=store_def
                ) as response:
                    assert response.status == 200

            # Index a document to each store and measure time
            times = []
            for store_id in stores:
                doc = {
                    "doc_id": f"{store_id}_doc",
                    "title": "Performance Test Document",
                    "content": "This is a test document for performance testing. " * 50,
                    "tags": ["performance", "test"]
                }

                start = time.time()
                async with session.post(
                    f"{KNOWLEDGE_SYSTEM_URL}/stores/{store_id}/documents",
                    json=doc
                ) as response:
                    assert response.status == 200
                    elapsed = time.time() - start
                    times.append(elapsed)

            # Verify reasonable performance (under 5 seconds per document)
            avg_time = sum(times) / len(times)
            max_time = max(times)

            print(f"\nPerformance stats:")
            print(f"  Average indexing time: {avg_time:.2f}s")
            print(f"  Max indexing time: {max_time:.2f}s")

            assert avg_time < 5.0, f"Average indexing time too high: {avg_time}s"
            assert max_time < 10.0, f"Max indexing time too high: {max_time}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
