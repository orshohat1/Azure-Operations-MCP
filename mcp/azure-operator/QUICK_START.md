# 🚀 Quick Start Guide - Azure Operator MCP Server

Get up and running with the Azure Operator MCP Server in under 5 minutes!

## Prerequisites

- Python 3.11 or higher
- Azure CLI (`az`) installed
- VS Code with GitHub Copilot extension (for VS Code integration)
- Git

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/orshohat1/Azure-Operations-MCP.git
cd Azure-Operations-MCP
```

### 2. Setup for VS Code + GitHub Copilot (Recommended)

Run the automated setup script:

**macOS/Linux:**
```bash
cd mcp/azure-operator
./setup_vscode.sh
```

**Windows:**
```cmd
cd mcp\azure-operator
setup_vscode.bat
```

This script will:
- ✅ Create virtual environment
- ✅ Install all dependencies
- ✅ Check Azure authentication
- ✅ Test server startup
- ✅ Configure VS Code

### 3. Authenticate with Azure

```bash
az login
```

### 4. Restart VS Code

Close and reopen VS Code to load the MCP server.

### 5. Test It!

Open GitHub Copilot Chat in VS Code and try:

```
@azure-operator What tools do you have available?
```

```
@azure-operator List all app services
```

```
@azure-operator Check best practices for my AKS cluster
```

---

## 🎯 Common Use Cases

### Observability
```
@azure-operator Show me failing pods in my AKS cluster
@azure-operator Get recent exceptions from App Insights
@azure-operator Check the state of my app service
```

### Best Practices
```
@azure-operator Check best practices for my app service
@azure-operator Analyze AKS security configuration
@azure-operator Review resource tagging compliance
```

### Remediation (requires approval)
```
@azure-operator Restart my app service (with approval)
@azure-operator Scale the AKS node pool
@azure-operator Enable detailed error logs
```

---

## 🔧 Manual Installation (Alternative)

If you prefer manual setup:

```bash
cd Azure-Operations-MCP/mcp/azure-operator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Test the server
python validate.py

# Test manual run
TEST_MODE=true python mcp_server.py
```

---

## 🩺 Troubleshooting

### Validation Failed?

Run the validation script to diagnose issues:

```bash
cd mcp/azure-operator
python validate.py
```

### Server Not Connecting?

Check VS Code Output:
1. View → Output
2. Select "GitHub Copilot Chat" from dropdown
3. Look for connection errors

### Azure Authentication Issues?

```bash
# Check if logged in
az account show

# Login if needed
az login

# List subscriptions
az account list --output table
```

### Still Having Issues?

1. Check the logs in VS Code Output panel
2. Try TEST_MODE: Set `TEST_MODE=true` in `.vscode/settings.json`
3. See detailed troubleshooting in `MCP_INSTALLATION_GUIDE.md`

---

## 📚 Documentation

- **[Full Installation Guide](../MCP_INSTALLATION_GUIDE.md)** - Complete setup instructions
- **[Best Practices](../MCP_BEST_PRACTICES.md)** - How we follow MCP standards
- **[App Service Tools](APP_SERVICE_TOOLS_README.md)** - 33 App Service tools
- **[AKS Tools](AKS_TOOLS_README.md)** - 41 AKS/Kubernetes tools
- **[Final Summary](../FINAL_SUMMARY.md)** - Complete feature overview

---

## 🎉 You're Ready!

The Azure Operator MCP Server provides 100+ tools for managing Azure infrastructure through natural language with GitHub Copilot or Claude Desktop.

**Happy AI-powered Azure operations!** 🚀
