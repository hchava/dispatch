"""Tool definitions passed to the Claude API."""

SEARCH_CONTEXT_TOOL = {
    "name": "search_context",
    "description": (
        "Search the knowledge base for relevant runbooks, data contracts, and "
        "prior incident resolutions. Use specific terms from the alert — pipeline "
        "name, error type, metric name — to get precise results."
    ),
    "input_schema": {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Be specific: include pipeline name and failure type.",
            },
            "source_types": {
                "type": "array",
                "items": {"type": "string", "enum": ["runbook", "contract", "incident"]},
                "description": "Limit results to specific document types. Omit to search all.",
            },
            "pipeline": {
                "type": "string",
                "description": "Filter to a specific pipeline name. Omit to search across all.",
            },
        },
    },
}
