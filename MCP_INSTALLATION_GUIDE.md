# Azure Operator MCP Server - Installation & Integration Guide

## 🎯 Overview

This guide explains how to install and configure the Azure Operator MCP Server to work with:
- **GitHub Copilot** in VSCode
- **Claude Desktop** app
- **Any MCP-compatible client**

The server follows [MCP best practices](https://modelcontextprotocol.info/docs/best-practices/) for optimal AI agent integration.

---

## 📋 Prerequisites

### Required
- **Python 3.11+** installed
- **Azure CLI** installed and configured (`az login`)
- **Git** for cloning the repository

### For GitHub Copilot Integration
- **VSCode** with latest version
- **GitHub Copilot** subscription and extension installed
- **GitHub Copilot Chat** extension enabled

### For Claude Desktop Integration
- **Claude Desktop** app installed

---

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/orshohat1/Azure-Operations-MCP.git
cd Azure-Operations-MCP/mcp/azure-operator
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Azure Authentication

Choose one of three authentication modes:

#### Option A: Azure CLI (Recommended for Local Development)
```bash
# Login to Azure
az login

# Set default subscription (optional)
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

#### Option B: Service Principal (For Automation)
Create a `.env` file:
```bash
cp .env.example .env
```

Edit `.env` and add:
```bash
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-client-secret
```

#### Option C: Managed Identity (For Azure Deployments)
No configuration needed - will auto-detect when running in Azure.

### Step 5: Test the Server

```bash
# Test in standalone mode
python mcp_server.py
```

You should see:
```
🔐 Authentication Mode: Azure CLI Login (local dev)
✅ Authentication successful using: Azure CLI / Developer
MCP server started via stdio
```

Press `Ctrl+C` to stop.

---

## 🔌 Integration with GitHub Copilot in VSCode

### Quick Setup (Recommended)

We provide an automated setup script that configures everything for you:

#### On macOS/Linux:
```bash
cd mcp/azure-operator
./setup_vscode.sh
```

#### On Windows:
```cmd
cd mcp\azure-operator
setup_vscode.bat
```

The script will:
1. ✓ Create and activate virtual environment
2. ✓ Install all dependencies
3. ✓ Check Azure authentication
4. ✓ Test MCP server startup
5. ✓ Verify VS Code configuration

After running the script, **restart VS Code** and you're ready to go!

---

### Manual Setup

If you prefer manual configuration, follow these steps:

### Step 1: Verify GitHub Copilot Extensions

Ensure you have these extensions installed in VSCode:
1. **GitHub Copilot** - AI pair programmer
2. **GitHub Copilot Chat** - Chat interface for Copilot

### Step 2: Configure MCP Server in VSCode

The repository includes a pre-configured `.vscode/settings.json` file that sets up the MCP server.

**Workspace Configuration** (already included):

```json
{
  "github.copilot.advanced": {
    "mcp": {
      "servers": {
        "azure-operator": {
          "command": "python",
          "args": [
            "${workspaceFolder}/mcp/azure-operator/mcp_server.py"
          ],
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

**For User Settings** (if you want global configuration):

1. Open VSCode Settings (Cmd/Ctrl + ,)
2. Search for "Copilot MCP" or click the gear icon → Settings (JSON)
3. Add the MCP server configuration with absolute paths:

```json
{
  "github.copilot.advanced": {
    "mcp": {
      "servers": {
        "azure-operator": {
          "command": "python",
          "args": [
            "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator/mcp_server.py"
          ],
          "cwd": "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator",
          "env": {
            "PYTHONPATH": "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator",
            "LOG_LEVEL": "INFO"
          }
        }
      }
    }
  }
}
```

**Note:** Replace `/absolute/path/to/` with your actual path.

### Step 3: Validate Installation

Run the validation script to ensure everything is working:

```bash
cd mcp/azure-operator
python validate.py
```

You should see:
```
✅ All validations passed! Server is ready to use.
```

### Step 4: Restart VSCode

Close and reopen VSCode to load the MCP server configuration.

### Step 5: Verify Connection

1. Open GitHub Copilot Chat (Cmd/Ctrl + Shift + I or click the chat icon)
2. Type: `@azure-operator` and press space
3. You should see the Azure Operator MCP server as an available context
4. Try a test command:
   ```
   @azure-operator What tools are available?
   ```

### Step 6: Using Azure Operator with Copilot

Example prompts:

```
@azure-operator Show me all AKS clusters in my subscription

@azure-operator Check best practices for app service "my-webapp"

@azure-operator Get the status of AKS cluster "prod-cluster"

@azure-operator Check security configuration for AKS cluster "prod-cluster"

@azure-operator What are the tagging compliance issues in resource group "rg-prod"?
```

---

## 🖥️ Integration with Claude Desktop

### Step 1: Find Claude Desktop Config

The configuration file location varies by OS:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

### Step 2: Edit Configuration

Add the Azure Operator MCP server:

```json
{
  "mcpServers": {
    "azure-operator": {
      "command": "python",
      "args": [
        "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator/venv/bin/python",
        "-m",
        "mcp_server"
      ],
      "cwd": "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Azure-Operations-MCP/mcp/azure-operator",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Step 3: Restart Claude Desktop

Quit and reopen Claude Desktop.

### Step 4: Use Azure Tools in Claude

In Claude Desktop chat:

```
Use the azure-operator MCP to list all App Services in subscription sub-12345

Check AKS best practices for cluster prod-aks-01

What security issues exist in my AKS clusters?
```

---

## 🛠️ Troubleshooting

### Issue: "MCP server not found"

**Solution:**
1. Verify Python path is correct:
   ```bash
   which python  # macOS/Linux
   where python  # Windows
   ```
2. Ensure virtual environment is activated
3. Check `PYTHONPATH` in config points to the correct directory

### Issue: "Authentication failed"

**Solution:**
1. Run `az login` again
2. Check your Azure credentials:
   ```bash
   az account show
   ```
3. Verify subscription access:
   ```bash
   az account list
   ```

### Issue: "Module not found"

**Solution:**
1. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Verify all files are present:
   ```bash
   ls -la mcp/azure-operator/
   ```

### Issue: "Permission denied"

**Solution:**
1. Ensure your Azure account has proper RBAC roles:
   - **Reader** role minimum for observability tools
   - **Contributor** role for remediation actions
2. Check role assignments:
   ```bash
   az role assignment list --assignee $(az account show --query user.name -o tsv)
   ```

### Enable Debug Logging

Edit your MCP config and set:
```json
"env": {
  "LOG_LEVEL": "DEBUG"
}
```

Then check logs in:
- **VSCode:** View → Output → Select "GitHub Copilot MCP"
- **Claude Desktop:** Help → View Logs

---

## 📚 Available Tools

The MCP server provides **100+ tools** across these categories:

### 🔍 Observability (50+ tools)
- **App Service:** list, status, config, logs, diagnostics, deployments
- **AKS:** clusters, nodes, pods, services, ingresses, resources
- **Azure Monitor:** metrics, alerts, logs, Application Insights

### 🔧 Remediation (30+ tools)
- **App Service:** restart, scale, configure, deploy, swap slots
- **AKS:** upgrade, scale nodepools, manage addons, pod operations
- **Kubernetes:** scale deployments, rollback, drain nodes

### ✅ Best Practices (20+ tools)
- **App Service:** security, availability, performance, cost optimization
- **AKS:** security config, RBAC, network policies, cost optimization
- **Infrastructure:** tagging, monitoring, network security, resource locks

---

## 🔒 Security Best Practices

### 1. Use Least Privilege

Grant minimum Azure RBAC permissions:
```bash
# Reader role for observability only
az role assignment create --assignee USER_OR_SP \
  --role Reader \
  --scope /subscriptions/SUBSCRIPTION_ID

# Contributor for remediation
az role assignment create --assignee USER_OR_SP \
  --role Contributor \
  --scope /subscriptions/SUBSCRIPTION_ID/resourceGroups/RG_NAME
```

### 2. Rate Limiting

The server enforces **10 actions per minute** by default.

Configure in `.env`:
```bash
MAX_ACTIONS_PER_MINUTE=5
```

### 3. Approval Required

All remediation actions require `approve: true`:
```json
{
  "subscription_id": "sub-123",
  "app_name": "my-app",
  "approve": true
}
```

### 4. Audit Logging

All actions are logged with:
- Timestamp
- Action name
- Parameters
- Success/failure
- Error details (if any)

Check logs:
```bash
tail -f logs/azure-operator.log
```

---

## 🎯 Next Steps

1. **Explore Tools:** Try different Azure operator tools
2. **Create Workflows:** Combine multiple tools for complex tasks
3. **Set Up Alerts:** Configure monitoring for your resources
4. **Contribute:** Add more tools or improve existing ones

---

## 📖 Additional Resources

- [MCP Documentation](https://modelcontextprotocol.info/)
- [MCP Best Practices](https://modelcontextprotocol.info/docs/best-practices/)
- [Azure SDK for Python](https://learn.microsoft.com/en-us/azure/developer/python/)
- [GitHub Copilot Docs](https://docs.github.com/en/copilot)

---

## 🆘 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review [GitHub Issues](https://github.com/orshohat1/Azure-Operations-MCP/issues)
3. Create a new issue with:
   - Error messages
   - Configuration details
   - Steps to reproduce

---

## 📝 License

MIT License - See LICENSE file for details
