"""Tool definitions passed to the Claude API."""

SEARCH_CONTEXT_TOOL = {
    "name": "search_context",
    "description": (
        "Search the knowledge base for context relevant to an oncall alert. "
        "The knowledge base contains: runbooks (triage steps), data contracts "
        "(schema, SLA, ownership, upstream/downstream dependencies), prior incident "
        "resolutions, code patterns (backfill, schema repair, exactly-once writes), "
        "and validation examples (row count, null rate, distribution bounds checks). "
        "Use specific terms from the alert — pipeline name, error type, metric name, "
        "column name — to get precise results. Call multiple times with different "
        "queries to build complete context."
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
                "items": {
                    "type": "string",
                    "enum": ["runbook", "contract", "incident", "code_pattern", "validation_example"],
                },
                "description": (
                    "Limit results to specific document types. "
                    "runbook=triage steps, contract=schema/SLA/ownership, "
                    "incident=prior resolutions, code_pattern=fix recipes, "
                    "validation_example=test expectations. Omit to search all."
                ),
            },
            "pipeline": {
                "type": "string",
                "description": "Filter to a specific pipeline name. Omit to search across all.",
            },
        },
    },
}
