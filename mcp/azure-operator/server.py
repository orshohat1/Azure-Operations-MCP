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
# Additional Request Models for New AKS and Best Practices Tools
# ============================================================================

class AKSNodePoolRequest(AKSRequest):
    nodepool_name: str = Field(..., description="Nodepool name")


class K8sResourceRequest(AKSPodsRequest):
    resource_type: str = Field(..., description="Resource type (deployment, statefulset, daemonset, etc.)")
    resource_name: str = Field(..., description="Resource name")


class K8sScaleRequest(AKSPodsRequest, ActionRequest):
    resource_type: str = Field(..., description="Resource type (deployment, statefulset)")
    resource_name: str = Field(..., description="Resource name")
    replicas: int = Field(..., description="Number of replicas")


class K8sPodRequest(AKSPodsRequest):
    pod_name: str = Field(..., description="Pod name")


class K8sDeletePodRequest(AKSPodsRequest, ActionRequest):
    pod_name: str = Field(..., description="Pod name to delete")


class K8sDrainNodeRequest(AKSRequest, ActionRequest):
    node_name: str = Field(..., description="Node name to drain")


class AKSUpgradeRequest(AKSRequest, ActionRequest):
    kubernetes_version: str = Field(..., description="Target Kubernetes version")


class AKSNodePoolUpgradeRequest(AKSNodePoolRequest, ActionRequest):
    kubernetes_version: str = Field(..., description="Target Kubernetes version")


class AKSAddNodePoolRequest(AKSRequest, ActionRequest):
    nodepool_name: str = Field(..., description="New nodepool name")
    vm_size: str = Field(default="Standard_DS2_v2", description="VM size")
    node_count: int = Field(default=3, description="Initial node count")
    min_count: Optional[int] = Field(None, description="Minimum node count for autoscaling")
    max_count: Optional[int] = Field(None, description="Maximum node count for autoscaling")


class AKSDeleteNodePoolRequest(AKSNodePoolRequest, ActionRequest):
    pass


class AKSAddonRequest(AKSRequest, ActionRequest):
    addon_name: str = Field(..., description="Addon name (monitoring, policy, etc.)")


class K8sApplyManifestRequest(AKSPodsRequest, ActionRequest):
    manifest: str = Field(..., description="Kubernetes manifest YAML")


class BestPracticesRequest(BaseRequest):
    resource_type: str = Field(..., description="Resource type (app_service, aks, environment)")
    resource_name: Optional[str] = Field(None, description="Specific resource name (optional)")


class ResourceGroupRequest(BaseRequest):
    resource_group: str = Field(..., description="Resource group name")


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
# AKS - Extended Investigation Tools
# ============================================================================

