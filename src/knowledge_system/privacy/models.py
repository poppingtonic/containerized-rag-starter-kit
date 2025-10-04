"""
Privacy and PII models
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class PIIType(Enum):
    """Types of personally identifiable information"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    MEDICAL_RECORD = "medical_record"
    FINANCIAL_ACCOUNT = "financial_account"
    CUSTOM = "custom"


class SensitivityLevel(Enum):
    """Data sensitivity levels"""
    PUBLIC = "public"  # No restrictions
    INTERNAL = "internal"  # Organization only
    CONFIDENTIAL = "confidential"  # Limited access
    RESTRICTED = "restricted"  # Highly restricted
    SECRET = "secret"  # Maximum protection


@dataclass
class PIIEntity:
    """Represents a detected PII entity"""
    text: str
    pii_type: PIIType
    start_pos: int
    end_pos: int
    confidence: float
    context: Optional[str] = None
