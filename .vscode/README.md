# VS Code + GitHub Copilot Integration

This directory contains the configuration for integrating the Azure Operator MCP Server with VS Code and GitHub Copilot.

## 📁 What's Included

- **settings.json** - Pre-configured MCP server settings for GitHub Copilot
- Automatic path resolution using `${workspaceFolder}`
- Python environment configuration
- Recommended VS Code settings for development

## 🚀 Quick Setup

1. **Open this repository in VS Code**
   ```bash
   code /path/to/Azure-Operations-MCP
   ```

2. **Run the setup script** from `mcp/azure-operator`:
   ```bash
   ./setup_vscode.sh  # macOS/Linux
   # or
   setup_vscode.bat   # Windows
   ```

3. **Restart VS Code**

4. **Open GitHub Copilot Chat** (Ctrl+Shift+I or Cmd+Shift+I)

5. **Test the connection**:
   ```
   @azure-operator What tools are available?
   ```

## ⚙️ Configuration Details

### MCP Server Configuration

The `settings.json` file configures GitHub Copilot to use the Azure Operator MCP server:

```json
{
  "github.copilot.advanced": {
    "mcp": {
      "servers": {
        "azure-operator": {
          "command": "python",
          "args": ["${workspaceFolder}/mcp/azure-operator/mcp_server.py"],
          "env": {
            "PYTHONPATH": "${workspaceFolder}/mcp/azure-operator",
            "LOG_LEVEL": "INFO"
          },
          "cwd": "${workspaceFolder}/mcp/azure-operator"
        }
      }
    }
  }
}
```

### Environment Variables

You can customize the server behavior by modifying the `env` section:

- **LOG_LEVEL**: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)
- **TEST_MODE**: Set to `true` to run without Azure authentication
- **AZURE_CLIENT_ID**: Service Principal client ID (optional)
- **AZURE_TENANT_ID**: Azure tenant ID (optional)
- **AZURE_CLIENT_SECRET**: Service Principal secret (optional)

Example with test mode:
```json
"env": {
  "PYTHONPATH": "${workspaceFolder}/mcp/azure-operator",
  "LOG_LEVEL": "DEBUG",
  "TEST_MODE": "true"
}
```

## 🔍 Troubleshooting

### Server Not Starting?

1. **Check VS Code Output Panel**:
   - View → Output
   - Select "GitHub Copilot Chat" from dropdown
   - Look for error messages

2. **Verify Python Environment**:
   ```bash
   cd mcp/azure-operator
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   python validate.py
   ```

3. **Check Server Logs**:
   - Logs appear in the VS Code Output panel when MCP server starts
   - Look for "Azure Operator MCP Server" startup banner

### Common Issues

#### "Module not found" errors
**Solution**: Make sure you ran the setup script or installed dependencies:
```bash
cd mcp/azure-operator
pip install -r requirements.txt
```

#### Server starts but @azure-operator not available
**Solution**: 
1. Restart VS Code completely (not just reload window)
2. Check that GitHub Copilot Chat extension is installed and enabled
3. Verify settings.json is in `.vscode/` directory at workspace root

#### Authentication errors
**Solution**: Run `az login` before starting VS Code:
```bash
az login
code .
```

#### "Python command not found"
**Solution**: Update the command path in settings.json:
```json
"command": "/full/path/to/python",
```

Or use the virtual environment Python:
```json
"command": "${workspaceFolder}/mcp/azure-operator/venv/bin/python",
```

## 📊 Monitoring Server Status

### Enable Debug Logging

Update settings.json:
```json
"env": {
  "LOG_LEVEL": "DEBUG"
}
```

### View Server Output

1. Open Output panel: View → Output (or Ctrl+Shift+U)
2. Select "GitHub Copilot Chat" from dropdown
3. Watch for MCP server messages

### Expected Startup Output

```
============================================================
Azure Operator MCP Server v1.0.0
Model Context Protocol for Azure Operations
============================================================
🔍 Validating environment...
✅ Environment validation passed
🔐 Initializing authentication...
✅ Authentication mode: Azure CLI Login (local dev)
🚀 Starting MCP server via stdio...
📡 Ready to accept connections from MCP clients
============================================================
```

## 🎯 Usage Examples

Once configured, you can use natural language commands in GitHub Copilot Chat:

### Discovery
```
@azure-operator List all app services in my subscription
@azure-operator Show me all AKS clusters
@azure-operator What resources are in resource group "production"?
```

### Diagnostics
```
@azure-operator Check the health of my app service "my-webapp"
@azure-operator Show me failing pods in AKS cluster "prod-aks"
@azure-operator Get recent exceptions from App Insights
```

### Best Practices
```
@azure-operator Check security best practices for my app service
@azure-operator Analyze my AKS cluster configuration
@azure-operator Review my resource tagging compliance
```

### Actions (with approval)
```
@azure-operator Restart my app service with approval
@azure-operator Scale node pool to 5 nodes (approve: true)
@azure-operator Enable autoscale for my app service plan
```

## 🔐 Security Notes

- All remediation actions require `approve: true` parameter
- No secrets are returned in plaintext (automatically masked)
- Rate limiting: 10 actions per minute
- All actions are logged for audit
- Read-only by default

## 📚 Additional Resources

- [Quick Start Guide](../mcp/azure-operator/QUICK_START.md)
- [Full Installation Guide](../MCP_INSTALLATION_GUIDE.md)
- [MCP Best Practices](../MCP_BEST_PRACTICES.md)
- [App Service Tools Documentation](../mcp/azure-operator/APP_SERVICE_TOOLS_README.md)
- [AKS Tools Documentation](../mcp/azure-operator/AKS_TOOLS_README.md)

## 💡 Tips

1. **Use specific names**: Instead of "my app", use the actual resource name
2. **Include subscription IDs**: For multi-subscription environments
3. **Check best practices regularly**: Use the best practices tools proactively
4. **Test mode**: Use TEST_MODE=true for testing without Azure access
5. **Save workspace**: Save as workspace file (.code-workspace) to preserve settings

## 🆘 Need Help?

1. Run validation: `python validate.py` in `mcp/azure-operator`
2. Check logs in VS Code Output panel
3. See troubleshooting guide in MCP_INSTALLATION_GUIDE.md
4. Review server.py for tool documentation
5. Open an issue on GitHub

---

**Ready to manage Azure with AI!** 🚀
