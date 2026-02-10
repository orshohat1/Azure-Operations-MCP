"""
Azure Operator MCP Server
Following MCP best practices from https://modelcontextprotocol.info/docs/best-practices/
"""

import os
import logging
import asyncio
from typing import Any, Sequence
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

# Import local modules
from auth import AuthManager
from utils import check_rate_limit, log_action

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("azure-operator-mcp")

# Initialize MCP server
server = Server("azure-operator")

# Global auth manager
auth_manager = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Azure operator tools"""
    tools = [
        # App Service Observability Tools
        Tool(
            name="list_app_services",
            description="List all Azure App Services in a subscription",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Azure subscription ID"
                    }
                },
                "required": ["subscription_id"]
            }
        ),
        Tool(
            name="get_app_service_state",
            description="Get the current state of an App Service (Running/Stopped/Degraded)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string", "description": "Azure subscription ID"},
                    "app_name": {"type": "string", "description": "App Service name"}
                },
                "required": ["subscription_id", "app_name"]
            }
        ),
        Tool(
            name="get_app_service_config",
            description="Get App Service configuration including settings, slots, and runtime stack",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "app_name": {"type": "string"}
                },
                "required": ["subscription_id", "app_name"]
            }
        ),
        Tool(
            name="check_app_service_best_practices",
            description="Comprehensive best practices check for App Service (HTTPS, Always On, TLS version, deployment slots)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "app_name": {"type": "string"}
                },
                "required": ["subscription_id", "app_name"]
            }
        ),
        
        # AKS Observability Tools
        Tool(
            name="list_aks_clusters",
            description="List all AKS clusters in a subscription",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"}
                },
                "required": ["subscription_id"]
            }
        ),
        Tool(
            name="get_aks_status",
            description="Get detailed AKS cluster status including node pools and Kubernetes version",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "cluster_name": {"type": "string", "description": "AKS cluster name"}
                },
                "required": ["subscription_id", "cluster_name"]
            }
        ),
        Tool(
            name="get_aks_cluster_diagnostics",
            description="Get diagnostic settings and monitoring configuration for AKS cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "cluster_name": {"type": "string"}
                },
                "required": ["subscription_id", "cluster_name"]
            }
        ),
        Tool(
            name="check_aks_best_practices",
            description="Comprehensive AKS best practices check (RBAC, network policy, monitoring, autoscaling)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "cluster_name": {"type": "string"}
                },
                "required": ["subscription_id", "cluster_name"]
            }
        ),
        Tool(
            name="check_aks_security_config",
            description="Security configuration assessment for AKS (RBAC, private cluster, network policy, Azure Policy)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "cluster_name": {"type": "string"}
                },
                "required": ["subscription_id", "cluster_name"]
            }
        ),
        
        # App Service Remediation Tools
        Tool(
            name="restart_app_service",
            description="Restart an Azure App Service (requires approval)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "app_name": {"type": "string"},
                    "approve": {"type": "boolean", "description": "Must be true to execute"}
                },
                "required": ["subscription_id", "app_name", "approve"]
            }
        ),
        Tool(
            name="set_app_setting",
            description="Update an App Service application setting (requires approval)",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "app_name": {"type": "string"},
                    "key": {"type": "string", "description": "Setting key"},
                    "value": {"type": "string", "description": "Setting value"},
                    "approve": {"type": "boolean"}
                },
                "required": ["subscription_id", "app_name", "key", "value", "approve"]
            }
        ),
        
        # Infrastructure Best Practices
        Tool(
            name="check_resource_tagging",
            description="Check resource tagging compliance in a resource group",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "resource_group": {"type": "string", "description": "Resource group name"}
                },
                "required": ["subscription_id", "resource_group"]
            }
        ),
        Tool(
            name="check_monitoring_coverage",
            description="Assess monitoring coverage across resources in a resource group",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "resource_group": {"type": "string"}
                },
                "required": ["subscription_id", "resource_group"]
            }
        )
    ]
    
    logger.info(f"Listed {len(tools)} available tools")
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool execution"""
    logger.info(f"Tool called: {name} with arguments: {arguments}")
    
    try:
        # Import tool modules dynamically
        import app_service_tools
        import aks_tools
        import best_practices_tools
        
        # Route to appropriate tool handler
        if name == "list_app_services":
            from models import BaseRequest
            request = BaseRequest(**arguments)
            result = await app_service_tools.list_app_services(auth_manager, request)
            
        elif name == "get_app_service_state":
            from models import AppServiceRequest
            request = AppServiceRequest(**arguments)
            result = await app_service_tools.get_app_service_state(auth_manager, request)
            
        elif name == "get_app_service_config":
            from models import AppServiceRequest
            request = AppServiceRequest(**arguments)
            result = await app_service_tools.get_app_service_config(auth_manager, request)
            
        elif name == "check_app_service_best_practices":
            from models import AppServiceRequest
            request = AppServiceRequest(**arguments)
            result = await app_service_tools.check_app_service_best_practices(auth_manager, request)
            
        elif name == "list_aks_clusters":
            from models import BaseRequest
            request = BaseRequest(**arguments)
            result = await aks_tools.list_aks_clusters(auth_manager, request)
            
        elif name == "get_aks_status":
            from models import AKSRequest
            request = AKSRequest(**arguments)
            result = await aks_tools.get_aks_status(auth_manager, request)
            
        elif name == "get_aks_cluster_diagnostics":
            from models import AKSRequest
            request = AKSRequest(**arguments)
            result = await aks_tools.get_aks_cluster_diagnostics(auth_manager, request)
            
        elif name == "check_aks_best_practices":
            from models import AKSRequest
            request = AKSRequest(**arguments)
            result = await aks_tools.check_aks_best_practices(auth_manager, request)
            
        elif name == "check_aks_security_config":
            from models import AKSRequest
            request = AKSRequest(**arguments)
            result = await aks_tools.check_aks_security_config(auth_manager, request)
            
        elif name == "restart_app_service":
            from models import RestartAppServiceRequest
            request = RestartAppServiceRequest(**arguments)
            result = await app_service_tools.restart_app_service(auth_manager, request)
            
        elif name == "set_app_setting":
            from models import SetAppSettingRequest
            request = SetAppSettingRequest(**arguments)
            result = await app_service_tools.set_app_setting(auth_manager, request)
            
        elif name == "check_resource_tagging":
            from models import ResourceGroupRequest
            request = ResourceGroupRequest(**arguments)
            result = await best_practices_tools.check_resource_tagging(auth_manager, request)
            
        elif name == "check_monitoring_coverage":
            from models import ResourceGroupRequest
            request = ResourceGroupRequest(**arguments)
            result = await best_practices_tools.check_monitoring_coverage(auth_manager, request)
            
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        # Format result as MCP response
        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
        
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}", exc_info=True)
        return [TextContent(
            type="text",
            text=f"Error: {str(e)}"
        )]


