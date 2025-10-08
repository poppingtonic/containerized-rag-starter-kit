"""
Document Router

Routes documents to appropriate knowledge stores based on:
- File type/extension
- Document metadata
- Content analysis
- Custom routing rules
"""

import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import yaml


class RoutingStrategy(Enum):
    """Strategy for routing documents to stores"""
    FILE_EXTENSION = "file_extension"
    METADATA_FIELD = "metadata_field"
    CONTENT_PATTERN = "content_pattern"
    CUSTOM_FUNCTION = "custom_function"
    DEFAULT = "default"


@dataclass
class RoutingRule:
    """Rule for routing documents to stores"""
    rule_id: str
    name: str
    description: str
    strategy: RoutingStrategy
    target_store_id: str
    priority: int = 100  # Lower number = higher priority

    # Strategy-specific configuration
    file_extensions: Optional[List[str]] = None  # For FILE_EXTENSION
    metadata_field: Optional[str] = None  # For METADATA_FIELD
    metadata_values: Optional[List[str]] = None  # For METADATA_FIELD
    content_patterns: Optional[List[str]] = None  # For CONTENT_PATTERN (regex)
    custom_function: Optional[str] = None  # For CUSTOM_FUNCTION (function name)

    # Additional options
    enabled: bool = True


@dataclass
class RoutingResult:
    """Result of document routing"""
    store_id: str
    rule_id: str
    rule_name: str
    confidence: float = 1.0  # 0.0 to 1.0
    metadata: Optional[Dict[str, Any]] = None


