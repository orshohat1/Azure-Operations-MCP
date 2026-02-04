# Azure Operator MCP Server (v1)

**AI SRE Layer for Azure Workloads** - Observe, diagnose, and safely remediate Azure resources via Model Context Protocol (MCP).

## 🎯 Overview

Azure Operator MCP Server enables AI agents (GitHub Copilot, Foundry agents, external LLMs) to interact with Azure workloads through structured tools. Version 1 focuses on **App Service as the primary target**, while also supporting AKS and platform telemetry.

### Key Features

- ✅ **Multi-mode Azure Authentication** (CLI, Managed Identity, Service Principal)
- ✅ **Deep App Service Observability** (13+ read tools)
- ✅ **App Service Remediation Actions** (11+ action tools)
- ✅ **AKS Support** (observability + remediation)
- ✅ **Security Guardrails** (approval required, rate limiting, audit logging)
- ✅ **Azure Monitor Integration**
- ✅ **Docker & Container Apps Ready**

---

## 📋 Requirements

- **Python 3.11+**
- **Azure Subscription**
- **Azure CLI** (for local development)
- **Docker** (optional, for containerized deployment)

---

## 🚀 Quick Start

### Option 1: Local Development with Azure CLI

1. **Clone the repository**
   ```bash
   git clone https://github.com/orshohat1/Azure-Operations-MCP.git
   cd Azure-Operations-MCP/mcp/azure-operator
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Login to Azure**
   ```bash
   az login
   ```

4. **Set environment variables** (optional)
   ```bash
   cp .env.example .env
   # Edit .env to set AZURE_SUBSCRIPTION_ID and other settings
   ```

5. **Run the server**
   ```bash
   python server.py
   ```

6. **Test the server**
   ```bash
   curl http://localhost:8000/health
   ```

The server will automatically use your Azure CLI credentials via `DefaultAzureCredential`.

### Option 2: Docker Compose

1. **Navigate to the project directory**
   ```bash
   cd mcp/azure-operator
   ```

2. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

3. **Test the server**
   ```bash
   curl http://localhost:8000/health
   ```

### Option 3: Docker

1. **Build the image**
   ```bash
   docker build -t azure-operator-mcp .
   ```

2. **Run the container**
   ```bash
   docker run -p 8000:8000 \
     -e AZURE_CLIENT_ID=your-client-id \
     -e AZURE_TENANT_ID=your-tenant-id \
     -e AZURE_CLIENT_SECRET=your-secret \
     azure-operator-mcp
   ```

---

## 🔐 Authentication Modes

The server automatically selects the authentication mode based on environment variables:

### Mode A: Azure CLI Login (Local Development)
**When to use:** Local development on your machine  
**Setup:** Run `az login` before starting the server  
**Environment:** No `AZURE_CLIENT_ID` set  

```bash
az login
python server.py
```

### Mode B: Managed Identity (Production)
**When to use:** Deployed to Azure (Container Apps, App Service, AKS with workload identity)  
**Setup:** Enable System or User Assigned Managed Identity on the Azure resource  
**Environment:** Automatically detected in Azure environments  

No additional configuration needed - the server will use the managed identity automatically.

### Mode C: Service Principal (Automation/CI)
**When to use:** CI/CD pipelines, automation scripts  
**Setup:** Create a Service Principal and set environment variables  

```bash
# Create Service Principal
az ad sp create-for-rbac --name azure-operator-mcp --role Contributor

# Set environment variables
export AZURE_CLIENT_ID=<appId>
export AZURE_TENANT_ID=<tenant>
export AZURE_CLIENT_SECRET=<password>
export AZURE_SUBSCRIPTION_ID=<subscription-id>

