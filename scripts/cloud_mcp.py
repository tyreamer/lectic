"""Goal-oriented MCP tools and dispatcher for authenticated WayKit Cloud accounts.

Exposes conversational operations for AI assistants:
- save_knowledge
- learn_from_source
- organize_knowledge
- get_relevant_context
- apply_knowledge
- search_knowledge
- export_library

All executions are strictly sandboxed inside the verified account's private library.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from account_service import AuthorizationError
from cloud_library import CloudLibrary
from ec import Invalid

CLOUD_TOOLS = [
    {
        'name': 'save_knowledge',
        'description': 'Save a link, note, text, or source to your private WayKit library and process it immediately into reusable knowledge when destination is clear. If ambiguous, asks for collection clarification.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'text': {'type': 'string', 'description': 'Text content, article excerpt, or notes to save.'},
                'url': {'type': 'string', 'description': 'Web or YouTube URL to save.'},
                'title': {'type': 'string', 'description': 'Optional title or label for the material.'},
                'note': {'type': 'string', 'description': 'Personal context or reason for saving.'},
                'collections': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Optional target collection names.'}
            },
            'additionalProperties': False
        }
    },
    {
        'name': 'learn_from_source',
        'description': 'Extract and compile structured, reusable expertise from a saved capture, source, or text. Preserves source citations and distinguishes observed statements from interpretations.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'text': {'type': 'string', 'description': 'Direct text to learn from if not previously saved.'},
                'capture_id': {'type': 'string', 'description': 'ID of a saved capture in your library.'},
                'collection': {'type': 'string', 'description': 'Name of the knowledge collection or pack to create or update.'},
                'title': {'type': 'string', 'description': 'Title for the source material.'},
                'units': {
                    'type': 'array',
                    'items': {'type': 'object'},
                    'description': 'Optional pre-structured knowledge units designed by the assistant.'
                },
                'note': {'type': 'string', 'description': 'Optional notes on the extraction.'}
            },
            'additionalProperties': False
        }
    },
    {
        'name': 'organize_knowledge',
        'description': 'Organize collections and define or infer relationships between packs (such as specialization, domain hierarchy, or personal preferences).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'action': {
                    'type': 'string',
                    'enum': ['infer', 'link', 'unlink', 'explain'],
                    'description': 'Action to perform: infer relationships, explicitly link, unlink, or explain a pack.'
                },
                'source_collection': {'type': 'string', 'description': 'Source collection name.'},
                'target_collection': {'type': 'string', 'description': 'Target collection name.'},
                'relationship': {
                    'type': 'string',
                    'enum': ['related_to', 'specializes', 'part_of', 'useful_with', 'derived_from', 'supersedes', 'contradicts', 'personal_preference_relevant_to', 'learned_from'],
                    'description': 'Relationship type.'
                },
                'reason': {'type': 'string', 'description': 'Plain-language rationale for the relationship.'}
            },
            'additionalProperties': False
        }
    },
    {
        'name': 'get_relevant_context',
        'description': 'Selectively retrieve relevant knowledge units across related packs for a task or question, without loading unrelated knowledge. Keeps task context non-persistent.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'intent': {'type': 'string', 'description': 'What task, question, or goal WayKit should prepare knowledge for.'},
                'task_context': {'type': 'string', 'description': 'Ephemeral details of the current task (budget, constraints, drafts). Not permanently saved.'},
                'max_units': {'type': 'integer', 'description': 'Maximum units to retrieve (default 24).'}
            },
            'required': ['intent'],
            'additionalProperties': False
        }
    },
    {
        'name': 'apply_knowledge',
        'description': 'Apply relevant compiled knowledge to review, solve, or plan a task, producing an auditable checklist and recommendations citing exact source evidence.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'intent': {'type': 'string', 'description': 'The review, decision, or planning task to perform.'},
                'task_context': {'type': 'string', 'description': 'Current project draft, situation details, or constraints.'},
                'collection': {'type': 'string', 'description': 'Optional specific collection to prioritize.'}
            },
            'required': ['intent'],
            'additionalProperties': False
        }
    },
    {
        'name': 'search_knowledge',
        'description': 'Search across all knowledge units and sources in your private library with evidence citations.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Keywords or concepts to search for.'},
                'limit': {'type': 'integer', 'description': 'Maximum number of results to return (default 10).'}
            },
            'required': ['query'],
            'additionalProperties': False
        }
    },
    {
        'name': 'export_library',
        'description': 'Export your entire private library into a portable WayKit archive (.waykit-home or .lectic-home) that can be inspected, moved, or restored into local WayKit.',
        'inputSchema': {
            'type': 'object',
            'properties': {},
            'additionalProperties': False
        }
    }
]


class CloudMcpHandler:
    """Dispatches authenticated MCP tool requests to an isolated CloudLibrary instance."""

    def __init__(self, cloud_library: CloudLibrary):
        self.library = cloud_library

    def list_tools(self) -> List[Dict[str, Any]]:
        return CLOUD_TOOLS

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool call and return MCP-compliant result object."""
        # Normalize tool names with or without waykit_ / lectic_ prefix
        if name.startswith('waykit_'):
            name = name[len('waykit_'):]
        elif name.startswith('lectic_'):
            name = name[len('lectic_'):]

        # Never allow caller to supply or override user identity
        for banned in ('account_id', 'user_id', 'home', 'project'):
            if banned in arguments:
                arguments.pop(banned, None)

        try:
            if name == 'save_knowledge':
                res = self.library.save_knowledge(
                    text=arguments.get('text', ''),
                    url=arguments.get('url', ''),
                    title=arguments.get('title', ''),
                    note=arguments.get('note', ''),
                    collections=tuple(arguments.get('collections', ()))
                )
            elif name == 'learn_from_source':
                res = self.library.learn_from_source(
                    text=arguments.get('text'),
                    capture_id=arguments.get('capture_id'),
                    collection=arguments.get('collection'),
                    title=arguments.get('title'),
                    units=arguments.get('units'),
                    note=arguments.get('note')
                )
            elif name == 'organize_knowledge':
                res = self.library.organize_knowledge(
                    action=arguments.get('action', 'infer'),
                    source_collection=arguments.get('source_collection'),
                    target_collection=arguments.get('target_collection'),
                    relationship=arguments.get('relationship'),
                    reason=arguments.get('reason')
                )
            elif name == 'get_relevant_context':
                res = self.library.get_relevant_context(
                    intent=arguments['intent'],
                    task_context=arguments.get('task_context', ''),
                    max_units=int(arguments.get('max_units', 24))
                )
            elif name == 'apply_knowledge':
                res = self.library.apply_knowledge(
                    intent=arguments['intent'],
                    task_context=arguments.get('task_context', ''),
                    collection=arguments.get('collection')
                )
            elif name == 'search_knowledge':
                res = self.library.search_knowledge(
                    query=arguments['query'],
                    limit=int(arguments.get('limit', 10))
                )
            elif name == 'export_library':
                raw_bytes = self.library.export_library()
                import base64
                res = {
                    'phase': 'library_exported',
                    'format': 'waykit-home',
                    'legacy_format': 'lectic-home',
                    'archive_size_bytes': len(raw_bytes),
                    'archive_base64': base64.b64encode(raw_bytes).decode('ascii'),
                    'message': 'Library exported successfully. Save or restore locally with: waykit restore <file>'
                }
            else:
                return {
                    'content': [{'type': 'text', 'text': f'Unknown tool: {name}'}],
                    'isError': True
                }

            return {
                'content': [{'type': 'text', 'text': json.dumps(res, indent=2, ensure_ascii=False)}],
                'isError': False
            }

        except (Invalid, AuthorizationError, ValueError, TypeError) as exc:
            return {
                'content': [{'type': 'text', 'text': f'Error executing {name}: {exc}'}],
                'isError': True
            }
        except Exception as exc:
            return {
                'content': [{'type': 'text', 'text': f'Internal server error: {exc}'}],
                'isError': True
            }
