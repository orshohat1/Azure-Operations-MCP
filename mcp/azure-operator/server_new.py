"""
Azure Operator MCP Server (v1) - Main Application
AI SRE layer for Azure workloads with focus on App Service and AKS
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Import local modules
from auth import AuthManager
from utils import check_rate_limit, log_action

# Import tool modules
import app_service_tools
import aks_tools
import best_practices_tools

# Import models
from models import (
    # Base
    BaseRequest,
    # App Service
    AppServiceRequest, AppServiceSlotRequest, AppServiceFileSystemRequest,
    RestartAppServiceRequest, RestartAppServiceSlotRequest,
    ScaleAppServicePlanRequest, SetAppSettingRequest,
    EnableDetailedErrorLogsRequest, ClearAppServiceCacheRequest,
    RedeployLastReleaseRequest, SwapSlotsRequest,
    ResetAppServiceCredentialsRequest, EnableAutoscaleRequest, DisableAutoscaleRequest,
    # App Insights
    AppInsightsRequest, AppInsightsQueryRequest, AppInsightsTimeRangeRequest, SlowRequestsRequest,
    # AKS
    AKSRequest, AKSPodsRequest, AKSPodLogsRequest, AKSNodePoolRequest,
    ScaleAKSNodepoolRequest, RestartK8sDeploymentRequest, CordonNodeRequest,
    K8sResourceRequest, K8sScaleRequest, K8sPodRequest, K8sDeletePodRequest,
    K8sDrainNodeRequest, AKSUpgradeRequest, AKSNodePoolUpgradeRequest,
    AKSAddNodePoolRequest, AKSDeleteNodePoolRequest, AKSAddonRequest, K8sApplyManifestRequest,
    # Secrets & CI
    RotateKeyVaultSecretRequest, TriggerGitHubWorkflowRequest,
    # Best Practices
    ResourceGroupRequest
)

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Global auth manager
auth_manager = AuthManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app"""
    logger.info("🚀 Azure Operator MCP Server starting...")
    logger.info(f"📊 Rate limit: {os.getenv('MAX_ACTIONS_PER_MINUTE', '10')} actions per minute")
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
# Health Check Endpoints
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
    return await app_service_tools.list_app_services(auth_manager, request)


@app.post("/tools/get_app_service_state")
async def get_app_service_state(request: AppServiceRequest):
    return await app_service_tools.get_app_service_state(auth_manager, request)


@app.post("/tools/get_app_service_config")
async def get_app_service_config(request: AppServiceRequest):
    return await app_service_tools.get_app_service_config(auth_manager, request)


@app.post("/tools/get_app_service_diagnostic_settings")
async def get_app_service_diagnostic_settings(request: AppServiceRequest):
    return await app_service_tools.get_app_service_diagnostic_settings(auth_manager, request)


@app.post("/tools/get_app_service_container_logs")
async def get_app_service_container_logs(request: AppServiceRequest):
    return await app_service_tools.get_app_service_container_logs(auth_manager, request)


@app.post("/tools/get_app_service_file_system")
async def get_app_service_file_system(request: AppServiceFileSystemRequest):
    return await app_service_tools.get_app_service_file_system(auth_manager, request)


@app.post("/tools/get_app_service_process_list")
async def get_app_service_process_list(request: AppServiceRequest):
    return await app_service_tools.get_app_service_process_list(auth_manager, request)


@app.post("/tools/get_app_service_memory_dump")
async def get_app_service_memory_dump(request: AppServiceRequest):
    return await app_service_tools.get_app_service_memory_dump(auth_manager, request)


@app.post("/tools/get_app_service_instance_health")
async def get_app_service_instance_health(request: AppServiceRequest):
    return await app_service_tools.get_app_service_instance_health(auth_manager, request)


@app.post("/tools/get_app_service_scaling_rules")
async def get_app_service_scaling_rules(request: AppServiceRequest):
    return await app_service_tools.get_app_service_scaling_rules(auth_manager, request)


@app.post("/tools/get_app_service_last_deploy")
async def get_app_service_last_deploy(request: AppServiceRequest):
    return await app_service_tools.get_app_service_last_deploy(auth_manager, request)


@app.post("/tools/get_app_service_deployment_logs")
async def get_app_service_deployment_logs(request: AppServiceRequest):
    return await app_service_tools.get_app_service_deployment_logs(auth_manager, request)