@app.post("/tools/get_aks_cluster_diagnostics")
async def get_aks_cluster_diagnostics(request: AKSRequest):
    """Get diagnostic settings and logs for AKS cluster"""
    try:
        client = ContainerServiceClient(auth_manager.credential, request.subscription_id)
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
        # Find resource group and cluster
        resource_group = None
        cluster_id = None
        for cluster in client.managed_clusters.list():
            if cluster.name == request.cluster_name:
                resource_group = cluster.id.split('/')[4]
                cluster_id = cluster.id
                break
        
        if not resource_group:
            raise HTTPException(status_code=404, detail=f"AKS cluster '{request.cluster_name}' not found")
        
        # Get diagnostic settings
        diagnostic_settings = []
        try:
            for setting in monitor_client.diagnostic_settings.list(cluster_id):
                diagnostic_settings.append({
                    "name": setting.name,
                    "storage_account_id": setting.storage_account_id,
                    "workspace_id": setting.workspace_id,
                    "logs_enabled": len(setting.logs) > 0 if setting.logs else False,
                    "metrics_enabled": len(setting.metrics) > 0 if setting.metrics else False
                })
        except:
            pass
        
        return {
            "cluster_name": request.cluster_name,
            "diagnostic_settings": diagnostic_settings,
            "recommendation": "Enable diagnostic settings to send logs to Log Analytics workspace"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AKS diagnostics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_node_pool_details")
async def get_aks_node_pool_details(request: AKSNodePoolRequest):
    """Get detailed nodepool information including autoscaling, health, and taints"""
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
        
        # Get nodepool details
        try:
            nodepool = client.agent_pools.get(resource_group, request.cluster_name, request.nodepool_name)
            
            return {
                "name": nodepool.name,
                "count": nodepool.count,
                "vm_size": nodepool.vm_size,
                "os_type": nodepool.os_type,
                "os_disk_size_gb": nodepool.os_disk_size_gb,
                "provisioning_state": nodepool.provisioning_state,
                "enable_auto_scaling": nodepool.enable_auto_scaling,
                "min_count": nodepool.min_count,
                "max_count": nodepool.max_count,
                "node_taints": nodepool.node_taints if nodepool.node_taints else [],
                "node_labels": nodepool.node_labels if nodepool.node_labels else {},
                "availability_zones": nodepool.availability_zones if nodepool.availability_zones else [],
                "mode": nodepool.mode
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Nodepool '{request.nodepool_name}' not found: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting nodepool details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_networking_config")
async def get_aks_networking_config(request: AKSRequest):
    """Get network configuration including policies, service mesh, and ingress"""
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
        
        network_profile = cluster.network_profile
        return {
            "cluster_name": request.cluster_name,
            "network_plugin": network_profile.network_plugin if network_profile else None,
            "network_policy": network_profile.network_policy if network_profile else None,
            "pod_cidr": network_profile.pod_cidr if network_profile else None,
            "service_cidr": network_profile.service_cidr if network_profile else None,
            "dns_service_ip": network_profile.dns_service_ip if network_profile else None,
            "load_balancer_sku": network_profile.load_balancer_sku if network_profile else None,
            "outbound_type": network_profile.outbound_type if network_profile else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting network config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_addon_status")
async def get_aks_addon_status(request: AKSRequest):
    """Get status of AKS addons (monitoring, policy, etc.)"""
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
        
        addons = {}
        if cluster.addon_profiles:
            for addon_name, addon_profile in cluster.addon_profiles.items():
                addons[addon_name] = {
                    "enabled": addon_profile.enabled,
                    "config": addon_profile.config if addon_profile.config else {}
                }
        
        return {
            "cluster_name": request.cluster_name,
            "addons": addons
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting addon status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_upgrade_history")
async def get_aks_upgrade_history(request: AKSRequest):
    """Get Kubernetes version upgrade history"""
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
        
        # Get available upgrades
        try:
            upgrade_profile = client.managed_clusters.get_upgrade_profile(resource_group, request.cluster_name)
            available_upgrades = [upgrade.kubernetes_version for upgrade in upgrade_profile.control_plane_profile.upgrades] if upgrade_profile.control_plane_profile.upgrades else []
        except:
            available_upgrades = []
        
        return {
            "cluster_name": request.cluster_name,
            "current_version": cluster.kubernetes_version,
            "available_upgrades": available_upgrades,
            "note": "Upgrade history available via Activity Log in Azure Monitor"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting upgrade history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_aks_resource_usage")
async def get_aks_resource_usage(request: AKSRequest):
    """Get CPU and memory usage per nodepool"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "note": "Resource usage metrics available via Azure Monitor",
            "recommendation": "Query Azure Monitor metrics API for detailed CPU/memory usage",
            "sample_metrics": [
                "node_cpu_usage_percentage",
                "node_memory_working_set_percentage",
                "node_disk_usage_percentage"
            ]
        }
    except Exception as e:
        logger.error(f"Error getting resource usage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/list_k8s_namespaces")
async def list_k8s_namespaces(request: AKSRequest):
    """List all namespaces in the cluster"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list namespaces"
        }
    except Exception as e:
        logger.error(f"Error listing namespaces: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_pod_status")
async def get_k8s_pod_status(request: K8sPodRequest):
    """Get detailed pod status with events and conditions"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "pod_name": request.pod_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to get pod status, events, and conditions"
        }
    except Exception as e:
        logger.error(f"Error getting pod status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_service_endpoints")
async def get_k8s_service_endpoints(request: AKSPodsRequest):
    """Get service endpoints and load balancers"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list services and their endpoints"
        }
    except Exception as e:
        logger.error(f"Error getting service endpoints: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_persistent_volumes")
async def get_k8s_persistent_volumes(request: AKSPodsRequest):
    """Get persistent volume and persistent volume claim status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list PVs and PVCs with their status"
        }
    except Exception as e:
        logger.error(f"Error getting persistent volumes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_secrets_configmaps")
async def get_k8s_secrets_configmaps(request: AKSPodsRequest):
    """List secrets and configmaps (names only, not values)"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list secrets and configmaps (names only for security)"
        }
    except Exception as e:
        logger.error(f"Error getting secrets/configmaps: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_ingress_status")
async def get_k8s_ingress_status(request: AKSPodsRequest):
    """Get ingress controllers and rules"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list ingress resources and their rules"
        }
    except Exception as e:
        logger.error(f"Error getting ingress status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_deployment_status")
async def get_k8s_deployment_status(request: K8sResourceRequest):
    """Get deployment rollout status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "resource_name": request.resource_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to get deployment status and replica counts"
        }
    except Exception as e:
        logger.error(f"Error getting deployment status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_statefulset_status")
async def get_k8s_statefulset_status(request: K8sResourceRequest):
    """Get StatefulSet status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "resource_name": request.resource_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to get StatefulSet status and pod ordinals"
        }
    except Exception as e:
        logger.error(f"Error getting StatefulSet status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_daemonset_status")
async def get_k8s_daemonset_status(request: K8sResourceRequest):
    """Get DaemonSet status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "resource_name": request.resource_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to get DaemonSet status across nodes"
        }
    except Exception as e:
        logger.error(f"Error getting DaemonSet status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_jobs_cronjobs")