python server.py
```

The server logs the active authentication mode at startup:
```
🔐 Authentication Mode: Azure CLI Login (local dev)
✅ Authentication successful using: Azure CLI Login (local dev)
```

---

## 🛠️ API Endpoints

### Health & Info

- `GET /` - Server information and status
- `GET /health` - Health check endpoint

### App Service - Observability (Read)

| Endpoint | Description | Required Parameters |
|----------|-------------|---------------------|
| `POST /tools/list_app_services` | List all App Services | `subscription_id` |
| `POST /tools/get_app_service_state` | Get app state (Running/Stopped) | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_config` | Get configuration and slots | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_diagnostic_settings` | Get diagnostic settings | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_container_logs` | Get container logs info | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_file_system` | List files in /home | `subscription_id`, `app_name`, `path` |
| `POST /tools/get_app_service_process_list` | Get running processes | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_memory_dump` | Get memory view | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_instance_health` | Multi-instance health | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_scaling_rules` | Get autoscale config | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_last_deploy` | Get deployment info | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_deployment_logs` | Get deployment logs | `subscription_id`, `app_name` |
| `POST /tools/get_app_service_environment_variables` | Get app settings (masked) | `subscription_id`, `app_name` |

### App Service - Remediation (Actions)

⚠️ **All actions require `approve: true` in request body**

| Endpoint | Description | Required Parameters |
|----------|-------------|---------------------|
| `POST /tools/restart_app_service` | Restart app | `subscription_id`, `app_name`, `approve` |
| `POST /tools/restart_app_service_slot` | Restart slot | `subscription_id`, `app_name`, `slot`, `approve` |
| `POST /tools/scale_app_service_plan` | Change SKU/instances | `subscription_id`, `plan_name`, `approve` |
| `POST /tools/set_app_setting` | Update app setting | `subscription_id`, `app_name`, `key`, `value`, `approve` |

### Azure Monitor & App Insights

| Endpoint | Description |
|----------|-------------|
| `POST /tools/query_app_insights` | Execute KQL query |
| `POST /tools/get_recent_exceptions` | Get exceptions |
| `POST /tools/get_dependency_failures` | Get failed dependencies |
| `POST /tools/get_slow_requests` | Get slow requests |
| `POST /tools/get_availability_tests` | Get availability tests |
| `POST /tools/get_alerts_last_24h` | Get recent alerts |

### AKS - Observability

| Endpoint | Description |
|----------|-------------|
| `POST /tools/list_aks_clusters` | List AKS clusters |
| `POST /tools/get_aks_status` | Get cluster status |
| `POST /tools/get_failing_pods` | Get failing pods |
| `POST /tools/get_pod_logs` | Get pod logs |

### AKS - Remediation

| Endpoint | Description |
|----------|-------------|
| `POST /tools/scale_aks_nodepool` | Scale nodepool |
| `POST /tools/restart_k8s_deployment` | Restart deployment |
| `POST /tools/cordon_node` | Cordon node |
| `POST /tools/uncordon_node` | Uncordon node |

---

## 📝 Usage Examples

### Example 1: List App Services

```bash
curl -X POST http://localhost:8000/tools/list_app_services \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "your-subscription-id"
  }'
```

### Example 2: Get App Service State

```bash
curl -X POST http://localhost:8000/tools/get_app_service_state \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "your-subscription-id",
    "app_name": "my-app-service"
  }'
```

### Example 3: Restart App Service (with approval)

```bash
curl -X POST http://localhost:8000/tools/restart_app_service \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "your-subscription-id",
    "app_name": "my-app-service",
    "approve": true
  }'
```

### Example 4: Update App Setting

```bash
curl -X POST http://localhost:8000/tools/set_app_setting \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "your-subscription-id",
    "app_name": "my-app-service",
    "key": "MY_SETTING",
    "value": "new-value",
    "approve": true
  }'
```

---

## 🎯 AI Agent Prompts

Example prompts for GitHub Copilot or other AI agents:

1. **"Why is my App Service slow in the last hour?"**
   - Agent uses `get_app_service_state` → `query_app_insights` → `get_slow_requests`

2. **"Find deployment failures and suggest remediation."**
   - Agent uses `get_app_service_deployment_logs` → analyzes errors → suggests `redeploy_last_release`

3. **"Restart staging slot only if unhealthy."**
   - Agent uses `get_app_service_instance_health` → conditional `restart_app_service_slot`

4. **"Check if autoscale is enabled and fix it."**
   - Agent uses `get_app_service_scaling_rules` → conditional `enable_autoscale`

5. **"Show me recent 500 errors and their root cause."**
   - Agent uses `get_recent_exceptions` → `query_app_insights` with error analysis

---

## 🔒 Security & Guardrails

### Built-in Protections

