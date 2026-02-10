"""
Pydantic models for request/response validation
"""

from typing import Optional
from pydantic import BaseModel, Field


# ============================================================================
# Base Request Models
# ============================================================================

class BaseRequest(BaseModel):
    subscription_id: str = Field(..., description="Azure subscription ID")


class ActionRequest(BaseRequest):
    approve: bool = Field(..., description="Must be true to execute action")


# ============================================================================
# App Service Request Models
# ============================================================================

class AppServiceRequest(BaseRequest):
    app_name: str = Field(..., description="App Service name")


class AppServiceSlotRequest(AppServiceRequest):
    slot: str = Field(..., description="Deployment slot name")


class AppServiceFileSystemRequest(AppServiceRequest):
    path: str = Field(default="/home", description="File system path to explore")


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
# Application Insights Request Models
# ============================================================================

class AppInsightsRequest(BaseModel):
    app_insights_resource_id: str = Field(..., description="Application Insights resource ID")


class AppInsightsQueryRequest(AppInsightsRequest):
    kql_query: str = Field(..., description="KQL query to execute")


class AppInsightsTimeRangeRequest(AppInsightsRequest):
    last_hours: int = Field(default=24, description="Number of hours to look back")


class SlowRequestsRequest(AppInsightsRequest):
    p95_ms: int = Field(default=1000, description="P95 threshold in milliseconds")


# ============================================================================
# AKS Request Models
# ============================================================================

class AKSRequest(BaseRequest):
    cluster_name: str = Field(..., description="AKS cluster name")


class AKSPodsRequest(AKSRequest):
    namespace: str = Field(default="default", description="Kubernetes namespace")


class AKSPodLogsRequest(AKSPodsRequest):
    pod: str = Field(..., description="Pod name")


class AKSNodePoolRequest(AKSRequest):
    nodepool_name: str = Field(..., description="Nodepool name")


class ScaleAKSNodepoolRequest(AKSRequest, ActionRequest):
    nodepool_name: str = Field(..., description="Nodepool name")
    min_count: Optional[int] = Field(None, description="Minimum node count")
    max_count: Optional[int] = Field(None, description="Maximum node count")


class RestartK8sDeploymentRequest(AKSPodsRequest, ActionRequest):
    deployment: str = Field(..., description="Deployment name")


class CordonNodeRequest(AKSRequest, ActionRequest):
    node_name: str = Field(..., description="Node name to cordon")


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


# ============================================================================
# Secrets & CI Request Models
# ============================================================================

class RotateKeyVaultSecretRequest(ActionRequest):
    vault_name: str = Field(..., description="Key Vault name")
    secret_name: str = Field(..., description="Secret name")


class TriggerGitHubWorkflowRequest(ActionRequest):
    repo_owner: str = Field(..., description="GitHub repository owner")
    repo_name: str = Field(..., description="GitHub repository name")
    workflow_id: str = Field(..., description="Workflow ID or filename")
    ref: str = Field(default="main", description="Git ref to run workflow on")


# ============================================================================
# Best Practices Request Models
# ============================================================================

class BestPracticesRequest(BaseRequest):
    resource_type: str = Field(..., description="Resource type (app_service, aks, environment)")
    resource_name: Optional[str] = Field(None, description="Specific resource name (optional)")


class ResourceGroupRequest(BaseRequest):
    resource_group: str = Field(..., description="Resource group name")