@app.post("/tools/get_app_service_environment_variables")
async def get_app_service_environment_variables(request: AppServiceRequest):
    return await app_service_tools.get_app_service_environment_variables(auth_manager, request)


# ============================================================================
# Azure Monitor & App Insights
# ============================================================================

@app.post("/tools/query_app_insights")
async def query_app_insights(request: AppInsightsQueryRequest):
    return await app_service_tools.query_app_insights(auth_manager, request)


@app.post("/tools/get_recent_exceptions")
async def get_recent_exceptions(request: AppInsightsTimeRangeRequest):
    return await app_service_tools.get_recent_exceptions(auth_manager, request)


@app.post("/tools/get_dependency_failures")
async def get_dependency_failures(request: AppInsightsTimeRangeRequest):
    return await app_service_tools.get_dependency_failures(auth_manager, request)


@app.post("/tools/get_slow_requests")
async def get_slow_requests(request: SlowRequestsRequest):
    return await app_service_tools.get_slow_requests(auth_manager, request)


@app.post("/tools/get_availability_tests")
async def get_availability_tests(request: AppInsightsRequest):
    return await app_service_tools.get_availability_tests(auth_manager, request)


@app.post("/tools/get_alerts_last_24h")
async def get_alerts_last_24h(request: BaseRequest):
    return await best_practices_tools.get_alerts_last_24h(auth_manager, request)


# ============================================================================
# AKS - Observability Tools
# ============================================================================

@app.post("/tools/list_aks_clusters")
async def list_aks_clusters(request: BaseRequest):
    return await aks_tools.list_aks_clusters(auth_manager, request)


@app.post("/tools/get_aks_status")
async def get_aks_status(request: AKSRequest):
    return await aks_tools.get_aks_status(auth_manager, request)


@app.post("/tools/get_failing_pods")
async def get_failing_pods(request: AKSPodsRequest):
    return await aks_tools.get_failing_pods(auth_manager, request)


@app.post("/tools/get_pod_logs")
async def get_pod_logs(request: AKSPodLogsRequest):
    return await aks_tools.get_pod_logs(auth_manager, request)


@app.post("/tools/get_aks_cluster_diagnostics")
async def get_aks_cluster_diagnostics(request: AKSRequest):
    return await aks_tools.get_aks_cluster_diagnostics(auth_manager, request)


@app.post("/tools/get_aks_node_pool_details")
async def get_aks_node_pool_details(request: AKSNodePoolRequest):
    return await aks_tools.get_aks_node_pool_details(auth_manager, request)


@app.post("/tools/get_aks_networking_config")
async def get_aks_networking_config(request: AKSRequest):
    return await aks_tools.get_aks_networking_config(auth_manager, request)


@app.post("/tools/get_aks_addon_status")
async def get_aks_addon_status(request: AKSRequest):
    return await aks_tools.get_aks_addon_status(auth_manager, request)


@app.post("/tools/get_aks_upgrade_history")
async def get_aks_upgrade_history(request: AKSRequest):
    return await aks_tools.get_aks_upgrade_history(auth_manager, request)


@app.post("/tools/get_aks_resource_usage")
async def get_aks_resource_usage(request: AKSRequest):
    return await aks_tools.get_aks_resource_usage(auth_manager, request)


@app.post("/tools/list_k8s_namespaces")
async def list_k8s_namespaces(request: AKSRequest):
    return await aks_tools.list_k8s_namespaces(auth_manager, request)


@app.post("/tools/get_k8s_pod_status")
async def get_k8s_pod_status(request: K8sPodRequest):
    return await aks_tools.get_k8s_pod_status(auth_manager, request)


@app.post("/tools/get_k8s_service_endpoints")
async def get_k8s_service_endpoints(request: AKSPodsRequest):
    return await aks_tools.get_k8s_service_endpoints(auth_manager, request)


@app.post("/tools/get_k8s_persistent_volumes")
async def get_k8s_persistent_volumes(request: AKSPodsRequest):
    return await aks_tools.get_k8s_persistent_volumes(auth_manager, request)


@app.post("/tools/get_k8s_secrets_configmaps")
async def get_k8s_secrets_configmaps(request: AKSPodsRequest):
    return await aks_tools.get_k8s_secrets_configmaps(auth_manager, request)


@app.post("/tools/get_k8s_ingress_status")
async def get_k8s_ingress_status(request: AKSPodsRequest):
    return await aks_tools.get_k8s_ingress_status(auth_manager, request)