class DocumentRouter:
    """
    Routes documents to appropriate knowledge stores based on rules.

    Example usage:
        router = DocumentRouter(config_path="routing_rules.yaml")
        result = router.route_document(
            filename="meeting_notes.pdf",
            content="Meeting about Q4 planning...",
            metadata={"type": "meeting", "date": "2024-10-08"}
        )
        print(f"Route to store: {result.store_id}")
    """

    def __init__(self, config_path: Optional[str] = None, default_store_id: str = "default"):
        """
        Initialize document router.

        Args:
            config_path: Path to YAML configuration file with routing rules
            default_store_id: Default store to route to if no rules match
        """
        self.default_store_id = default_store_id
        self.rules: List[RoutingRule] = []
        self.custom_functions: Dict[str, callable] = {}

        if config_path and os.path.exists(config_path):
            self.load_rules_from_file(config_path)

    def add_rule(self, rule: RoutingRule):
        """Add a routing rule"""
        self.rules.append(rule)
        # Keep rules sorted by priority
        self.rules.sort(key=lambda r: r.priority)

    def register_custom_function(self, name: str, func: callable):
        """
        Register a custom routing function.

        The function should have signature:
        func(filename: str, content: str, metadata: Dict) -> bool

        Return True if the document should be routed to the rule's target store.
        """
        self.custom_functions[name] = func

    def load_rules_from_file(self, config_path: str):
        """Load routing rules from YAML file"""
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        if not config or 'routing_rules' not in config:
            return

        for rule_config in config['routing_rules']:
            rule = RoutingRule(
                rule_id=rule_config['rule_id'],
                name=rule_config['name'],
                description=rule_config.get('description', ''),
                strategy=RoutingStrategy(rule_config['strategy']),
                target_store_id=rule_config['target_store_id'],
                priority=rule_config.get('priority', 100),
                file_extensions=rule_config.get('file_extensions'),
                metadata_field=rule_config.get('metadata_field'),
                metadata_values=rule_config.get('metadata_values'),
                content_patterns=rule_config.get('content_patterns'),
                custom_function=rule_config.get('custom_function'),
                enabled=rule_config.get('enabled', True)
            )
            self.add_rule(rule)

    def route_document(
        self,
        filename: str,
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RoutingResult:
        """
        Route a document to the appropriate knowledge store.

        Args:
            filename: Document filename
            content: Document text content (optional)
            metadata: Document metadata (optional)

        Returns:
            RoutingResult with target store_id and routing information
        """
        metadata = metadata or {}

        # Try each rule in priority order
        for rule in self.rules:
            if not rule.enabled:
                continue

            if self._matches_rule(rule, filename, content, metadata):
                return RoutingResult(
                    store_id=rule.target_store_id,
                    rule_id=rule.rule_id,
                    rule_name=rule.name,
                    confidence=1.0,
                    metadata={"matched_rule": rule.name}
                )

        # No rules matched, use default
        return RoutingResult(
            store_id=self.default_store_id,
            rule_id="default",
            rule_name="Default Routing",
            confidence=0.5,
            metadata={"reason": "no_rules_matched"}
        )

    def _matches_rule(
        self,
        rule: RoutingRule,
        filename: str,
        content: Optional[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """Check if a document matches a routing rule"""

        if rule.strategy == RoutingStrategy.FILE_EXTENSION:
            return self._matches_file_extension(rule, filename)

        elif rule.strategy == RoutingStrategy.METADATA_FIELD:
            return self._matches_metadata(rule, metadata)

        elif rule.strategy == RoutingStrategy.CONTENT_PATTERN:
            return self._matches_content_pattern(rule, content)

        elif rule.strategy == RoutingStrategy.CUSTOM_FUNCTION:
            return self._matches_custom_function(rule, filename, content, metadata)

        return False

    def _matches_file_extension(self, rule: RoutingRule, filename: str) -> bool:
        """Check if filename matches rule's file extensions"""
        if not rule.file_extensions:
            return False

        _, ext = os.path.splitext(filename.lower())
        ext = ext.lstrip('.')

        return ext in [e.lower().lstrip('.') for e in rule.file_extensions]

    def _matches_metadata(self, rule: RoutingRule, metadata: Dict[str, Any]) -> bool:
        """Check if metadata matches rule"""
        if not rule.metadata_field or not rule.metadata_values:
            return False

        field_value = metadata.get(rule.metadata_field)
        if field_value is None:
            return False

        # Convert to string for comparison
        field_value_str = str(field_value).lower()

        return any(
            str(val).lower() in field_value_str or field_value_str in str(val).lower()
            for val in rule.metadata_values
        )

    def _matches_content_pattern(self, rule: RoutingRule, content: Optional[str]) -> bool:
        """Check if content matches rule's regex patterns"""
        if not rule.content_patterns or not content:
            return False

        for pattern in rule.content_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True

        return False

    def _matches_custom_function(
        self,
        rule: RoutingRule,
        filename: str,
        content: Optional[str],
        metadata: Dict[str, Any]
    ) -> bool:
        """Check if custom function matches"""
        if not rule.custom_function:
            return False

        func = self.custom_functions.get(rule.custom_function)
        if not func:
            return False

        try:
            return func(filename, content, metadata)
        except Exception:
            return False

    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get statistics about routing rules"""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules if r.enabled]),
            "rules_by_strategy": {
                strategy.value: len([r for r in self.rules if r.strategy == strategy])
                for strategy in RoutingStrategy
            },
            "rules_by_store": self._count_rules_by_store()
        }

    def _count_rules_by_store(self) -> Dict[str, int]:
        """Count rules targeting each store"""
        counts = {}
        for rule in self.rules:
            if rule.enabled:
                counts[rule.target_store_id] = counts.get(rule.target_store_id, 0) + 1
        return counts


# Pre-defined custom routing functions

def is_meeting_document(filename: str, content: Optional[str], metadata: Dict[str, Any]) -> bool:
    """Check if document is a meeting transcript or notes"""
    # Check filename
    meeting_keywords = ['meeting', 'minutes', 'standup', 'sync', 'call', 'transcript']
    if any(keyword in filename.lower() for keyword in meeting_keywords):
        return True

    # Check metadata
    doc_type = metadata.get('type', '').lower()
    if 'meeting' in doc_type or 'transcript' in doc_type:
        return True

    # Check content patterns
    if content:
        meeting_patterns = [
            r'agenda:',
            r'attendees:',
            r'action items:',
            r'meeting notes',
            r'discussed:',
            r'\[.*\d{1,2}:\d{2}\s*(AM|PM)?.*\]'  # Timestamps
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in meeting_patterns)

    return False


def is_email_document(filename: str, content: Optional[str], metadata: Dict[str, Any]) -> bool:
    """Check if document is an email"""
    # Check extension
    if filename.lower().endswith(('.eml', '.msg')):
        return True

    # Check metadata
    if metadata.get('type') == 'email':
        return True

    # Check content headers
    if content:
        email_headers = ['From:', 'To:', 'Subject:', 'Date:', 'Cc:', 'Bcc:']
        header_count = sum(1 for header in email_headers if header in content[:500])
        return header_count >= 3

    return False


def is_presentation_document(filename: str, content: Optional[str], metadata: Dict[str, Any]) -> bool:
    """Check if document is a presentation"""
    presentation_exts = ['.ppt', '.pptx', '.key', '.odp']
    return any(filename.lower().endswith(ext) for ext in presentation_exts)


def is_spreadsheet_document(filename: str, content: Optional[str], metadata: Dict[str, Any]) -> bool:
    """Check if document is a spreadsheet"""
    spreadsheet_exts = ['.xls', '.xlsx', '.csv', '.ods', '.numbers']
    return any(filename.lower().endswith(ext) for ext in spreadsheet_exts)


def is_code_document(filename: str, content: Optional[str], metadata: Dict[str, Any]) -> bool:
    """Check if document is source code"""
    code_exts = [
        '.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.cs', '.rb', '.go',
        '.rs', '.php', '.swift', '.kt', '.scala', '.r', '.m', '.sh', '.sql'
    ]
    return any(filename.lower().endswith(ext) for ext in code_exts)
