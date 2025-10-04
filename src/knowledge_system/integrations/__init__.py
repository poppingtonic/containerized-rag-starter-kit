"""
Integration Layer for Microsoft Services

Provides compatibility with:
- Power Automate
- Copilot Studio
- Microsoft Teams
- Azure Bot Framework
"""

from .power_automate import PowerAutomateAdapter
from .copilot_studio import CopilotStudioAdapter
from .bot_framework import BotFrameworkAdapter

__all__ = [
    "PowerAutomateAdapter",
    "CopilotStudioAdapter",
    "BotFrameworkAdapter",
]
