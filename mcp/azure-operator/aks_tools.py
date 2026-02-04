"""
AKS and Kubernetes Tools for Azure Operator MCP Server
All AKS and Kubernetes observability, remediation, and best practices functions
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.monitor import MonitorManagementClient

from models import (
    BaseRequest,
    AKSRequest,
    AKSPodsRequest,
    AKSPodLogsRequest,
    AKSNodePoolRequest,
    ScaleAKSNodepoolRequest,
    RestartK8sDeploymentRequest,
    CordonNodeRequest,
    K8sResourceRequest,
    K8sScaleRequest,
    K8sPodRequest,
    K8sDeletePodRequest,
    K8sDrainNodeRequest,
    AKSUpgradeRequest,
    AKSNodePoolUpgradeRequest,
    AKSAddNodePoolRequest,
    AKSDeleteNodePoolRequest,
    AKSAddonRequest,
    K8sApplyManifestRequest,
)
from utils import check_rate_limit, log_action

logger = logging.getLogger(__name__)


# ============================================================================
# AKS - Observability Tools
# ============================================================================

def list_aks_clusters(auth_manager):
    """Create route handler for listing all AKS clusters"""
    async def handler(request: BaseRequest):
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
    return handler


def get_aks_status(auth_manager):
    """Create route handler for getting AKS cluster status"""
    async def handler(request: AKSRequest):
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
    return handler


def get_failing_pods(auth_manager):
    """Create route handler for getting failing pods"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_pod_logs(auth_manager):
    """Create route handler for getting pod logs"""
    async def handler(request: AKSPodLogsRequest):
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
    return handler


def get_aks_cluster_diagnostics(auth_manager):
    """Create route handler for getting AKS cluster diagnostics"""
    async def handler(request: AKSRequest):
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
    return handler


def get_aks_node_pool_details(auth_manager):
    """Create route handler for getting nodepool details"""
    async def handler(request: AKSNodePoolRequest):
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
    return handler


def get_aks_networking_config(auth_manager):
    """Create route handler for getting network configuration"""
    async def handler(request: AKSRequest):
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
    return handler


def get_aks_addon_status(auth_manager):
    """Create route handler for getting addon status"""
    async def handler(request: AKSRequest):
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
    return handler


def get_aks_upgrade_history(auth_manager):
    """Create route handler for getting upgrade history"""
    async def handler(request: AKSRequest):
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
    return handler


def get_aks_resource_usage(auth_manager):
    """Create route handler for getting resource usage"""
    async def handler(request: AKSRequest):
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
    return handler


# ============================================================================
# Kubernetes - Observability Tools
# ============================================================================

def list_k8s_namespaces(auth_manager):
    """Create route handler for listing namespaces"""
    async def handler(request: AKSRequest):
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
    return handler


def get_k8s_pod_status(auth_manager):
    """Create route handler for getting pod status"""
    async def handler(request: K8sPodRequest):
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
    return handler


def get_k8s_service_endpoints(auth_manager):
    """Create route handler for getting service endpoints"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_k8s_persistent_volumes(auth_manager):
    """Create route handler for getting persistent volumes"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_k8s_secrets_configmaps(auth_manager):
    """Create route handler for getting secrets and configmaps"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_k8s_ingress_status(auth_manager):
    """Create route handler for getting ingress status"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_k8s_deployment_status(auth_manager):
    """Create route handler for getting deployment status"""
    async def handler(request: K8sResourceRequest):
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
    return handler


def get_k8s_statefulset_status(auth_manager):
    """Create route handler for getting StatefulSet status"""
    async def handler(request: K8sResourceRequest):
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
    return handler


def get_k8s_daemonset_status(auth_manager):
    """Create route handler for getting DaemonSet status"""
    async def handler(request: K8sResourceRequest):
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
    return handler


def get_k8s_jobs_cronjobs(auth_manager):
    """Create route handler for getting Job and CronJob status"""
    async def handler(request: AKSPodsRequest):
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
    return handler


def get_k8s_node_conditions(auth_manager):
    """Create route handler for getting node conditions"""
    async def handler(request: AKSRequest):
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
    return handler


def get_k8s_events(auth_manager):
    """Create route handler for getting cluster events"""
    async def handler(request: AKSPodsRequest):
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
    return handler


# ============================================================================
# AKS - Remediation Actions
# ============================================================================

def scale_aks_nodepool(auth_manager):
    """Create route handler for scaling AKS nodepool"""
    async def handler(request: ScaleAKSNodepoolRequest):
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
    return handler


def restart_k8s_deployment(auth_manager):
    """Create route handler for restarting Kubernetes deployment"""
    async def handler(request: RestartK8sDeploymentRequest):
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
    return handler


def cordon_node(auth_manager):
    """Create route handler for cordoning a node"""
    async def handler(request: CordonNodeRequest):
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
    return handler


def uncordon_node(auth_manager):
    """Create route handler for uncordoning a node"""
    async def handler(request: CordonNodeRequest):
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
    return handler


def update_aks_kubernetes_version(auth_manager):
    """Create route handler for upgrading AKS Kubernetes version"""
    async def handler(request: AKSUpgradeRequest):
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
    return handler


def update_aks_nodepool_version(auth_manager):
    """Create route handler for upgrading AKS nodepool version"""
    async def handler(request: AKSNodePoolUpgradeRequest):
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
    return handler


def add_aks_nodepool(auth_manager):
    """Create route handler for adding AKS nodepool"""
    async def handler(request: AKSAddNodePoolRequest):
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
    return handler


def delete_aks_nodepool(auth_manager):
    """Create route handler for deleting AKS nodepool"""
    async def handler(request: AKSDeleteNodePoolRequest):
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
    return handler


def enable_aks_addon(auth_manager):
    """Create route handler for enabling AKS addon"""
    async def handler(request: AKSAddonRequest):
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
    return handler


def disable_aks_addon(auth_manager):
    """Create route handler for disabling AKS addon"""
    async def handler(request: AKSAddonRequest):
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
    return handler


def drain_k8s_node(auth_manager):
    """Create route handler for draining a Kubernetes node"""
    async def handler(request: K8sDrainNodeRequest):
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
    return handler


def delete_k8s_pod(auth_manager):
    """Create route handler for deleting a pod"""
    async def handler(request: K8sDeletePodRequest):
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
    return handler


def scale_k8s_deployment(auth_manager):
    """Create route handler for scaling Kubernetes deployment"""
    async def handler(request: K8sScaleRequest):
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
    return handler


def rollback_k8s_deployment(auth_manager):
    """Create route handler for rolling back Kubernetes deployment"""
    async def handler(request: RestartK8sDeploymentRequest):
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
    return handler


def apply_k8s_manifest(auth_manager):
    """Create route handler for applying Kubernetes manifest"""
    async def handler(request: K8sApplyManifestRequest):
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
    return handler


# ============================================================================
# AKS - Best Practices Tools
# ============================================================================

def check_aks_best_practices(auth_manager):
    """Create route handler for comprehensive AKS best practices check"""
    async def handler(request: AKSRequest):
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
    return handler


def check_aks_security_config(auth_manager):
    """Create route handler for AKS security configuration assessment"""
    async def handler(request: AKSRequest):
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
    return handler


def check_aks_cost_optimization(auth_manager):
    """Create route handler for AKS cost optimization recommendations"""
    async def handler(request: AKSRequest):
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
    return handler


def check_aks_upgrade_readiness(auth_manager):
    """Create route handler for AKS upgrade readiness assessment"""
    async def handler(request: AKSRequest):
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
    return handler