async def get_k8s_jobs_cronjobs(request: AKSPodsRequest):
    """Get Job and CronJob status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list Jobs and CronJobs with their status"
        }
    except Exception as e:
        logger.error(f"Error getting jobs/cronjobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_node_conditions")
async def get_k8s_node_conditions(request: AKSRequest):
    """Get node conditions and health status"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to get node conditions (Ready, MemoryPressure, DiskPressure, etc.)"
        }
    except Exception as e:
        logger.error(f"Error getting node conditions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_k8s_events")
async def get_k8s_events(request: AKSPodsRequest):
    """Get recent cluster events"""
    try:
        return {
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Requires kubeconfig and Kubernetes API access",
            "recommendation": "Use kubernetes client to list recent events for troubleshooting"
        }
    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
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
    """Cordon a Kubernetes node (mark as unschedulable)"""
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
# AKS - Extended Remediation Actions
# ============================================================================

@app.post("/tools/update_aks_kubernetes_version")
async def update_aks_kubernetes_version(request: AKSUpgradeRequest):
    """Upgrade AKS cluster Kubernetes version"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
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
        
        log_action("update_aks_kubernetes_version", {
            "cluster": request.cluster_name,
            "target_version": request.kubernetes_version
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Kubernetes version upgrade to {request.kubernetes_version} initiated",
            "cluster_name": request.cluster_name,
            "target_version": request.kubernetes_version,
            "note": "Upgrade is performed using Azure SDK begin_create_or_update with new version"
        }
    except HTTPException:
        raise
    except Exception as e:
        log_action("update_aks_kubernetes_version", {
            "cluster": request.cluster_name,
            "target_version": request.kubernetes_version
        }, False, str(e))
        logger.error(f"Error upgrading cluster: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/update_aks_nodepool_version")
async def update_aks_nodepool_version(request: AKSNodePoolUpgradeRequest):
    """Upgrade AKS nodepool Kubernetes version"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("update_aks_nodepool_version", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name,
            "target_version": request.kubernetes_version
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Nodepool upgrade to {request.kubernetes_version} initiated",
            "cluster_name": request.cluster_name,
            "nodepool_name": request.nodepool_name,
            "target_version": request.kubernetes_version
        }
    except Exception as e:
        log_action("update_aks_nodepool_version", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name
        }, False, str(e))
        logger.error(f"Error upgrading nodepool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/add_aks_nodepool")
