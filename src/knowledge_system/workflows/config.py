"""
Workflow Configuration

Load and validate workflow definitions from YAML/JSON files.
"""

import logging
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Workflow

logger = logging.getLogger(__name__)


class WorkflowConfig:
    """
    Manages workflow configuration loading and validation.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.workflows: Dict[str, Workflow] = {}

    def load_from_file(self, file_path: str) -> List[Workflow]:
        """
        Load workflows from YAML or JSON file.

        Args:
            file_path: Path to config file

        Returns:
            List of loaded workflows
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow config file not found: {file_path}")

        try:
            with open(path, 'r') as f:
                if path.suffix in ['.yaml', '.yml']:
                    config = yaml.safe_load(f)
                elif path.suffix == '.json':
                    import json
                    config = json.load(f)
                else:
                    raise ValueError(f"Unsupported config file format: {path.suffix}")

            workflows = self._parse_config(config)
            logger.info(f"Loaded {len(workflows)} workflows from {file_path}")
            return workflows

        except Exception as e:
            logger.error(f"Error loading workflow config: {str(e)}")
            raise

    def _parse_config(self, config: Dict) -> List[Workflow]:
        """Parse workflow config dictionary"""
        workflows = []

        for workflow_id, workflow_def in config.get('workflows', {}).items():
            try:
                workflow = Workflow(
                    workflow_id=workflow_id,
                    name=workflow_def.get('name', workflow_id),
                    description=workflow_def.get('description', ''),
                    allowed_stores=workflow_def.get('allowed_stores', []),
                    required_roles=workflow_def.get('required_roles', []),
                    denied_roles=workflow_def.get('denied_roles', []),
                    pii_level=workflow_def.get('pii_level', 'partial'),
                    obfuscation_enabled=workflow_def.get('obfuscation_enabled', True),
                    audit_level=workflow_def.get('audit_level', 'detailed'),
                    log_queries=workflow_def.get('log_queries', True),
                    log_results=workflow_def.get('log_results', False),
                    max_results=workflow_def.get('max_results', 50),
                    default_filters=workflow_def.get('default_filters', {}),
                    enable_amplification=workflow_def.get('enable_amplification', False),
                    enable_smart_selection=workflow_def.get('enable_smart_selection', True),
                    integration_type=workflow_def.get('integration_type'),
                    integration_config=workflow_def.get('integration_config', {}),
                    created_at=datetime.utcnow(),
                    active=workflow_def.get('active', True),
                    metadata=workflow_def.get('metadata', {})
                )

                self._validate_workflow(workflow)
                workflows.append(workflow)
                self.workflows[workflow_id] = workflow

            except Exception as e:
                logger.error(f"Error parsing workflow {workflow_id}: {str(e)}")
                continue

        return workflows

    def _validate_workflow(self, workflow: Workflow) -> None:
        """
        Validate workflow configuration.

        Args:
            workflow: Workflow to validate

        Raises:
            ValueError: If validation fails
        """
        if not workflow.workflow_id:
            raise ValueError("Workflow ID is required")

        if not workflow.name:
            raise ValueError("Workflow name is required")

        if not workflow.allowed_stores:
            logger.warning(f"Workflow {workflow.workflow_id} has no allowed stores")

        valid_pii_levels = ['full', 'partial', 'metadata_only']
        if workflow.pii_level not in valid_pii_levels:
            raise ValueError(f"Invalid PII level: {workflow.pii_level}")

        valid_audit_levels = ['basic', 'detailed', 'forensic']
        if workflow.audit_level not in valid_audit_levels:
            raise ValueError(f"Invalid audit level: {workflow.audit_level}")

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a loaded workflow by ID"""
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[Workflow]:
        """List all loaded workflows"""
        return list(self.workflows.values())

    def export_to_dict(self) -> Dict[str, Any]:
        """Export workflows to dictionary format"""
        return {
            'workflows': {
                wf.workflow_id: {
                    'name': wf.name,
                    'description': wf.description,
                    'allowed_stores': wf.allowed_stores,
                    'required_roles': wf.required_roles,
                    'denied_roles': wf.denied_roles,
                    'pii_level': wf.pii_level,
                    'obfuscation_enabled': wf.obfuscation_enabled,
                    'audit_level': wf.audit_level,
                    'log_queries': wf.log_queries,
                    'log_results': wf.log_results,
                    'max_results': wf.max_results,
                    'default_filters': wf.default_filters,
                    'enable_amplification': wf.enable_amplification,
                    'enable_smart_selection': wf.enable_smart_selection,
                    'integration_type': wf.integration_type,
                    'integration_config': wf.integration_config,
                    'active': wf.active,
                    'metadata': wf.metadata
                }
                for wf in self.workflows.values()
            }
        }

    def save_to_file(self, file_path: str) -> None:
        """
        Save current workflows to file.

        Args:
            file_path: Path to save config
        """
        config = self.export_to_dict()

        path = Path(file_path)
        with open(path, 'w') as f:
            if path.suffix in ['.yaml', '.yml']:
                yaml.dump(config, f, default_flow_style=False)
            elif path.suffix == '.json':
                import json
                json.dump(config, f, indent=2)

        logger.info(f"Saved {len(self.workflows)} workflows to {file_path}")


# Example workflow configuration
EXAMPLE_CONFIG = """
workflows:
  meeting_tracker:
    name: "Meeting Tracker"
    description: "Track meeting notes and action items"
    allowed_stores:
      - meetings
    required_roles:
      - employee
    pii_level: metadata_only
    audit_level: detailed
    max_results: 20

  project_assistant:
    name: "Project Team Assistant"
    description: "Access project docs and shared files"
    allowed_stores:
      - project_teams
      - shared_documents
    required_roles:
      - project_member
    pii_level: partial
    audit_level: detailed
    enable_smart_selection: true

  confidential_research:
    name: "Confidential Research Assistant"
    description: "Access to market data and research"
    allowed_stores:
      - confidential
    required_roles:
      - analyst
      - manager
    denied_roles:
      - contractor
    pii_level: full
    audit_level: forensic
    log_results: true

  email_search:
    name: "Email Search"
    description: "Search email messages and threads"
    allowed_stores:
      - emails
    required_roles:
      - employee
    pii_level: partial
    audit_level: detailed
    default_filters:
      date_range: "last_30_days"
"""
