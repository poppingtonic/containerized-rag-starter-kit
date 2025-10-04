"""
Data Obfuscation

Handles PII obfuscation and metadata-only access modes.
"""

import hashlib
import logging
from typing import Dict, List, Optional

from .detector import PIIDetector
from .models import PIIEntity, PIIType, SensitivityLevel

logger = logging.getLogger(__name__)


class DataObfuscator:
    """
    Obfuscates PII in text based on sensitivity levels.

    Features:
    - Multiple obfuscation strategies (redact, hash, replace)
    - Metadata-only mode
    - Preserves text structure
    - Configurable by PII type
    """

    def __init__(self, detector: Optional[PIIDetector] = None):
        self.detector = detector or PIIDetector()
        self.obfuscation_strategies = self._load_default_strategies()

    def _load_default_strategies(self) -> Dict[PIIType, str]:
        """Load default obfuscation strategies for each PII type"""
        return {
            PIIType.EMAIL: "hash",
            PIIType.PHONE: "mask",
            PIIType.SSN: "redact",
            PIIType.CREDIT_CARD: "redact",
            PIIType.NAME: "replace",
            PIIType.ADDRESS: "replace",
            PIIType.IP_ADDRESS: "hash",
        }

    def obfuscate(
        self,
        text: str,
        sensitivity_level: SensitivityLevel,
        preserve_structure: bool = True
    ) -> str:
        """
        Obfuscate PII in text based on sensitivity level.

        Args:
            text: Text to obfuscate
            sensitivity_level: Level of obfuscation to apply
            preserve_structure: Whether to preserve text structure

        Returns:
            Obfuscated text
        """
        # No obfuscation for public data
        if sensitivity_level == SensitivityLevel.PUBLIC:
            return text

        # Detect PII entities
        entities = self.detector.detect(text)
        if not entities:
            return text

        # Apply obfuscation strategy based on sensitivity
        if sensitivity_level == SensitivityLevel.INTERNAL:
            # Light obfuscation - mask partial info
            return self._partial_obfuscate(text, entities, preserve_structure)
        elif sensitivity_level == SensitivityLevel.CONFIDENTIAL:
            # Medium obfuscation - replace with tokens
            return self._token_obfuscate(text, entities, preserve_structure)
        elif sensitivity_level in [SensitivityLevel.RESTRICTED, SensitivityLevel.SECRET]:
            # Full obfuscation - redact completely
            return self._full_redact(text, entities, preserve_structure)

        return text

    def _partial_obfuscate(
        self,
        text: str,
        entities: List[PIIEntity],
        preserve_structure: bool
    ) -> str:
        """
        Partially obfuscate PII (e.g., show first/last chars).

        Example: john.doe@company.com -> j***.d**@company.com
        """
        result = text
        offset = 0

        for entity in entities:
            original = entity.text
            obfuscated = self._mask_partial(original, entity.pii_type)

            # Replace in result
            start = entity.start_pos + offset
            end = entity.end_pos + offset
            result = result[:start] + obfuscated + result[end:]

            # Update offset for next replacement
            offset += len(obfuscated) - len(original)

        return result

    def _token_obfuscate(
        self,
        text: str,
        entities: List[PIIEntity],
        preserve_structure: bool
    ) -> str:
        """
        Replace PII with typed tokens.

        Example: john.doe@company.com -> [EMAIL]
                 (555) 123-4567 -> [PHONE]
        """
        result = text
        offset = 0

        for entity in entities:
            token = f"[{entity.pii_type.value.upper()}]"

            start = entity.start_pos + offset
            end = entity.end_pos + offset
            result = result[:start] + token + result[end:]

            offset += len(token) - len(entity.text)

        return result

    def _full_redact(
        self,
        text: str,
        entities: List[PIIEntity],
        preserve_structure: bool
    ) -> str:
        """
        Fully redact PII with [REDACTED].

        Example: john.doe@company.com -> [REDACTED]
        """
        result = text
        offset = 0

        for entity in entities:
            redacted = "[REDACTED]"

            start = entity.start_pos + offset
            end = entity.end_pos + offset
            result = result[:start] + redacted + result[end:]

            offset += len(redacted) - len(entity.text)

        return result

    def _mask_partial(self, text: str, pii_type: PIIType) -> str:
        """Mask part of the text based on PII type"""
        if pii_type == PIIType.EMAIL:
            # Mask username part
            if '@' in text:
                username, domain = text.split('@', 1)
                if len(username) > 2:
                    masked = username[0] + '*' * (len(username) - 2) + username[-1]
                    return f"{masked}@{domain}"
            return text

        elif pii_type == PIIType.PHONE:
            # Show last 4 digits only
            digits = ''.join(c for c in text if c.isdigit())
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return "***-***-****"

        elif pii_type == PIIType.CREDIT_CARD:
            # Show last 4 digits
            digits = ''.join(c for c in text if c.isdigit())
            if len(digits) >= 4:
                return f"****-****-****-{digits[-4:]}"
            return "****-****-****-****"

        else:
            # Generic masking
            if len(text) > 4:
                return text[:2] + '*' * (len(text) - 4) + text[-2:]
            return '*' * len(text)

    def hash_pii(self, text: str) -> str:
        """
        Hash PII for consistent identification without revealing content.

        Args:
            text: Text containing PII

        Returns:
            Hashed representation
        """
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def extract_metadata(self, text: str) -> Dict:
        """
        Extract metadata about PII without revealing content.

        Args:
            text: Text to analyze

        Returns:
            Dict with PII metadata (types, counts, hashes)
        """
        entities = self.detector.detect(text)

        metadata = {
            "has_pii": len(entities) > 0,
            "pii_count": len(entities),
            "pii_types": list(set(e.pii_type.value for e in entities)),
            "entity_hashes": [self.hash_pii(e.text) for e in entities]
        }

        return metadata

    def metadata_only_response(self, text: str, doc_metadata: Dict) -> Dict:
        """
        Generate a metadata-only response (no actual content).

        Args:
            text: Original text (for PII detection)
            doc_metadata: Document metadata

        Returns:
            Dict with metadata only, no content
        """
        pii_metadata = self.extract_metadata(text)

        return {
            "access_mode": "metadata_only",
            "document_id": doc_metadata.get("doc_id"),
            "title": doc_metadata.get("title"),
            "author": doc_metadata.get("author"),
            "created_at": doc_metadata.get("created_at"),
            "size": len(text),
            "word_count": len(text.split()),
            "pii_detected": pii_metadata["has_pii"],
            "pii_types": pii_metadata["pii_types"],
            "sensitivity_level": doc_metadata.get("sensitivity_level"),
            "message": "Content hidden due to sensitivity level. Only metadata is accessible."
        }

    def set_strategy(self, pii_type: PIIType, strategy: str) -> None:
        """
        Set obfuscation strategy for a PII type.

        Args:
            pii_type: Type of PII
            strategy: Strategy name (redact, hash, mask, replace)
        """
        self.obfuscation_strategies[pii_type] = strategy
        logger.info(f"Set obfuscation strategy for {pii_type.value}: {strategy}")