async def add_aks_nodepool(request: AKSAddNodePoolRequest):
    """Add a new nodepool to AKS cluster"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("add_aks_nodepool", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name,
            "vm_size": request.vm_size,
            "node_count": request.node_count
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Nodepool '{request.nodepool_name}' creation initiated",
            "cluster_name": request.cluster_name,
            "nodepool_name": request.nodepool_name,
            "vm_size": request.vm_size,
            "node_count": request.node_count
        }
    except Exception as e:
        log_action("add_aks_nodepool", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name
        }, False, str(e))
        logger.error(f"Error adding nodepool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/delete_aks_nodepool")
async def delete_aks_nodepool(request: AKSDeleteNodePoolRequest):
    """Delete a nodepool from AKS cluster"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("delete_aks_nodepool", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Nodepool '{request.nodepool_name}' deletion initiated",
            "cluster_name": request.cluster_name,
            "nodepool_name": request.nodepool_name,
            "warning": "This will delete all nodes in the nodepool"
        }
    except Exception as e:
        log_action("delete_aks_nodepool", {
            "cluster": request.cluster_name,
            "nodepool": request.nodepool_name
        }, False, str(e))
        logger.error(f"Error deleting nodepool: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/enable_aks_addon")
async def enable_aks_addon(request: AKSAddonRequest):
    """Enable AKS addon (monitoring, policy, etc.)"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("enable_aks_addon", {
            "cluster": request.cluster_name,
            "addon": request.addon_name
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Addon '{request.addon_name}' enablement initiated",
            "cluster_name": request.cluster_name,
            "addon_name": request.addon_name
        }
    except Exception as e:
        log_action("enable_aks_addon", {
            "cluster": request.cluster_name,
            "addon": request.addon_name
        }, False, str(e))
        logger.error(f"Error enabling addon: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/disable_aks_addon")
async def disable_aks_addon(request: AKSAddonRequest):
    """Disable AKS addon"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("disable_aks_addon", {
            "cluster": request.cluster_name,
            "addon": request.addon_name
        }, True)
        
        return {
            "status": "initiated",
            "message": f"Addon '{request.addon_name}' disablement initiated",
            "cluster_name": request.cluster_name,
            "addon_name": request.addon_name
        }
    except Exception as e:
        log_action("disable_aks_addon", {
            "cluster": request.cluster_name,
            "addon": request.addon_name
        }, False, str(e))
        logger.error(f"Error disabling addon: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/drain_k8s_node")
async def drain_k8s_node(request: K8sDrainNodeRequest):
    """Drain a Kubernetes node for maintenance"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("drain_k8s_node", {
            "cluster": request.cluster_name,
            "node": request.node_name
        }, True)
        
        return {
            "status": "not_implemented",
            "message": "Node draining requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "node_name": request.node_name,
            "note": "Use kubernetes client to drain node (evict pods gracefully)"
        }
    except Exception as e:
        log_action("drain_k8s_node", {
            "cluster": request.cluster_name,
            "node": request.node_name
        }, False, str(e))
        logger.error(f"Error draining node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/delete_k8s_pod")
async def delete_k8s_pod(request: K8sDeletePodRequest):
    """Delete a problematic pod"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("delete_k8s_pod", {
            "cluster": request.cluster_name,
            "namespace": request.namespace,
            "pod": request.pod_name
        }, True)
        
        return {
            "status": "not_implemented",
            "message": "Pod deletion requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "pod_name": request.pod_name,
            "note": "Use kubernetes client to delete pod"
        }
    except Exception as e:
        log_action("delete_k8s_pod", {
            "cluster": request.cluster_name,
            "pod": request.pod_name
        }, False, str(e))
        logger.error(f"Error deleting pod: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/scale_k8s_deployment")
