"""Tools: plain Python functions the agent can call.

Rule for this package: no LLM code here. A tool is just a function that takes
arguments and returns JSON-friendly data. That separation is what lets the
same tools be reused later by an MCP server or a LangGraph graph.
"""
