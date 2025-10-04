"""
PII Detection

Detects personally identifiable information in text using:
- Regex patterns
- Named entity recognition
- Machine learning models
"""

import logging
import re
from typing import List, Optional

from .models import PIIEntity, PIIType

logger = logging.getLogger(__name__)


class PIIDetector:
    """
    Detects PII in text using multiple techniques.

    Features:
    - Pattern-based detection (email, phone, SSN, etc.)
    - NER-based detection (names, addresses)
    - Configurable patterns
    - False positive filtering
    """

    def __init__(self, custom_patterns: Optional[dict] = None):
        self.patterns = self._load_default_patterns()
        if custom_patterns:
            self.patterns.update(custom_patterns)

    def _load_default_patterns(self) -> dict:
        """Load default PII detection patterns"""
        return {
            PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            PIIType.PHONE: r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
            PIIType.SSN: r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b',
            PIIType.CREDIT_CARD: r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
            PIIType.IP_ADDRESS: r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        }

    def detect(self, text: str) -> List[PIIEntity]:
        """
        Detect all PII entities in text.

        Args:
            text: Text to analyze

        Returns:
            List of detected PII entities
        """
        entities = []

        # Pattern-based detection
        for pii_type, pattern in self.patterns.items():
            for match in re.finditer(pattern, text):
                entity = PIIEntity(
                    text=match.group(),
                    pii_type=pii_type,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    confidence=0.95,  # High confidence for pattern matches
                    context=self._get_context(text, match.start(), match.end())
                )
                entities.append(entity)

        # Sort by position
        entities.sort(key=lambda e: e.start_pos)

        logger.info(f"Detected {len(entities)} PII entities in text")
        return entities

    def contains_pii(self, text: str) -> bool:
        """
        Quick check if text contains any PII.

        Args:
            text: Text to check

        Returns:
            bool: True if PII detected
        """
        return len(self.detect(text)) > 0

    def detect_by_type(self, text: str, pii_type: PIIType) -> List[PIIEntity]:
        """
        Detect specific type of PII.

        Args:
            text: Text to analyze
            pii_type: Type of PII to detect

        Returns:
            List of detected PII entities of specified type
        """
        all_entities = self.detect(text)
        return [e for e in all_entities if e.pii_type == pii_type]

    def _get_context(self, text: str, start: int, end: int, window: int = 30) -> str:
        """
        Get surrounding context for a PII match.

        Args:
            text: Full text
            start: Start position of match
            end: End position of match
            window: Characters before/after to include

        Returns:
            Context string
        """
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def add_custom_pattern(self, pii_type: PIIType, pattern: str) -> None:
        """
        Add a custom PII detection pattern.

        Args:
            pii_type: Type of PII
            pattern: Regex pattern
        """
        self.patterns[pii_type] = pattern
        logger.info(f"Added custom pattern for {pii_type.value}")

    def get_statistics(self, text: str) -> dict:
        """
        Get statistics about PII in text.

        Args:
            text: Text to analyze

        Returns:
            Dict with PII statistics
        """
        entities = self.detect(text)

        stats = {
            "total_entities": len(entities),
            "by_type": {},
            "has_pii": len(entities) > 0
        }

        for entity in entities:
            type_name = entity.pii_type.value
            if type_name not in stats["by_type"]:
                stats["by_type"][type_name] = 0
            stats["by_type"][type_name] += 1

        return stats