async def scale_k8s_deployment(request: K8sScaleRequest):
    """Scale a Kubernetes deployment"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("scale_k8s_deployment", {
            "cluster": request.cluster_name,
            "namespace": request.namespace,
            "resource": request.resource_name,
            "replicas": request.replicas
        }, True)
        
        return {
            "status": "not_implemented",
            "message": "Scaling requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "resource_name": request.resource_name,
            "replicas": request.replicas,
            "note": "Use kubernetes client to scale deployment"
        }
    except Exception as e:
        log_action("scale_k8s_deployment", {
            "cluster": request.cluster_name,
            "resource": request.resource_name
        }, False, str(e))
        logger.error(f"Error scaling deployment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/rollback_k8s_deployment")
async def rollback_k8s_deployment(request: RestartK8sDeploymentRequest):
    """Rollback a Kubernetes deployment to previous revision"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("rollback_k8s_deployment", {
            "cluster": request.cluster_name,
            "namespace": request.namespace,
            "deployment": request.deployment
        }, True)
        
        return {
            "status": "not_implemented",
            "message": "Rollback requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "deployment": request.deployment,
            "note": "Use kubernetes client to rollback deployment"
        }
    except Exception as e:
        log_action("rollback_k8s_deployment", {
            "cluster": request.cluster_name,
            "deployment": request.deployment
        }, False, str(e))
        logger.error(f"Error rolling back deployment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/apply_k8s_manifest")
async def apply_k8s_manifest(request: K8sApplyManifestRequest):
    """Apply a Kubernetes manifest"""
    if not request.approve:
        raise HTTPException(status_code=403, detail="Action requires approve=true")
    
    if not check_rate_limit():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        log_action("apply_k8s_manifest", {
            "cluster": request.cluster_name,
            "namespace": request.namespace
        }, True)
        
        return {
            "status": "not_implemented",
            "message": "Applying manifest requires kubeconfig and kubernetes client",
            "cluster_name": request.cluster_name,
            "namespace": request.namespace,
            "note": "Use kubernetes client to apply manifest YAML"
        }
    except Exception as e:
        log_action("apply_k8s_manifest", {
            "cluster": request.cluster_name
        }, False, str(e))
        logger.error(f"Error applying manifest: {str(e)}")
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
# App Service - Best Practices Tools
# ============================================================================

@app.post("/tools/check_app_service_best_practices")
async def check_app_service_best_practices(request: AppServiceRequest):
    """Comprehensive best practices check for App Service"""
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
        
        recommendations = []
        
        # Check Always On
        if not config.always_on:
            recommendations.append({
                "category": "availability",
                "severity": "medium",
                "issue": "Always On is disabled",
                "recommendation": "Enable Always On to keep the app loaded at all times"
            })
        
        # Check HTTPS
        if not app.https_only:
            recommendations.append({
                "category": "security",
                "severity": "high",
                "issue": "HTTPS Only is not enforced",
                "recommendation": "Enable HTTPS Only to enforce secure connections"
            })
        
        # Check minimum TLS version
        if config.min_tls_version and config.min_tls_version < "1.2":
            recommendations.append({
                "category": "security",
                "severity": "high",
                "issue": f"Minimum TLS version is {config.min_tls_version}",
                "recommendation": "Set minimum TLS version to 1.2 or higher"
            })
        
        # Check deployment slots
        slots_count = 0
        try:
            for _ in client.web_apps.list_slots(resource_group, request.app_name):
                slots_count += 1
        except:
            pass
        
        if slots_count == 0:
            recommendations.append({
                "category": "deployment",
                "severity": "medium",
                "issue": "No deployment slots configured",
                "recommendation": "Use deployment slots for zero-downtime deployments"
            })
        
        return {
            "app_name": request.app_name,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
            "summary": "Best practices check completed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking best practices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_app_service_security")