@app.post("/tools/get_k8s_deployment_status")
async def get_k8s_deployment_status(request: K8sResourceRequest):
    return await aks_tools.get_k8s_deployment_status(auth_manager, request)


@app.post("/tools/get_k8s_statefulset_status")
async def get_k8s_statefulset_status(request: K8sResourceRequest):
    return await aks_tools.get_k8s_statefulset_status(auth_manager, request)


@app.post("/tools/get_k8s_daemonset_status")
async def get_k8s_daemonset_status(request: K8sResourceRequest):
    return await aks_tools.get_k8s_daemonset_status(auth_manager, request)


@app.post("/tools/get_k8s_jobs_cronjobs")
async def get_k8s_jobs_cronjobs(request: AKSPodsRequest):
    return await aks_tools.get_k8s_jobs_cronjobs(auth_manager, request)


@app.post("/tools/get_k8s_node_conditions")
async def get_k8s_node_conditions(request: AKSRequest):
    return await aks_tools.get_k8s_node_conditions(auth_manager, request)


@app.post("/tools/get_k8s_events")
async def get_k8s_events(request: AKSPodsRequest):
    return await aks_tools.get_k8s_events(auth_manager, request)


# ============================================================================
# App Service - Remediation Actions
# ============================================================================

@app.post("/tools/restart_app_service")
async def restart_app_service(request: RestartAppServiceRequest):
    return await app_service_tools.restart_app_service(auth_manager, request)


@app.post("/tools/restart_app_service_slot")
async def restart_app_service_slot(request: RestartAppServiceSlotRequest):
    return await app_service_tools.restart_app_service_slot(auth_manager, request)


@app.post("/tools/scale_app_service_plan")
async def scale_app_service_plan(request: ScaleAppServicePlanRequest):
    return await app_service_tools.scale_app_service_plan(auth_manager, request)


@app.post("/tools/enable_detailed_error_logs")
async def enable_detailed_error_logs(request: EnableDetailedErrorLogsRequest):
    return await app_service_tools.enable_detailed_error_logs(auth_manager, request)


@app.post("/tools/clear_app_service_cache")
async def clear_app_service_cache(request: ClearAppServiceCacheRequest):
    return await app_service_tools.clear_app_service_cache(auth_manager, request)


@app.post("/tools/redeploy_last_release")
async def redeploy_last_release(request: RedeployLastReleaseRequest):
    return await app_service_tools.redeploy_last_release(auth_manager, request)


@app.post("/tools/swap_slots")
async def swap_slots(request: SwapSlotsRequest):
    return await app_service_tools.swap_slots(auth_manager, request)


@app.post("/tools/reset_app_service_credentials")
async def reset_app_service_credentials(request: ResetAppServiceCredentialsRequest):
    return await app_service_tools.reset_app_service_credentials(auth_manager, request)


@app.post("/tools/set_app_setting")
async def set_app_setting(request: SetAppSettingRequest):
    return await app_service_tools.set_app_setting(auth_manager, request)


@app.post("/tools/enable_autoscale")
async def enable_autoscale(request: EnableAutoscaleRequest):
    return await app_service_tools.enable_autoscale(auth_manager, request)


@app.post("/tools/disable_autoscale")
async def disable_autoscale(request: DisableAutoscaleRequest):
    return await app_service_tools.disable_autoscale(auth_manager, request)


# ============================================================================
# AKS - Remediation Actions
# ============================================================================

@app.post("/tools/scale_aks_nodepool")
async def scale_aks_nodepool(request: ScaleAKSNodepoolRequest):
    return await aks_tools.scale_aks_nodepool(auth_manager, request)


@app.post("/tools/restart_k8s_deployment")
async def restart_k8s_deployment(request: RestartK8sDeploymentRequest):
    return await aks_tools.restart_k8s_deployment(auth_manager, request)


@app.post("/tools/cordon_node")
async def cordon_node(request: CordonNodeRequest):
    return await aks_tools.cordon_node(auth_manager, request)


@app.post("/tools/uncordon_node")
async def uncordon_node(request: CordonNodeRequest):
    return await aks_tools.uncordon_node(auth_manager, request)


@app.post("/tools/update_aks_kubernetes_version")
async def update_aks_kubernetes_version(request: AKSUpgradeRequest):
    return await aks_tools.update_aks_kubernetes_version(auth_manager, request)


