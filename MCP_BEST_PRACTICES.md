# MCP Best Practices Implementation

This document explains how the Azure Operator MCP Server follows the [official MCP best practices](https://modelcontextprotocol.info/docs/best-practices/).

## ✅ Best Practices Implemented

### 1. **Clear Tool Naming and Descriptions**

**Best Practice:** Use descriptive, action-oriented names and detailed descriptions.

**Implementation:**
```python
Tool(
    name="check_aks_best_practices",
    description="Comprehensive AKS best practices check (RBAC, network policy, monitoring, autoscaling)",
    inputSchema={...}
)
```

- ✅ Names follow verb-noun pattern: `list_app_services`, `check_aks_security`
- ✅ Descriptions explain what the tool does and what it returns
- ✅ Grouped by category (observability, remediation, best practices)

### 2. **Well-Defined Input Schemas**

**Best Practice:** Use JSON Schema to validate inputs and guide users.

**Implementation:**
```python
inputSchema={
    "type": "object",
    "properties": {
        "subscription_id": {
            "type": "string",
            "description": "Azure subscription ID"
        },
        "app_name": {
            "type": "string",
            "description": "App Service name"
        }
    },
    "required": ["subscription_id", "app_name"]
}
```

- ✅ All required fields marked explicitly
- ✅ Type validation for each parameter
- ✅ Descriptions for every property
- ✅ Nested schemas for complex inputs

### 3. **Proper Error Handling**

**Best Practice:** Return meaningful error messages that help users understand what went wrong.

**Implementation:**
```python
try:
    result = await execute_tool(...)
    return [TextContent(type="text", text=json.dumps(result))]
except HTTPException as e:
    return [TextContent(type="text", text=f"Error {e.status_code}: {e.detail}")]
except Exception as e:
    logger.error(f"Unexpected error: {str(e)}", exc_info=True)
    return [TextContent(type="text", text=f"Error: {str(e)}")]
```

- ✅ Specific error messages
- ✅ Error logging with context
- ✅ Graceful degradation
- ✅ HTTP status codes for API errors

### 4. **Structured Output**

**Best Practice:** Return well-structured JSON that's easy to parse and display.

**Implementation:**
```python
{
    "cluster_name": "prod-aks",
    "total_recommendations": 3,
    "recommendations": [
        {
            "category": "security",
            "severity": "high",
            "issue": "RBAC is not enabled",
            "recommendation": "Enable RBAC for fine-grained access control"
        }
    ]
}
```

- ✅ Consistent JSON structure
- ✅ Nested objects for complex data
- ✅ Arrays for collections
- ✅ Metadata (counts, summaries) included

### 5. **Security by Default**

**Best Practice:** Implement safety measures for destructive operations.

**Implementation:**
```python
# Require explicit approval
if not request.approve:
    raise HTTPException(status_code=403, detail="Action requires approve=true")

# Rate limiting
if not check_rate_limit():
    raise HTTPException(status_code=429, detail="Rate limit exceeded")

# Audit logging
log_action("restart_app_service", {
    "app_name": request.app_name
}, success=True)
```

- ✅ Approval required for all remediation actions
- ✅ Rate limiting (10 actions/minute)
- ✅ Audit logging for all actions
- ✅ Secret masking in responses
- ✅ Read-only mode by default

### 6. **Modular Architecture**

**Best Practice:** Organize code into logical modules for maintainability.

**Implementation:**
```
mcp/azure-operator/
├── mcp_server.py           # Main MCP server entry point
├── auth.py                 # Authentication management
├── models.py               # Pydantic request models
├── utils.py                # Utility functions
├── app_service_tools.py    # App Service tools
├── aks_tools.py            # AKS/Kubernetes tools
└── best_practices_tools.py # Infrastructure best practices
```

- ✅ Separation of concerns
- ✅ Each module has single responsibility
- ✅ Easy to test and maintain
- ✅ Clear dependencies

### 7. **Resource Efficiency**

**Best Practice:** Handle long-running operations efficiently.

**Implementation:**
```python
# Async operations
async def call_tool(name: str, arguments: dict):
    result = await execute_async_operation(arguments)
    return result

# Lazy loading
def list_tools():
    # Only import modules when needed
    import app_service_tools
    import aks_tools
```

- ✅ Async/await for I/O operations
- ✅ Connection pooling for Azure clients
- ✅ Lazy module loading
- ✅ Efficient JSON serialization

### 8. **Comprehensive Documentation**

**Best Practice:** Provide clear documentation for installation and usage.

**Implementation:**
- ✅ `MCP_INSTALLATION_GUIDE.md` - Step-by-step installation
- ✅ `README.md` - Overview and quick start
- ✅ Inline code comments
- ✅ Tool descriptions in MCP schema
- ✅ Example prompts and use cases

### 9. **Standard Communication Protocol**

**Best Practice:** Use stdio for MCP communication.

**Implementation:**
```python
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )
```

- ✅ stdio-based communication
- ✅ Standard MCP protocol
- ✅ Compatible with all MCP clients
- ✅ No custom transport layer

### 10. **Testing and Validation**

**Best Practice:** Validate inputs and test thoroughly.

**Implementation:**
```python
# Pydantic models for validation
class AppServiceRequest(BaseModel):
    subscription_id: str = Field(..., description="Azure subscription ID")
    app_name: str = Field(..., description="App Service name")

# Input validation happens automatically
request = AppServiceRequest(**arguments)
```

- ✅ Automatic input validation via Pydantic
- ✅ Type checking
- ✅ Required field validation
- ✅ Custom validation rules

---

## 🎯 Tool Categories

### Observability Tools (Read-Only)
**Design:** These tools never modify resources
- List resources
- Get status and configuration
- Query logs and metrics
- No approval required

### Remediation Tools (Write Operations)
**Design:** These tools can modify resources
- Require `approve=true` parameter
- Rate limited
- Audit logged
- Rollback support where possible

### Best Practices Tools (Analysis)
**Design:** These tools provide recommendations
- Analyze configuration
- Security assessment
- Cost optimization suggestions
- No modifications made

---

## 🔄 Continuous Improvement

We continuously update the server to follow new MCP best practices:

1. **Monitor MCP Updates:** Track MCP specification changes
2. **User Feedback:** Incorporate user suggestions
3. **Performance Optimization:** Improve response times
4. **Security Hardening:** Regular security audits

---

## 📚 References

- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/)
- [MCP Specification](https://modelcontextprotocol.info/docs/specification/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
