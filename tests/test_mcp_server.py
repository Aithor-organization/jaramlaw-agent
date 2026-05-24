from jaramlaw_agent.mcp_server import handle_tool


def test_mcp_unknown_tool_lists_available_tools():
    result = handle_tool("missing-tool", {})
    assert result["status"] == "error"
    assert "jaramlaw_review" in result["tools"]


def test_mcp_memory_search_tool():
    result = handle_tool("memory_search", {"query": "academy refund"})
    assert result["status"] == "success"
    assert result["memory"]["memory_version"] == "jaramlaw-memory/v1"
