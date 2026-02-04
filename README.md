# Azure Operations MCP

**Model Context Protocol (MCP) server for Azure Operations** - enables AI agents to observe, diagnose, and safely remediate Azure workloads.

[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.info/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 What is This?

The Azure Operator MCP Server provides **100+ tools** that allow AI assistants like GitHub Copilot and Claude to directly interact with your Azure infrastructure. It follows [MCP best practices](https://modelcontextprotocol.info/docs/best-practices/) for seamless AI integration.

### Example Prompts

```
@azure-operator list all app services in my subscription

@azure-operator check AKS best practices for cluster prod-aks

@azure-operator why is my app service slow in the last hour?

@azure-operator check security configuration for all AKS clusters

@azure-operator what tagging issues exist in resource group rg-prod?
```

## ✨ Features

### 🔍 **Observability (50+ tools)**
- **App Service:** State, config, logs, diagnostics, deployments, scaling rules
- **AKS:** Cluster status, node pools, networking, addons, upgrade history
- **Kubernetes:** Pods, services, deployments, StatefulSets, DaemonSets, events
- **Azure Monitor:** Metrics, alerts, Application Insights, KQL queries

### 🔧 **Remediation (30+ tools)**
- **App Service:** Restart, scale, configure settings, deploy, swap slots
- **AKS:** Upgrade versions, scale nodepools, manage addons, node operations
- **Kubernetes:** Scale deployments, rollback, drain nodes, apply manifests

### ✅ **Best Practices (20+ tools)**
- **App Service:** Security assessment, performance analysis, cost optimization
- **AKS:** Security config, RBAC review, network policies, upgrade readiness
- **Infrastructure:** Tagging compliance, monitoring coverage, resource locks

## 🚀 Quick Start

### Installation (5 minutes)

```bash
# Clone the repository
git clone https://github.com/orshohat1/Azure-Operations-MCP.git
cd Azure-Operations-MCP/mcp/azure-operator

# Run installation script
# macOS/Linux:
./install.sh
# Windows:
install.bat

# Authenticate with Azure
az login

# Test the server
source venv/bin/activate  # or: venv\Scripts\activate on Windows
python mcp_server.py
```

### Integration with GitHub Copilot in VSCode

1. Add to `.vscode/settings.json`:
```json
{
  "github.copilot.advanced": {
    "mcp": {
      "servers": {
        "azure-operator": {
          "command": "python",
          "args": ["-m", "mcp_server"],
          "cwd": "${workspaceFolder}/mcp/azure-operator"
        }
      }
    }
  }
}
```

2. Restart VSCode and start using:
```
@azure-operator list all AKS clusters
```

**📖 [Complete Installation Guide](./MCP_INSTALLATION_GUIDE.md)**

## 🏗️ Architecture

```
mcp/azure-operator/
├── mcp_server.py           # MCP protocol implementation
├── server_new.py           # Modular FastAPI server (REST API)
├── auth.py                 # Multi-mode Azure authentication
├── models.py               # Request/response models
├── utils.py                # Rate limiting & logging
├── app_service_tools.py    # 33 App Service tools
├── aks_tools.py            # 41 AKS/Kubernetes tools
└── best_practices_tools.py # 6 Infrastructure tools
```

## 🔐 Security

- ✅ **Approval Required:** All remediation actions need `approve: true`
- ✅ **Rate Limiting:** 10 actions per minute (configurable)
- ✅ **Audit Logging:** All actions logged with timestamp and parameters
- ✅ **Secret Masking:** Automatic masking of sensitive data
- ✅ **Least Privilege:** Use Azure RBAC for fine-grained access control

## 🔑 Authentication Modes

The server automatically detects the best authentication method:

1. **Azure CLI** (local dev): `az login`
2. **Managed Identity** (production): Auto-detected in Azure
3. **Service Principal** (automation): Set `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
4. **Test Mode**: Set `TEST_MODE=true` for testing without credentials

## 📚 Documentation

- **[Installation Guide](./MCP_INSTALLATION_GUIDE.md)** - Step-by-step setup for VSCode, Claude Desktop
- **[MCP Best Practices](./MCP_BEST_PRACTICES.md)** - How we follow MCP standards
- **[Implementation Summary](./IMPLEMENTATION_SUMMARY.md)** - Technical details
- **[App Service Tools](./mcp/azure-operator/APP_SERVICE_TOOLS_README.md)** - 33 App Service tools
- **[AKS Tools](./mcp/azure-operator/AKS_TOOLS_README.md)** - 41 AKS/K8s tools

## 🎯 Use Cases

### DevOps & SRE
- Investigate production incidents faster with AI assistance
- Automate routine operational tasks
- Check infrastructure against best practices
- Monitor resource health and performance

### Security Teams
- Audit Azure configurations for security issues
- Check compliance with security policies
- Review RBAC and network policies
- Identify untagged or misconfigured resources

### Cost Optimization
- Identify overprovisioned resources
- Check autoscaling configurations
- Review VM sizes and recommendations
- Analyze resource utilization

## 🛠️ Technology Stack

- **MCP SDK** - Model Context Protocol
- **FastAPI** - REST API framework (optional)
- **Azure SDK for Python** - Azure resource management
- **Kubernetes Python Client** - K8s operations
- **Pydantic** - Data validation

## 📋 Requirements

- **Python 3.11+**
- **Azure Subscription** with appropriate RBAC roles
- **Azure CLI** (for local development)
- **VSCode** with GitHub Copilot (for Copilot integration)
- **Claude Desktop** (for Claude integration)

## 🤝 Contributing

Contributions welcome! To add new tools:

1. Add tool definition to `mcp_server.py`
2. Implement handler in appropriate module (`app_service_tools.py`, `aks_tools.py`, etc.)
3. Add request model to `models.py`
4. Update documentation
5. Test with `python mcp_server.py`

## 📄 License

MIT License - see [LICENSE](LICENSE) for details

## 🙏 Acknowledgments

- Built following [MCP best practices](https://modelcontextprotocol.info/docs/best-practices/)
- Powered by [Azure SDK for Python](https://github.com/Azure/azure-sdk-for-python)
- Inspired by the need for better Azure operational tooling

---

**Ready to supercharge your Azure operations with AI?** 🚀

[Get Started →](./MCP_INSTALLATION_GUIDE.md) | [View Tools →](./mcp/azure-operator/README.md) | [Report Issues →](https://github.com/orshohat1/Azure-Operations-MCP/issues)