@app.post("/tools/update_aks_nodepool_version")
async def update_aks_nodepool_version(request: AKSNodePoolUpgradeRequest):
    return await aks_tools.update_aks_nodepool_version(auth_manager, request)


@app.post("/tools/add_aks_nodepool")
async def add_aks_nodepool(request: AKSAddNodePoolRequest):
    return await aks_tools.add_aks_nodepool(auth_manager, request)


@app.post("/tools/delete_aks_nodepool")
async def delete_aks_nodepool(request: AKSDeleteNodePoolRequest):
    return await aks_tools.delete_aks_nodepool(auth_manager, request)


@app.post("/tools/enable_aks_addon")
async def enable_aks_addon(request: AKSAddonRequest):
    return await aks_tools.enable_aks_addon(auth_manager, request)


@app.post("/tools/disable_aks_addon")
async def disable_aks_addon(request: AKSAddonRequest):
    return await aks_tools.disable_aks_addon(auth_manager, request)


@app.post("/tools/drain_k8s_node")
async def drain_k8s_node(request: K8sDrainNodeRequest):
    return await aks_tools.drain_k8s_node(auth_manager, request)


@app.post("/tools/delete_k8s_pod")
async def delete_k8s_pod(request: K8sDeletePodRequest):
    return await aks_tools.delete_k8s_pod(auth_manager, request)


@app.post("/tools/scale_k8s_deployment")
async def scale_k8s_deployment(request: K8sScaleRequest):
    return await aks_tools.scale_k8s_deployment(auth_manager, request)


@app.post("/tools/rollback_k8s_deployment")
async def rollback_k8s_deployment(request: RestartK8sDeploymentRequest):
    return await aks_tools.rollback_k8s_deployment(auth_manager, request)


@app.post("/tools/apply_k8s_manifest")
async def apply_k8s_manifest(request: K8sApplyManifestRequest):
    return await aks_tools.apply_k8s_manifest(auth_manager, request)


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
    return await app_service_tools.check_app_service_best_practices(auth_manager, request)


@app.post("/tools/check_app_service_security")
async def check_app_service_security(request: AppServiceRequest):
    return await app_service_tools.check_app_service_security(auth_manager, request)


@app.post("/tools/check_app_service_backup_config")
async def check_app_service_backup_config(request: AppServiceRequest):
    return await app_service_tools.check_app_service_backup_config(auth_manager, request)


@app.post("/tools/check_app_service_monitoring")
async def check_app_service_monitoring(request: AppServiceRequest):
    return await app_service_tools.check_app_service_monitoring(auth_manager, request)


# ============================================================================
# AKS - Best Practices Tools
# ============================================================================

@app.post("/tools/check_aks_best_practices")
async def check_aks_best_practices(request: AKSRequest):
    return await aks_tools.check_aks_best_practices(auth_manager, request)


@app.post("/tools/check_aks_security_config")
async def check_aks_security_config(request: AKSRequest):
    return await aks_tools.check_aks_security_config(auth_manager, request)


@app.post("/tools/check_aks_cost_optimization")
async def check_aks_cost_optimization(request: AKSRequest):
    return await aks_tools.check_aks_cost_optimization(auth_manager, request)


@app.post("/tools/check_aks_upgrade_readiness")
async def check_aks_upgrade_readiness(request: AKSRequest):
    return await aks_tools.check_aks_upgrade_readiness(auth_manager, request)


# ============================================================================
# Environment Configuration - Best Practices Tools
# ============================================================================

@app.post("/tools/check_resource_tagging")
async def check_resource_tagging(request: ResourceGroupRequest):
    return await best_practices_tools.check_resource_tagging(auth_manager, request)


@app.post("/tools/check_network_security")
async def check_network_security(request: ResourceGroupRequest):
    return await best_practices_tools.check_network_security(auth_manager, request)


@app.post("/tools/check_key_vault_security")
async def check_key_vault_security(request: BaseRequest):
    return await best_practices_tools.check_key_vault_security(auth_manager, request)


@app.post("/tools/check_monitoring_coverage")
async def check_monitoring_coverage(request: ResourceGroupRequest):
    return await best_practices_tools.check_monitoring_coverage(auth_manager, request)


@app.post("/tools/check_resource_locks")
async def check_resource_locks(request: ResourceGroupRequest):
    return await best_practices_tools.check_resource_locks(auth_manager, request)


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