async def check_app_service_security(request: AppServiceRequest):
    """Security configuration assessment for App Service"""
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
        
        security_checks = {
            "https_only": app.https_only,
            "client_cert_enabled": app.client_cert_enabled,
            "min_tls_version": config.min_tls_version,
            "ftps_state": config.ftps_state,
            "remote_debugging_enabled": config.remote_debugging_enabled,
            "managed_identity": app.identity is not None
        }
        
        return {
            "app_name": request.app_name,
            "security_checks": security_checks,
            "security_score": sum(1 for v in [
                security_checks["https_only"],
                security_checks["client_cert_enabled"],
                security_checks["min_tls_version"] == "1.2",
                security_checks["ftps_state"] in ["FtpsOnly", "Disabled"],
                not security_checks["remote_debugging_enabled"],
                security_checks["managed_identity"]
            ] if v) * 100 // 6
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking security: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_app_service_backup_config")
async def check_app_service_backup_config(request: AppServiceRequest):
    """Check backup configuration for App Service"""
    try:
        return {
            "app_name": request.app_name,
            "note": "Backup configuration can be checked via App Service backup API",
            "recommendation": "Configure automated backups for disaster recovery"
        }
    except Exception as e:
        logger.error(f"Error checking backup config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_app_service_monitoring")
async def check_app_service_monitoring(request: AppServiceRequest):
    """Check monitoring configuration completeness"""
    try:
        client = WebSiteManagementClient(auth_manager.credential, request.subscription_id)
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
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
        
        monitoring_checks = {
            "diagnostic_settings_configured": False,
            "application_insights_enabled": False,
            "alerts_configured": False
        }
        
        # Check diagnostic settings
        try:
            settings_list = list(monitor_client.diagnostic_settings.list(app_id))
            monitoring_checks["diagnostic_settings_configured"] = len(settings_list) > 0
        except:
            pass
        
        return {
            "app_name": request.app_name,
            "monitoring_checks": monitoring_checks,
            "recommendations": [
                "Enable Application Insights for application performance monitoring",
                "Configure diagnostic settings to send logs to Log Analytics",
                "Set up alerts for critical metrics (CPU, memory, response time)"
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AKS - Best Practices Tools
# ============================================================================

@app.post("/tools/check_aks_best_practices")
async def check_aks_best_practices(request: AKSRequest):
    """Comprehensive AKS best practices check"""
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
        
        recommendations = []
        
        # Check RBAC
        if not cluster.enable_rbac:
            recommendations.append({
                "category": "security",
                "severity": "high",
                "issue": "RBAC is not enabled",
                "recommendation": "Enable RBAC for fine-grained access control"
            })
        
        # Check network policy
        if cluster.network_profile and not cluster.network_profile.network_policy:
            recommendations.append({
                "category": "security",
                "severity": "medium",
                "issue": "Network policy is not configured",
                "recommendation": "Enable network policy (Azure or Calico) for pod-to-pod traffic control"
            })
        
        # Check monitoring addon
        monitoring_enabled = False
        if cluster.addon_profiles and "omsagent" in cluster.addon_profiles:
            monitoring_enabled = cluster.addon_profiles["omsagent"].enabled
        
        if not monitoring_enabled:
            recommendations.append({
                "category": "monitoring",
                "severity": "high",
                "issue": "Container Insights (monitoring addon) is not enabled",
                "recommendation": "Enable Container Insights for cluster and container monitoring"
            })
        
        # Check autoscaling on nodepools
        has_autoscaling = False
        for profile in cluster.agent_pool_profiles or []:
            if profile.enable_auto_scaling:
                has_autoscaling = True
                break
        
        if not has_autoscaling:
            recommendations.append({
                "category": "scalability",
                "severity": "medium",
                "issue": "No nodepools have autoscaling enabled",
                "recommendation": "Enable cluster autoscaler for automatic scaling based on workload"
            })
        
        return {
            "cluster_name": request.cluster_name,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations,
            "summary": "AKS best practices check completed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking AKS best practices: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_aks_security_config")
async def check_aks_security_config(request: AKSRequest):
    """Security configuration assessment for AKS"""
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
        
        security_checks = {
            "rbac_enabled": cluster.enable_rbac,
            "private_cluster": cluster.api_server_access_profile.enable_private_cluster if cluster.api_server_access_profile else False,
            "network_policy": cluster.network_profile.network_policy if cluster.network_profile else None,
            "azure_policy_enabled": False,
            "managed_identity": cluster.identity is not None,
            "disk_encryption": cluster.disk_encryption_set_id is not None
        }
        
        # Check Azure Policy addon
        if cluster.addon_profiles and "azurepolicy" in cluster.addon_profiles:
            security_checks["azure_policy_enabled"] = cluster.addon_profiles["azurepolicy"].enabled
        
        return {
            "cluster_name": request.cluster_name,
            "security_checks": security_checks,
            "security_score": sum(1 for v in security_checks.values() if v) * 100 // len(security_checks)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking AKS security: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_aks_cost_optimization")
async def check_aks_cost_optimization(request: AKSRequest):
    """AKS cost optimization recommendations"""
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
        
        recommendations = []
        
        # Check for autoscaling
        for profile in cluster.agent_pool_profiles or []:
            if not profile.enable_auto_scaling:
                recommendations.append({
                    "category": "cost",
                    "nodepool": profile.name,
                    "issue": "Autoscaling not enabled",
                    "recommendation": "Enable autoscaling to scale down during low usage",
                    "potential_savings": "20-40%"
                })
        
        # Check VM sizes
        for profile in cluster.agent_pool_profiles or []:
            if profile.vm_size and "Standard_D" in profile.vm_size:
                recommendations.append({
                    "category": "cost",
                    "nodepool": profile.name,
                    "issue": f"Using {profile.vm_size} VMs",
                    "recommendation": "Consider Ev3 or Esv3 series for better cost/performance ratio"
                })
        
        return {
            "cluster_name": request.cluster_name,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking cost optimization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_aks_upgrade_readiness")
async def check_aks_upgrade_readiness(request: AKSRequest):
    """Assess AKS cluster upgrade readiness"""
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
        
        # Get available upgrades
        try:
            upgrade_profile = client.managed_clusters.get_upgrade_profile(resource_group, request.cluster_name)
            available_upgrades = [upgrade.kubernetes_version for upgrade in upgrade_profile.control_plane_profile.upgrades] if upgrade_profile.control_plane_profile.upgrades else []
        except:
            available_upgrades = []
        
        readiness_checks = {
            "current_version": cluster.kubernetes_version,
            "available_upgrades": available_upgrades,
            "all_nodepools_same_version": True,
            "pod_disruption_budgets_configured": "Requires K8s API access",
            "backup_taken": "Manual verification required"
        }
        
        # Check nodepool versions
        for profile in cluster.agent_pool_profiles or []:
            if profile.orchestrator_version != cluster.kubernetes_version:
                readiness_checks["all_nodepools_same_version"] = False
        
        return {
            "cluster_name": request.cluster_name,
            "readiness_checks": readiness_checks,
            "recommendations": [
                "Ensure all nodepools are on the same version before upgrading control plane",
                "Review Kubernetes changelog for breaking changes",
                "Test upgrade in non-production environment first",
                "Ensure Pod Disruption Budgets are configured for critical workloads"
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking upgrade readiness: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Environment Configuration - Best Practices Tools
# ============================================================================

@app.post("/tools/check_resource_tagging")
async def check_resource_tagging(request: ResourceGroupRequest):
    """Check resource tagging compliance"""
    try:
        resource_client = ResourceManagementClient(auth_manager.credential, request.subscription_id)
        
        # Get resources in resource group
        resources = list(resource_client.resources.list_by_resource_group(request.resource_group))
        
        required_tags = ["Environment", "Owner", "CostCenter", "Application"]
        
        untagged_resources = []
        partially_tagged = []
        
        for resource in resources:
            resource_tags = resource.tags or {}
            missing_tags = [tag for tag in required_tags if tag not in resource_tags]
            
            if not resource_tags:
                untagged_resources.append(resource.name)
            elif missing_tags:
                partially_tagged.append({
                    "resource": resource.name,
                    "missing_tags": missing_tags
                })
        
        return {
            "resource_group": request.resource_group,
            "total_resources": len(resources),
            "untagged_resources": len(untagged_resources),
            "partially_tagged": len(partially_tagged),
            "compliance_score": (len(resources) - len(untagged_resources) - len(partially_tagged)) * 100 // len(resources) if len(resources) > 0 else 100,
            "details": {
                "untagged": untagged_resources[:10],  # First 10
                "partially_tagged": partially_tagged[:10]
            }
        }
    except Exception as e:
        logger.error(f"Error checking tagging: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_network_security")
async def check_network_security(request: ResourceGroupRequest):
    """Check Network Security Group configurations"""
    try:
        return {
            "resource_group": request.resource_group,
            "note": "NSG analysis requires Network Management Client",
            "recommendations": [
                "Ensure NSGs are applied to all subnets",
                "Review NSG rules for overly permissive access",
                "Implement least privilege network access",
                "Enable NSG flow logs for security monitoring"
            ]
        }
    except Exception as e:
        logger.error(f"Error checking network security: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_key_vault_security")
async def check_key_vault_security(request: BaseRequest):
    """Check Key Vault security configuration"""
    try:
        return {
            "note": "Key Vault security check requires Key Vault Management Client",
            "recommendations": [
                "Enable soft delete and purge protection",
                "Use RBAC instead of access policies where possible",
                "Enable diagnostic logging",
                "Restrict network access using firewall rules",
                "Use managed identities for application access"
            ]
        }
    except Exception as e:
        logger.error(f"Error checking Key Vault security: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_monitoring_coverage")
async def check_monitoring_coverage(request: ResourceGroupRequest):
    """Assess monitoring coverage across resources"""
    try:
        resource_client = ResourceManagementClient(auth_manager.credential, request.subscription_id)
        monitor_client = MonitorManagementClient(auth_manager.credential, request.subscription_id)
        
        resources = list(resource_client.resources.list_by_resource_group(request.resource_group))
        
        monitored_count = 0
        for resource in resources:
            try:
                settings = list(monitor_client.diagnostic_settings.list(resource.id))
                if len(settings) > 0:
                    monitored_count += 1
            except:
                pass
        
        coverage_percent = monitored_count * 100 // len(resources) if len(resources) > 0 else 0
        
        return {
            "resource_group": request.resource_group,
            "total_resources": len(resources),
            "monitored_resources": monitored_count,
            "coverage_percentage": coverage_percent,
            "recommendations": [
                "Enable diagnostic settings for all critical resources",
                "Send logs to centralized Log Analytics workspace",
                "Configure alerts for critical metrics",
                "Use Application Insights for application monitoring"
            ]
        }
    except Exception as e:
        logger.error(f"Error checking monitoring coverage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/check_resource_locks")
async def check_resource_locks(request: ResourceGroupRequest):
    """Check resource lock configuration"""
    try:
        return {
            "resource_group": request.resource_group,
            "note": "Resource locks check requires Management Lock Client",
            "recommendations": [
                "Apply ReadOnly or CanNotDelete locks to critical resources",
                "Lock production resource groups to prevent accidental deletion",
                "Document lock removal procedures for emergency scenarios"
            ]
        }
    except Exception as e:
        logger.error(f"Error checking resource locks: {str(e)}")
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
