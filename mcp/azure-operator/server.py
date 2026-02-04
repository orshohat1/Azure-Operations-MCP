"""
Azure Operator MCP Server (v1)
AI SRE layer for Azure workloads with focus on App Service
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncio
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.monitor.query import LogsQueryClient
from azure.keyvault.secrets import SecretClient
from kubernetes import client as k8s_client, config as k8s_config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Rate limiting storage
action_history = defaultdict(list)
MAX_ACTIONS_PER_MINUTE = int(os.getenv("MAX_ACTIONS_PER_MINUTE", "10"))


class AuthManager:
    """Manages Azure authentication with multi-mode support"""
    
    def __init__(self):
        self.credential = None
        self.auth_mode = None
        self._initialize_auth()
    
    def _initialize_auth(self):
        """Initialize authentication based on environment"""
        client_id = os.getenv("AZURE_CLIENT_ID")
        tenant_id = os.getenv("AZURE_TENANT_ID")
        client_secret = os.getenv("AZURE_CLIENT_SECRET")
        test_mode = os.getenv("TEST_MODE", "false").lower() == "true"
        
        if test_mode:
            self.auth_mode = "Test Mode (No Authentication)"
            logger.warning("⚠️  Running in TEST MODE - authentication disabled")
            logger.warning("⚠️  Do not use in production!")
            self.credential = None
            return
        
        if client_id and tenant_id and client_secret:
            self.auth_mode = "Service Principal"
            logger.info("🔐 Authentication Mode: Service Principal (automation/CI)")
        elif client_id:
            self.auth_mode = "Managed Identity"
            logger.info("🔐 Authentication Mode: Managed Identity (production)")
        else:
            self.auth_mode = "Azure CLI / Developer"
            logger.info("🔐 Authentication Mode: Azure CLI Login (local dev)")
            logger.info("💡 Make sure you've run 'az login' before starting the server")
        
        try:
            self.credential = DefaultAzureCredential()
            # Test the credential
            token = self.credential.get_token("https://management.azure.com/.default")
            logger.info(f"✅ Authentication successful using: {self.auth_mode}")
        except Exception as e:
            logger.error(f"❌ Authentication failed: {str(e)}")
            raise


# Global auth manager
auth_manager = AuthManager()


def check_rate_limit(caller_id: str = "default") -> bool:
    """Check if caller has exceeded rate limit"""
    now = datetime.now()
    cutoff = now - timedelta(minutes=1)
    
    # Clean old entries
    action_history[caller_id] = [
        timestamp for timestamp in action_history[caller_id]
        if timestamp > cutoff
    ]
    
    # Check limit
    if len(action_history[caller_id]) >= MAX_ACTIONS_PER_MINUTE:
        return False
    
    action_history[caller_id].append(now)
    return True


def log_action(action_name: str, params: Dict[str, Any], success: bool, error: Optional[str] = None):
    """Log action to Azure Monitor (placeholder - would send to Log Analytics in production)"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action_name,
        "params": params,
        "success": success,
        "error": error,
        "auth_mode": auth_manager.auth_mode
    }
    logger.info(f"ACTION LOG: {log_entry}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app"""
    logger.info("🚀 Azure Operator MCP Server starting...")
    logger.info(f"📊 Rate limit: {MAX_ACTIONS_PER_MINUTE} actions per minute")
    yield
    logger.info("👋 Azure Operator MCP Server shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Azure Operator MCP Server",
    description="AI SRE layer for Azure workloads - observe, diagnose, and remediate",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# Pydantic Models for Request/Response
# ============================================================================

class BaseRequest(BaseModel):
    subscription_id: str = Field(..., description="Azure subscription ID")


class AppServiceRequest(BaseRequest):
    app_name: str = Field(..., description="App Service name")


class AppServiceSlotRequest(AppServiceRequest):
    slot: str = Field(..., description="Deployment slot name")


class AppServiceFileSystemRequest(AppServiceRequest):
    path: str = Field(default="/home", description="File system path to explore")


class AppInsightsRequest(BaseModel):
    app_insights_resource_id: str = Field(..., description="Application Insights resource ID")


class AppInsightsQueryRequest(AppInsightsRequest):
    kql_query: str = Field(..., description="KQL query to execute")


class AppInsightsTimeRangeRequest(AppInsightsRequest):
    last_hours: int = Field(default=24, description="Number of hours to look back")


class SlowRequestsRequest(AppInsightsRequest):
    p95_ms: int = Field(default=1000, description="P95 threshold in milliseconds")


class AKSRequest(BaseRequest):
    cluster_name: str = Field(..., description="AKS cluster name")


class AKSPodsRequest(AKSRequest):
    namespace: str = Field(default="default", description="Kubernetes namespace")


class AKSPodLogsRequest(AKSPodsRequest):
    pod: str = Field(..., description="Pod name")


class ActionRequest(BaseRequest):
    approve: bool = Field(..., description="Must be true to execute action")


class RestartAppServiceRequest(AppServiceRequest, ActionRequest):
    pass


class RestartAppServiceSlotRequest(AppServiceSlotRequest, ActionRequest):
    pass


class ScaleAppServicePlanRequest(ActionRequest):
    plan_name: str = Field(..., description="App Service Plan name")
    sku: Optional[str] = Field(None, description="SKU tier (e.g., 'B1', 'P1V2')")
    instances: Optional[int] = Field(None, description="Number of instances")


class SetAppSettingRequest(AppServiceRequest, ActionRequest):
    key: str = Field(..., description="Setting key")
    value: str = Field(..., description="Setting value")


class ScaleAKSNodepoolRequest(AKSRequest, ActionRequest):
    nodepool_name: str = Field(..., description="Nodepool name")
    min_count: Optional[int] = Field(None, description="Minimum node count")
    max_count: Optional[int] = Field(None, description="Maximum node count")


class RestartK8sDeploymentRequest(AKSPodsRequest, ActionRequest):
    deployment: str = Field(..., description="Deployment name")


class CordonNodeRequest(AKSRequest, ActionRequest):
    node_name: str = Field(..., description="Node name to cordon")


class RotateKeyVaultSecretRequest(ActionRequest):
    vault_name: str = Field(..., description="Key Vault name")
    secret_name: str = Field(..., description="Secret name")


class TriggerGitHubWorkflowRequest(ActionRequest):
    repo_owner: str = Field(..., description="GitHub repository owner")
    repo_name: str = Field(..., description="GitHub repository name")
    workflow_id: str = Field(..., description="Workflow ID or filename")
    ref: str = Field(default="main", description="Git ref to run workflow on")


class EnableDetailedErrorLogsRequest(AppServiceRequest, ActionRequest):
    pass


class ClearAppServiceCacheRequest(AppServiceRequest, ActionRequest):
    pass


class RedeployLastReleaseRequest(AppServiceRequest, ActionRequest):
    pass


class SwapSlotsRequest(AppServiceRequest, ActionRequest):
    pass


class ResetAppServiceCredentialsRequest(AppServiceRequest, ActionRequest):
    pass


class EnableAutoscaleRequest(ActionRequest):
    plan_name: str = Field(..., description="App Service Plan name")


class DisableAutoscaleRequest(ActionRequest):
    plan_name: str = Field(..., description="App Service Plan name")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with server info"""
    return {
        "service": "Azure Operator MCP Server",
        "version": "1.0.0",
        "auth_mode": auth_manager.auth_mode,
        "status": "operational"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "auth_mode": auth_manager.auth_mode}


# ============================================================================
# App Service - Observability Tools
# ============================================================================

@app.post("/tools/list_app_services")
async def list_app_services(request: BaseRequest):
    """List all App Services in a subscription"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        apps = []
        for app in client.web_apps.list():
            apps.append({
                "name": app.name,
                "resource_group": app.resource_group,
                "location": app.location,
                "state": app.state,
                "default_host_name": app.default_host_name,
                "enabled": app.enabled
            })
        return {"app_services": apps, "count": len(apps)}
    except Exception as e:
        logger.error(f"Error listing app services: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_state")
async def get_app_service_state(request: AppServiceRequest):
    """Get the current state of an App Service"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find the resource group for the app
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        app = client.web_apps.get(resource_group, request.app_name)
        
        return {
            "name": app.name,
            "state": app.state,
            "enabled": app.enabled,
            "availability_state": app.availability_state,
            "usage_state": app.usage_state,
            "last_modified_time": app.last_modified_time_utc.isoformat() if app.last_modified_time_utc else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting app service state: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_config")
async def get_app_service_config(request: AppServiceRequest):
    """Get App Service configuration including app settings and deployment slots"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        app = client.web_apps.get(resource_group, request.app_name)
        config = client.web_apps.get_configuration(resource_group, request.app_name)
        
        # Get deployment slots
        slots = []
        try:
            for slot in client.web_apps.list_slots(resource_group, request.app_name):
                slots.append(slot.name.split('/')[-1])
        except:
            pass
        
        return {
            "name": app.name,
            "runtime_stack": config.linux_fx_version or config.windows_fx_version,
            "always_on": config.always_on,
            "http20_enabled": config.http20_enabled,
            "min_tls_version": config.min_tls_version,
            "ftps_state": config.ftps_state,
            "deployment_slots": slots,
            "app_command_line": config.app_command_line,
            "number_of_workers": config.number_of_workers
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting app service config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_diagnostic_settings")
async def get_app_service_diagnostic_settings(request: AppServiceRequest):
    """Get diagnostic settings for an App Service"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        app_id = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                app_id = app.id
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get diagnostic settings using Monitor client
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
        try:
            diagnostic_settings = []
            for setting in monitor_client.diagnostic_settings.list(app_id):
                diagnostic_settings.append({
                    "name": setting.name,
                    "storage_account_id": setting.storage_account_id,
                    "workspace_id": setting.workspace_id,
                    "event_hub_authorization_rule_id": setting.event_hub_authorization_rule_id,
                    "logs_enabled": len(setting.logs) > 0 if setting.logs else False,
                    "metrics_enabled": len(setting.metrics) > 0 if setting.metrics else False
                })
            
            return {
                "app_name": request.app_name,
                "diagnostic_settings": diagnostic_settings
            }
        except:
            return {
                "app_name": request.app_name,
                "diagnostic_settings": [],
                "note": "No diagnostic settings configured or unable to retrieve"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting diagnostic settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_container_logs")
async def get_app_service_container_logs(request: AppServiceRequest):
    """Get recent container logs (stdout/stderr) for an App Service"""
    try:
        return {
            "app_name": request.app_name,
            "note": "Container logs can be retrieved via Kudu API or Log Analytics",
            "recommendation": "Use get_app_service_diagnostic_settings to see where logs are sent",
            "kudu_url": f"https://{request.app_name}.scm.azurewebsites.net/api/logs/docker"
        }
    except Exception as e:
        logger.error(f"Error getting container logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_file_system")
async def get_app_service_file_system(request: AppServiceFileSystemRequest):
    """List files in App Service file system"""
    try:
        return {
            "app_name": request.app_name,
            "path": request.path,
            "note": "File system access requires Kudu API",
            "kudu_url": f"https://{request.app_name}.scm.azurewebsites.net/api/vfs{request.path}",
            "recommendation": "Access Kudu REST API with deployment credentials"
        }
    except Exception as e:
        logger.error(f"Error accessing file system: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_process_list")
async def get_app_service_process_list(request: AppServiceRequest):
    """Get running processes in an App Service"""
    try:
        return {
            "app_name": request.app_name,
            "note": "Process list requires Kudu API",
            "kudu_url": f"https://{request.app_name}.scm.azurewebsites.net/api/processes",
            "recommendation": "Use Kudu REST API to get detailed process information"
        }
    except Exception as e:
        logger.error(f"Error getting process list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_memory_dump")
async def get_app_service_memory_dump(request: AppServiceRequest):
    """Get high-level memory view for an App Service"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get usage metrics
        app = client.web_apps.get(resource_group, request.app_name)
        
        return {
            "app_name": request.app_name,
            "note": "Memory metrics available via Azure Monitor",
            "recommendation": "Use query_app_insights or Azure Monitor for detailed memory metrics",
            "app_service_plan": app.server_farm_id.split('/')[-1] if app.server_farm_id else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting memory dump: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_instance_health")
async def get_app_service_instance_health(request: AppServiceRequest):
    """Get health status of all instances in a multi-instance App Service"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get instance info
        instances = []
        try:
            for instance in client.web_apps.list_instance_identifiers(resource_group, request.app_name):
                instances.append({
                    "instance_id": instance.name,
                    "state": "Running"  # Simplified - would need more API calls for actual state
                })
        except:
            pass
        
        return {
            "app_name": request.app_name,
            "instances": instances,
            "instance_count": len(instances)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting instance health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_scaling_rules")
async def get_app_service_scaling_rules(request: AppServiceRequest):
    """Get autoscale configuration for an App Service"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group and plan
        resource_group = None
        plan_id = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                plan_id = app.server_farm_id
                break
        
        if not resource_group or not plan_id:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get autoscale settings via Monitor client
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
        autoscale_settings = []
        try:
            for setting in monitor_client.autoscale_settings.list_by_resource_group(resource_group):
                if setting.target_resource_uri and plan_id in setting.target_resource_uri:
                    autoscale_settings.append({
                        "name": setting.name,
                        "enabled": setting.enabled,
                        "profiles": [
                            {
                                "name": profile.name,
                                "min_capacity": profile.capacity.minimum,
                                "max_capacity": profile.capacity.maximum,
                                "default_capacity": profile.capacity.default
                            }
                            for profile in setting.profiles
                        ] if setting.profiles else []
                    })
        except:
            pass
        
        return {
            "app_name": request.app_name,
            "autoscale_settings": autoscale_settings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting scaling rules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_last_deploy")
async def get_app_service_last_deploy(request: AppServiceRequest):
    """Get last deployment information"""
    try:
        return {
            "app_name": request.app_name,
            "note": "Deployment info available via Kudu API",
            "kudu_url": f"https://{request.app_name}.scm.azurewebsites.net/api/deployments",
            "recommendation": "Use Kudu REST API for deployment history"
        }
    except Exception as e:
        logger.error(f"Error getting last deploy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_deployment_logs")
async def get_app_service_deployment_logs(request: AppServiceRequest):
    """Get deployment failure logs"""
    try:
        return {
            "app_name": request.app_name,
            "note": "Deployment logs available via Kudu API",
            "kudu_url": f"https://{request.app_name}.scm.azurewebsites.net/api/deployments",
            "recommendation": "Use Kudu REST API to retrieve deployment logs"
        }
    except Exception as e:
        logger.error(f"Error getting deployment logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_app_service_environment_variables")
async def get_app_service_environment_variables(request: AppServiceRequest):
    """Get environment variables and app settings (secrets masked)"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get app settings
        settings = client.web_apps.list_application_settings(resource_group, request.app_name)
        
        # Mask sensitive values
        masked_settings = {}
        for key, value in settings.properties.items():
            if any(secret_keyword in key.lower() for secret_keyword in ['password', 'secret', 'key', 'token', 'connection']):
                masked_settings[key] = "***MASKED***"
            else:
                masked_settings[key] = value
        
        return {
            "app_name": request.app_name,
            "settings": masked_settings,
            "note": "Sensitive values are masked for security"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting environment variables: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Azure Monitor & App Insights Tools
# ============================================================================

@app.post("/tools/query_app_insights")
async def query_app_insights(request: AppInsightsQueryRequest):
    """Execute a KQL query against Application Insights"""
    try:
        # Note: Requires workspace ID from resource ID
        return {
            "note": "Application Insights queries require LogsQueryClient",
            "kql_query": request.kql_query,
            "recommendation": "Use Azure Monitor Query API with workspace ID"
        }
    except Exception as e:
        logger.error(f"Error querying App Insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_recent_exceptions")
async def get_recent_exceptions(request: AppInsightsTimeRangeRequest):
    """Get recent exceptions from Application Insights"""
    try:
        return {
            "note": "Exceptions can be queried via Application Insights API",
            "sample_kql": f"exceptions | where timestamp > ago({request.last_hours}h) | summarize count() by type, outerMessage",
            "recommendation": "Use query_app_insights with the sample KQL query"
        }
    except Exception as e:
        logger.error(f"Error getting exceptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_dependency_failures")
async def get_dependency_failures(request: AppInsightsTimeRangeRequest):
    """Get dependency call failures"""
    try:
        return {
            "note": "Dependency failures available via Application Insights",
            "sample_kql": f"dependencies | where timestamp > ago({request.last_hours}h) and success == false | summarize count() by name, resultCode",
            "recommendation": "Use query_app_insights with the sample KQL query"
        }
    except Exception as e:
        logger.error(f"Error getting dependency failures: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_slow_requests")
async def get_slow_requests(request: SlowRequestsRequest):
    """Get slow requests above P95 threshold"""
    try:
        return {
            "note": "Slow requests available via Application Insights",
            "sample_kql": f"requests | summarize percentile(duration, 95) by name | where percentile_duration_95 > {request.p95_ms}",
            "recommendation": "Use query_app_insights with the sample KQL query"
        }
    except Exception as e:
        logger.error(f"Error getting slow requests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_availability_tests")
async def get_availability_tests(request: AppInsightsRequest):
    """Get availability test results"""
    try:
        return {
            "note": "Availability tests can be retrieved via Application Insights API",
            "recommendation": "Use Azure Monitor API to list availability tests"
        }
    except Exception as e:
        logger.error(f"Error getting availability tests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_alerts_last_24h")
async def get_alerts_last_24h(request: BaseRequest):
    """Get alerts fired in the last 24 hours"""
    try:
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
        alerts = []
        try:
            # Get activity log alerts
            for alert in monitor_client.activity_log_alerts.list_by_subscription_id():
                alerts.append({
                    "name": alert.name,
                    "enabled": alert.enabled,
                    "description": alert.description,
                    "type": "ActivityLog"
                })
        except:
            pass
        
        return {
            "alerts": alerts,
            "note": "Alert history requires Activity Log or Alert History API"
        }
    except Exception as e:
        logger.error(f"Error getting alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AKS - Observability Tools
# ============================================================================

@app.post("/tools/list_aks_clusters")
async def list_aks_clusters(request: BaseRequest):
    """List all AKS clusters in a subscription"""
    try:
        client = ContainerServiceClient(auth_manager.credential, request.subscription_id)
        clusters = []
        for cluster in client.managed_clusters.list():
            clusters.append({
                "name": cluster.name,
                "resource_group": cluster.id.split('/')[4],
                "location": cluster.location,
                "kubernetes_version": cluster.kubernetes_version,
                "provisioning_state": cluster.provisioning_state,
                "fqdn": cluster.fqdn
            })
        return {"clusters": clusters, "count": len(clusters)}
    except Exception as e:
        logger.error(f"Error listing AKS clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_status")
async def get_aks_status(request: AKSRequest):
    """Get AKS cluster status"""
    try:
        client = ContainerServiceClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for cluster in client.managed_clusters.list():
            if cluster.name == request.cluster_name:
                resource_group = cluster.id.split('/')[4]
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"AKS cluster '{request.cluster_name}' not found")
        
        cluster = client.managed_clusters.get(resource_group, request.cluster_name)
        
        return {
            "name": cluster.name,
            "provisioning_state": cluster.provisioning_state,
            "power_state": cluster.power_state.code if cluster.power_state else "Unknown",
            "kubernetes_version": cluster.kubernetes_version,
            "node_resource_group": cluster.node_resource_group,
            "agent_pool_profiles": [
                {
                    "name": profile.name,
                    "count": profile.count,
                    "vm_size": profile.vm_size,
                    "provisioning_state": profile.provisioning_state
                }
                for profile in cluster.agent_pool_profiles
            ] if cluster.agent_pool_profiles else []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AKS status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_failing_pods")
async def get_failing_pods(request: AKSPodsRequest):
    """Get failing pods in an AKS cluster"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client with cluster credentials"
        }
    except Exception as e:
        logger.error(f"Error getting failing pods: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_pod_logs")
async def get_pod_logs(request: AKSPodLogsRequest):
    """Get logs from a specific pod"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "pod": request.pod,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to fetch pod logs"
        }
    except Exception as e:
        logger.error(f"Error getting pod logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# App Service - Remediation Actions
# ============================================================================

@app.post("/tools/restart_app_service")
async def restart_app_service(request: RestartAppServiceRequest):
    """Restart an App Service (requires approval)"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Restart the app
        client.web_apps.restart(resource_group, request.app_name)
        
        log_action("restart_app_service", {"app_name": request.app_name}, True)
        
        return {
            "status": "success",
            "message": f"App Service '{request.app_name}' restart initiated",
            "app_name": request.app_name
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("restart_app_service", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error restarting app service: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/restart_app_service_slot")
async def restart_app_service_slot(request: RestartAppServiceSlotRequest):
    """Restart a specific App Service deployment slot (requires approval)"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Restart the slot
        client.web_apps.restart_slot(resource_group, request.app_name, request.slot)
        
        log_action("restart_app_service_slot", {"app_name": request.app_name, "slot": request.slot}, True)
        
        return {
            "status": "success",
            "message": f"App Service slot '{request.slot}' restart initiated",
            "app_name": request.app_name,
            "slot": request.slot
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("restart_app_service_slot", {"app_name": request.app_name, "slot": request.slot}, False, str(e))
        logger.error(f"Error restarting app service slot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/scale_app_service_plan")
async def scale_app_service_plan(request: ScaleAppServicePlanRequest):
    """Scale App Service Plan (change SKU or instance count)"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Scaling App Service Plan requires additional implementation",
            "plan_name": request.plan_name,
            "note": "Use Azure SDK to update App Service Plan SKU and capacity"
        }
    except Exception as e:
        log_action("scale_app_service_plan", {"plan_name": request.plan_name}, False, str(e))
        logger.error(f"Error scaling app service plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/enable_detailed_error_logs")
async def enable_detailed_error_logs(request: EnableDetailedErrorLogsRequest):
    """Enable detailed error logging for an App Service"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Enable detailed error logs requires configuration update",
            "app_name": request.app_name,
            "note": "Use Azure SDK to update site config with detailed errors enabled"
        }
    except Exception as e:
        log_action("enable_detailed_error_logs", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error enabling detailed error logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/clear_app_service_cache")
async def clear_app_service_cache(request: ClearAppServiceCacheRequest):
    """Clear temporary cache for an App Service"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Clear cache requires Kudu API access",
            "app_name": request.app_name,
            "note": "Use Kudu REST API to clear cache directories"
        }
    except Exception as e:
        log_action("clear_app_service_cache", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error clearing cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/redeploy_last_release")
async def redeploy_last_release(request: RedeployLastReleaseRequest):
    """Redeploy the last successful release"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Redeployment requires deployment API access",
            "app_name": request.app_name,
            "note": "Use Azure DevOps or GitHub Actions API to trigger redeployment"
        }
    except Exception as e:
        log_action("redeploy_last_release", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error redeploying: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/swap_slots")
async def swap_slots(request: SwapSlotsRequest):
    """Swap staging slot with production"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        return {
            "status": "not_implemented",
            "message": "Slot swapping requires additional parameters",
            "app_name": request.app_name,
            "note": "Use client.web_apps.swap_slot with source and target slots"
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("swap_slots", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error swapping slots: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/reset_app_service_credentials")
async def reset_app_service_credentials(request: ResetAppServiceCredentialsRequest):
    """Reset publishing credentials for an App Service"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Credential reset requires publishing profile API",
            "app_name": request.app_name,
            "note": "Use Azure SDK to reset publishing profile"
        }
    except Exception as e:
        log_action("reset_app_service_credentials", {"app_name": request.app_name}, False, str(e))
        logger.error(f"Error resetting credentials: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/set_app_setting")
async def set_app_setting(request: SetAppSettingRequest):
    """Set or update an app setting"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group
        resource_group = None
        for app in client.web_apps.list():
            if app.name == request.app_name:
                resource_group = app.resource_group
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"App Service '{request.app_name}' not found")
        
        # Get current settings
        settings = client.web_apps.list_application_settings(resource_group, request.app_name)
        
        # Update the setting
        settings.properties[request.key] = request.value
        
        # Apply settings
        client.web_apps.update_application_settings(resource_group, request.app_name, settings)
        
        log_action("set_app_setting", {"app_name": request.app_name, "key": request.key}, True)
        
        return {
            "status": "success",
            "message": f"App setting '{request.key}' updated",
            "app_name": request.app_name,
            "key": request.key
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("set_app_setting", {"app_name": request.app_name, "key": request.key}, False, str(e))
        logger.error(f"Error setting app setting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/enable_autoscale")
async def enable_autoscale(request: EnableAutoscaleRequest):
    """Enable autoscaling for an App Service Plan"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Autoscale configuration requires Monitor API",
            "plan_name": request.plan_name,
            "note": "Use MonitorManagementClient to create autoscale settings"
        }
    except Exception as e:
        log_action("enable_autoscale", {"plan_name": request.plan_name}, False, str(e))
        logger.error(f"Error enabling autoscale: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/disable_autoscale")
async def disable_autoscale(request: DisableAutoscaleRequest):
    """Disable autoscaling for an App Service Plan"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Autoscale configuration requires Monitor API",
            "plan_name": request.plan_name,
            "note": "Use MonitorManagementClient to disable autoscale settings"
        }
    except Exception as e:
        log_action("disable_autoscale", {"plan_name": request.plan_name}, False, str(e))
        logger.error(f"Error disabling autoscale: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AKS - Remediation Actions
# ============================================================================

@app.post("/tools/scale_aks_nodepool")
async def scale_aks_nodepool(request: ScaleAKSNodepoolRequest):
    """Scale an AKS nodepool"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "AKS nodepool scaling requires Container Service API",
            "cluster_name": request.cluster_name,
            "nodepool_name": request.nodepool_name,
            "note": "Use ContainerServiceClient to update nodepool configuration"
        }
    except Exception as e:
        log_action("scale_aks_nodepool", {"cluster": request.cluster_name, "nodepool": request.nodepool_name}, False, str(e))
        logger.error(f"Error scaling AKS nodepool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/restart_k8s_deployment")
async def restart_k8s_deployment(request: RestartK8sDeploymentRequest):
    """Restart a Kubernetes deployment"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Kubernetes deployment restart requires kubeconfig",
            "cluster_name": request.cluster_name,
            "deployment": request.deployment,
            "note": "Use kubernetes client to perform rollout restart"
        }
    except Exception as e:
        log_action("restart_k8s_deployment", {"cluster": request.cluster_name, "deployment": request.deployment}, False, str(e))
        logger.error(f"Error restarting deployment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/cordon_node")
async def cordon_node(request: CordonNodeRequest):
    """Cordon (drain) a Kubernetes node"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Node cordoning requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "node_name": request.node_name,
            "note": "Use kubernetes client to cordon node"
        }
    except Exception as e:
        log_action("cordon_node", {"cluster": request.cluster_name, "node": request.node_name}, False, str(e))
        logger.error(f"Error cordoning node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/uncordon_node")
async def uncordon_node(request: CordonNodeRequest):
    """Uncordon a Kubernetes node"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Node uncordoning requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "node_name": request.node_name,
            "note": "Use kubernetes client to uncordon node"
        }
    except Exception as e:
        log_action("uncordon_node", {"cluster": request.cluster_name, "node": request.node_name}, False, str(e))
        logger.error(f"Error uncordoning node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Secrets & CI Actions
# ============================================================================

@app.post("/tools/rotate_keyvault_secret")
async def rotate_keyvault_secret(request: RotateKeyVaultSecretRequest):
    """Rotate a Key Vault secret"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "Secret rotation requires Key Vault client and rotation logic",
            "vault_name": request.vault_name,
            "secret_name": request.secret_name,
            "note": "Use azure-keyvault-secrets client to rotate secret"
        }
    except Exception as e:
        log_action("rotate_keyvault_secret", {"vault": request.vault_name, "secret": request.secret_name}, False, str(e))
        logger.error(f"Error rotating secret: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/trigger_github_workflow")
async def trigger_github_workflow(request: TriggerGitHubWorkflowRequest):
    """Trigger a GitHub Actions workflow"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        return {
            "status": "not_implemented",
            "message": "GitHub workflow triggering requires GitHub API token",
            "repo": f"{request.repo_owner}/{request.repo_name}",
            "workflow_id": request.workflow_id,
            "note": "Use GitHub REST API to trigger workflow dispatch"
        }
    except Exception as e:
        log_action("trigger_github_workflow", {"repo": f"{request.repo_owner}/{request.repo_name}"}, False, str(e))
        logger.error(f"Error triggering workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    
    logger.info(f"Starting Azure Operator MCP Server on {host}:{port}")
    
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=False,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
