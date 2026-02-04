"""
Main entry point for running the Azure Operator MCP Server as a module.

Usage:
    python -m azure_operator_mcp
"""

import sys
import os

# Add the current directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the MCP server
from mcp_server import main

if __name__ == "__main__":
    main()