1. **Approval Required**: All modification actions require `approve: true`
2. **Rate Limiting**: Max 10 actions per minute per caller
3. **Audit Logging**: All actions logged with timestamp, params, and result
4. **Secret Masking**: Sensitive values automatically masked in responses
5. **Read-Only Default**: Server starts in read-only mode
6. **No Shell Access**: No direct command execution on resources

### Action Logging

Every action is logged to stdout (and can be configured to send to Azure Monitor):

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "action": "restart_app_service",
  "params": {"app_name": "my-app"},
  "success": true,
  "error": null,
  "auth_mode": "Azure CLI Login"
}
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file (or set environment variables):

```bash
# Azure Authentication (Service Principal - optional)
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-secret

# Default Subscription (optional)
AZURE_SUBSCRIPTION_ID=your-subscription-id

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO

# Rate Limiting
MAX_ACTIONS_PER_MINUTE=10
```

### Azure Permissions

The service principal or managed identity needs these roles:

- **Reader** (minimum for observability)
- **Contributor** (for remediation actions)
- **Monitoring Reader** (for Azure Monitor/App Insights)

Example role assignment:

```bash
az role assignment create \
  --assignee <client-id or managed-identity> \
  --role Contributor \
  --scope /subscriptions/<subscription-id>
```

---

## 🐳 Deployment to Azure Container Apps

1. **Build and push Docker image**
   ```bash
   az acr login --name myregistry
   docker build -t myregistry.azurecr.io/azure-operator-mcp:v1 .
   docker push myregistry.azurecr.io/azure-operator-mcp:v1
   ```

2. **Create Container App with Managed Identity**
   ```bash
   az containerapp create \
     --name azure-operator-mcp \
     --resource-group my-rg \
     --image myregistry.azurecr.io/azure-operator-mcp:v1 \
     --target-port 8000 \
     --ingress external \
     --environment my-env \
     --assign-system-identity
   ```

3. **Assign Contributor role to the Managed Identity**
   ```bash
   IDENTITY_ID=$(az containerapp show \
     --name azure-operator-mcp \
     --resource-group my-rg \
     --query identity.principalId -o tsv)
   
   az role assignment create \
     --assignee $IDENTITY_ID \
     --role Contributor \
     --scope /subscriptions/<subscription-id>
   ```

---

## 🧪 Testing

### Manual Testing

1. Start the server:
   ```bash
   python server.py
   ```

2. Test health endpoint:
   ```bash
   curl http://localhost:8000/health
   ```

3. Test authentication:
   ```bash
   curl -X POST http://localhost:8000/tools/list_app_services \
     -H "Content-Type: application/json" \
     -d '{"subscription_id": "your-sub-id"}'
   ```

### Docker Testing

```bash
docker-compose up --build
curl http://localhost:8000/health
```

---

## 📦 Project Structure

```
mcp/azure-operator/
├── server.py              # Main FastAPI application
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Project metadata
├── Dockerfile            # Container image definition
├── docker-compose.yml    # Local development setup
├── .env.example          # Environment variable template
└── README.md             # This file
```

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details

---

## 📞 Support

For issues or questions:
- Open an issue on GitHub
- Contact: [Azure Operator Team]

---

## 🗺️ Roadmap

### v1.0 (Current)
- ✅ Multi-mode authentication
- ✅ App Service observability (13 tools)
- ✅ App Service remediation (11 tools)
- ✅ AKS basic support
- ✅ Security guardrails

### v1.1 (Planned)
- Full Kudu API integration
- Enhanced AKS support with kubeconfig
- Azure Monitor direct integration
- Application Insights query execution
- Enhanced rate limiting per tool

### v2.0 (Future)
- Azure Functions support
- Virtual Machine operations
- Azure SQL diagnostics
- Cosmos DB operations
- Custom agent templates

---

## ⚡ Quick Reference

### Start Server (Local)
```bash
az login
python server.py
```

### Start Server (Docker)
```bash
docker-compose up
```

### Check Authentication
```bash
curl http://localhost:8000/
```

### List App Services
```bash
curl -X POST http://localhost:8000/tools/list_app_services \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": "YOUR_SUB_ID"}'
```

### Restart App (with approval)
```bash
curl -X POST http://localhost:8000/tools/restart_app_service \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": "YOUR_SUB_ID", "app_name": "myapp", "approve": true}'
```

---

**Built with ❤️ for Azure SREs and AI Agents**
