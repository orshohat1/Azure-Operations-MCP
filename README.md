# Azure Operations MCP

**Model Context Protocol (MCP) servers for Azure Operations**

This repository contains MCP servers that enable AI agents to observe, diagnose, and safely remediate Azure workloads.

## 🚀 Services

### [Azure Operator MCP Server (v1)](./mcp/azure-operator)

AI SRE layer for Azure workloads with focus on App Service operations.

**Key Features:**
- ✅ Multi-mode Azure Authentication (CLI, Managed Identity, Service Principal)
- ✅ Deep App Service Observability (13+ tools)
- ✅ App Service Remediation Actions (11+ tools)
- ✅ AKS Support
- ✅ Security Guardrails
- ✅ Docker & Container Apps Ready

**Quick Start:**
```bash
cd mcp/azure-operator
az login
python server.py
```

[📖 Full Documentation →](./mcp/azure-operator/README.md)

## 📋 Requirements

- Python 3.11+
- Azure Subscription
- Azure CLI (for local development)
- Docker (optional)

## 🤝 Contributing

Contributions welcome! Please open an issue or submit a pull request.

## 📄 License

MIT License