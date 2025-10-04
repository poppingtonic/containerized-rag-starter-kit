"""
Knowledge Store Manager

Manages multiple knowledge stores and routes queries to appropriate stores.
"""

import logging
from typing import Any, Dict, List, Optional

from .base import KnowledgeStore, QueryResult, StoreMetadata, StoreType

logger = logging.getLogger(__name__)


class KnowledgeStoreManager:
    """
    Manages multiple knowledge stores and provides unified query interface.

    Features:
    - Multi-store query routing
    - Load balancing across stores
    - Store health monitoring
    - Automatic failover
    """

    def __init__(self):
        self.stores: Dict[str, KnowledgeStore] = {}
        self._store_health: Dict[str, bool] = {}

    def register_store(self, store: KnowledgeStore) -> None:
        """
        Register a knowledge store with the manager.

        Args:
            store: Knowledge store instance to register
        """
        store_id = store.metadata.store_id
        if store_id in self.stores:
            logger.warning(f"Store {store_id} already registered, overwriting")

        self.stores[store_id] = store
        self._store_health[store_id] = store.is_initialized()
        logger.info(f"Registered knowledge store: {store_id} ({store.metadata.store_type.value})")

    def unregister_store(self, store_id: str) -> bool:
        """
        Unregister a knowledge store.

        Args:
            store_id: ID of store to unregister

        Returns:
            bool: True if store was unregistered
        """
        if store_id in self.stores:
            del self.stores[store_id]
            del self._store_health[store_id]
            logger.info(f"Unregistered knowledge store: {store_id}")
            return True
        return False

    def get_store(self, store_id: str) -> Optional[KnowledgeStore]:
        """
        Get a knowledge store by ID.

        Args:
            store_id: Store identifier

        Returns:
            KnowledgeStore instance or None
        """
        return self.stores.get(store_id)

    def get_stores_by_type(self, store_type: StoreType) -> List[KnowledgeStore]:
        """
        Get all stores of a specific type.

        Args:
            store_type: Type of stores to retrieve

        Returns:
            List of knowledge stores
        """
        return [
            store for store in self.stores.values()
            if store.metadata.store_type == store_type
        ]

    def list_stores(self) -> List[StoreMetadata]:
        """
        List all registered stores.

        Returns:
            List of store metadata
        """
        return [store.metadata for store in self.stores.values()]

    async def initialize_all(self) -> Dict[str, bool]:
        """
        Initialize all registered stores.

        Returns:
            Dict mapping store_id to initialization success
        """
        results = {}
        for store_id, store in self.stores.items():
            try:
                success = await store.initialize()
                results[store_id] = success
                self._store_health[store_id] = success
                if success:
                    logger.info(f"Initialized store: {store_id}")
                else:
                    logger.error(f"Failed to initialize store: {store_id}")
            except Exception as e:
                logger.error(f"Error initializing store {store_id}: {str(e)}")
                results[store_id] = False
                self._store_health[store_id] = False
        return results

    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Run health checks on all stores.

        Returns:
            Dict mapping store_id to health check results
        """
        results = {}
        for store_id, store in self.stores.items():
            try:
                health = await store.health_check()
                results[store_id] = health
                self._store_health[store_id] = health.get("healthy", False)
            except Exception as e:
                logger.error(f"Health check failed for store {store_id}: {str(e)}")
                results[store_id] = {"healthy": False, "error": str(e)}
                self._store_health[store_id] = False
        return results

    async def query_stores(
        self,
        query_text: str,
        user_id: str,
        user_roles: List[str],
        store_ids: Optional[List[str]] = None,
        max_results_per_store: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[QueryResult]]:
        """
        Query multiple knowledge stores.

        Args:
            query_text: Natural language query
            user_id: User making the query
            user_roles: Roles assigned to the user
            store_ids: Specific stores to query (None = all accessible stores)
            max_results_per_store: Max results per store
            filters: Additional query filters

        Returns:
            Dict mapping store_id to list of query results
        """
        # Determine which stores to query
        if store_ids:
            target_stores = [
                (sid, self.stores[sid])
                for sid in store_ids
                if sid in self.stores and self._store_health.get(sid, False)
            ]
        else:
            # Query all healthy stores user has access to
            target_stores = [
                (sid, store)
                for sid, store in self.stores.items()
                if self._store_health.get(sid, False)
                and self._user_has_store_access(user_roles, store)
            ]

        # Query each store
        results = {}
        for store_id, store in target_stores:
            try:
                store_results = await store.query(
                    query_text=query_text,
                    user_id=user_id,
                    user_roles=user_roles,
                    max_results=max_results_per_store,
                    filters=filters
                )
                results[store_id] = store_results
                logger.info(f"Store {store_id} returned {len(store_results)} results")
            except Exception as e:
                logger.error(f"Error querying store {store_id}: {str(e)}")
                results[store_id] = []

        return results

    async def query_all_stores(
        self,
        query_text: str,
        user_id: str,
        user_roles: List[str],
        max_total_results: int = 50,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[QueryResult]:
        """
        Query all accessible stores and merge results by relevance.

        Args:
            query_text: Natural language query
            user_id: User making the query
            user_roles: Roles assigned to the user
            max_total_results: Maximum total results across all stores
            filters: Additional query filters

        Returns:
            Merged and sorted list of query results
        """
        store_results = await self.query_stores(
            query_text=query_text,
            user_id=user_id,
            user_roles=user_roles,
            store_ids=None,
            max_results_per_store=max_total_results,
            filters=filters
        )

        # Merge results from all stores
        all_results = []
        for store_id, results in store_results.items():
            all_results.extend(results)

        # Sort by similarity score
        all_results.sort(key=lambda r: r.similarity_score, reverse=True)

        # Return top N results
        return all_results[:max_total_results]

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all stores.

        Returns:
            Dict with aggregated statistics
        """
        stats = {
            "total_stores": len(self.stores),
            "healthy_stores": sum(1 for h in self._store_health.values() if h),
            "stores": {}
        }

        for store_id, store in self.stores.items():
            try:
                store_stats = await store.get_statistics()
                stats["stores"][store_id] = {
                    "type": store.metadata.store_type.value,
                    "healthy": self._store_health.get(store_id, False),
                    "statistics": store_stats
                }
            except Exception as e:
                logger.error(f"Error getting statistics for store {store_id}: {str(e)}")
                stats["stores"][store_id] = {
                    "type": store.metadata.store_type.value,
                    "healthy": False,
                    "error": str(e)
                }

        return stats

    def _user_has_store_access(
        self,
        user_roles: List[str],
        store: KnowledgeStore
    ) -> bool:
        """
        Check if user has access to a store based on roles.

        Args:
            user_roles: User's roles
            store: Knowledge store to check

        Returns:
            bool: True if user has access
        """
        required_roles = store.get_required_roles()
        if not required_roles:
            return True  # No role requirements
        return any(role in user_roles for role in required_roles)

    def get_accessible_stores(
        self,
        user_roles: List[str]
    ) -> List[StoreMetadata]:
        """
        Get list of stores accessible to a user based on roles.

        Args:
            user_roles: User's roles

        Returns:
            List of accessible store metadata
        """
        return [
            store.metadata
            for store in self.stores.values()
            if self._user_has_store_access(user_roles, store)
            and self._store_health.get(store.metadata.store_id, False)
        ]