def validate_environment():
    """Validate that the environment is properly configured"""
    issues = []
    
    # Check Python version
    import sys
    if sys.version_info < (3, 11):
        issues.append(f"Python 3.11+ required, found {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check required modules
    required_modules = [
        'azure.identity',
        'azure.mgmt.web',
        'azure.mgmt.monitor',
        'azure.mgmt.containerservice',
        'mcp',
        'mcp.server',
    ]
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            issues.append(f"Missing required module: {module}")
    
    # Check if TEST_MODE is enabled
    if os.getenv("TEST_MODE", "false").lower() == "true":
        logger.info("🧪 Running in TEST MODE - No Azure authentication required")
    else:
        # Check Azure authentication
        if not os.getenv("AZURE_CLIENT_ID") and not os.path.exists(os.path.expanduser("~/.azure")):
            logger.warning("⚠️  No Azure CLI login detected and no service principal configured")
            logger.warning("💡 Run 'az login' or set AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET")
    
    return issues


async def main():
    """Main entry point for MCP server"""
    global auth_manager
    
    # Print banner
    logger.info("=" * 60)
    logger.info("Azure Operator MCP Server v1.0.0")
    logger.info("Model Context Protocol for Azure Operations")
    logger.info("=" * 60)
    
    # Validate environment
    logger.info("🔍 Validating environment...")
    issues = validate_environment()
    
    if issues:
        logger.error("❌ Environment validation failed:")
        for issue in issues:
            logger.error(f"  - {issue}")
        logger.error("\n💡 Please run: pip install -r requirements.txt")
        return 1
    
    logger.info("✅ Environment validation passed")
    
    # Initialize authentication
    logger.info("🔐 Initializing authentication...")
    try:
        auth_manager = AuthManager()
        logger.info(f"✅ Authentication mode: {auth_manager.auth_mode}")
    except Exception as e:
        logger.error(f"❌ Authentication failed: {e}")
        if os.getenv("TEST_MODE", "false").lower() != "true":
            logger.info("💡 Set TEST_MODE=true to run without Azure authentication")
        return 1
    
    # Run the stdio server
    logger.info("🚀 Starting MCP server via stdio...")
    logger.info("📡 Ready to accept connections from MCP clients")
    logger.info("=" * 60)
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        logger.info("\n🛑 Server stopped by user")
        return 0
    except Exception as e:
        logger.error(f"❌ Server error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code if exit_code else 0)
