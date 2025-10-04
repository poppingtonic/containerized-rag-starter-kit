"""
Identity Provider integrations

Supports:
- Azure AD / Entra ID
- Okta
- Auth0
- Custom LDAP/AD
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import aiohttp

from .models import User

logger = logging.getLogger(__name__)


class IdentityProvider(ABC):
    """Abstract base class for identity providers"""

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, str]) -> Optional[User]:
        """
        Authenticate a user and return user object.

        Args:
            credentials: Dict with auth credentials (token, username/password, etc.)

        Returns:
            User object if authentication succeeds, None otherwise
        """
        pass

    @abstractmethod
    async def get_user(self, user_id: str) -> Optional[User]:
        """
        Get user details by ID.

        Args:
            user_id: User identifier

        Returns:
            User object or None
        """
        pass

    @abstractmethod
    async def get_user_groups(self, user_id: str) -> List[str]:
        """
        Get groups/roles for a user.

        Args:
            user_id: User identifier

        Returns:
            List of group/role IDs
        """
        pass

    @abstractmethod
    async def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate an access token.

        Args:
            token: Access token to validate

        Returns:
            Token claims if valid, None otherwise
        """
        pass


class AzureADProvider(IdentityProvider):
    """
    Azure AD / Entra ID identity provider.

    Uses Microsoft Graph API for user and group information.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.graph_api_base = "https://graph.microsoft.com/v1.0"

    async def authenticate(self, credentials: Dict[str, str]) -> Optional[User]:
        """
        Authenticate using Azure AD token.

        Expected credentials:
        {
            "access_token": "Bearer token..."
        }
        """
        token = credentials.get("access_token")
        if not token:
            return None

        # Validate token and get user info
        token_info = await self.validate_token(token)
        if not token_info:
            return None

        user_id = token_info.get("oid") or token_info.get("sub")
        if not user_id:
            return None

        return await self.get_user(user_id)

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user from Microsoft Graph API"""
        try:
            # Get access token for Graph API
            access_token = await self._get_app_access_token()
            if not access_token:
                return None

            # Call Graph API to get user
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {access_token}"}
                async with session.get(
                    f"{self.graph_api_base}/users/{user_id}",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get user from Graph API: {response.status}")
                        return None

                    data = await response.json()

                    # Get user's groups
                    groups = await self.get_user_groups(user_id)

                    return User(
                        user_id=data["id"],
                        email=data.get("mail") or data.get("userPrincipalName"),
                        name=data.get("displayName", ""),
                        roles=groups,
                        department=data.get("department"),
                        metadata={
                            "job_title": data.get("jobTitle"),
                            "office_location": data.get("officeLocation"),
                            "azure_ad": True
                        },
                        active=data.get("accountEnabled", True)
                    )

        except Exception as e:
            logger.error(f"Error getting user from Azure AD: {str(e)}")
            return None

    async def get_user_groups(self, user_id: str) -> List[str]:
        """Get user's groups from Azure AD"""
        try:
            access_token = await self._get_app_access_token()
            if not access_token:
                return []

            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {access_token}"}
                async with session.get(
                    f"{self.graph_api_base}/users/{user_id}/memberOf",
                    headers=headers
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get groups from Graph API: {response.status}")
                        return []

                    data = await response.json()
                    # Return group IDs
                    return [group["id"] for group in data.get("value", [])]

        except Exception as e:
            logger.error(f"Error getting groups from Azure AD: {str(e)}")
            return []

    async def validate_token(self, token: str) -> Optional[Dict]:
        """
        Validate Azure AD access token.

        In production, this should validate the JWT signature
        and check claims. Simplified here.
        """
        try:
            # Remove "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]

            # Call Graph API with the token to validate it
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {token}"}
                async with session.get(
                    f"{self.graph_api_base}/me",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "oid": data.get("id"),
                            "upn": data.get("userPrincipalName"),
                            "name": data.get("displayName")
                        }
                    return None

        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return None

    async def _get_app_access_token(self) -> Optional[str]:
        """
        Get an app-only access token for Microsoft Graph.

        Uses client credentials flow.
        """
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials"
                }

                async with session.post(
                    f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                    data=data
                ) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        return token_data.get("access_token")
                    else:
                        logger.error(f"Failed to get app token: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error getting app access token: {str(e)}")
            return None


class OktaProvider(IdentityProvider):
    """
    Okta identity provider.

    Placeholder implementation - would use Okta API.
    """

    def __init__(self, domain: str, api_token: str):
        self.domain = domain
        self.api_token = api_token
        self.base_url = f"https://{domain}/api/v1"

    async def authenticate(self, credentials: Dict[str, str]) -> Optional[User]:
        # Implementation would call Okta API
        raise NotImplementedError("Okta provider not yet implemented")

    async def get_user(self, user_id: str) -> Optional[User]:
        raise NotImplementedError("Okta provider not yet implemented")

    async def get_user_groups(self, user_id: str) -> List[str]:
        raise NotImplementedError("Okta provider not yet implemented")

    async def validate_token(self, token: str) -> Optional[Dict]:
        raise NotImplementedError("Okta provider not yet implemented")
