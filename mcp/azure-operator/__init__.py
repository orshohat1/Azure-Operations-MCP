"""
Azure Operator MCP Server Package

A Model Context Protocol (MCP) server for Azure operations, diagnostics, and remediation.
Designed to integrate with GitHub Copilot, Claude Desktop, and other AI assistants.
"""

__version__ = "1.0.0"
__author__ = "Azure Operations MCP Team"
__description__ = "MCP server for Azure infrastructure operations and best practices"

# Package-level exports
from .auth import AuthManager
from .models import *
from .utils import check_rate_limit, log_action

__all__ = [
    "AuthManager",
    "check_rate_limit",
    "log_action",
    "__version__",
]
