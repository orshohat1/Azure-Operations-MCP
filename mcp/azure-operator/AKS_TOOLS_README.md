# AKS Tools Module

This module contains all AKS and Kubernetes-related endpoint functions for the Azure Operator MCP Server.

## Overview

The `aks_tools.py` module provides 41 functions organized into four categories:
- **10 AKS Observability Functions**: Monitor and investigate AKS clusters
- **13 Kubernetes Observability Functions**: Monitor Kubernetes resources and workloads
- **15 AKS Remediation Functions**: Perform corrective actions on AKS and Kubernetes
- **4 AKS Best Practices Functions**: Assess cluster configuration and security

## Usage Pattern

All functions follow the same pattern as `app_service_tools.py`:

```python
from aks_tools import list_aks_clusters

# Create handler with auth_manager
handler = list_aks_clusters(auth_manager)

# Register with FastAPI
app.post("/tools/list_aks_clusters")(handler)
```

## Function Categories

### AKS Observability Functions

1. **list_aks_clusters** - List all AKS clusters in a subscription
2. **get_aks_status** - Get detailed status of an AKS cluster
3. **get_failing_pods** - Identify failing pods in a cluster
4. **get_pod_logs** - Retrieve logs from a specific pod
5. **get_aks_cluster_diagnostics** - Get diagnostic settings and logs
6. **get_aks_node_pool_details** - Get detailed nodepool information
7. **get_aks_networking_config** - Get network configuration details
8. **get_aks_addon_status** - Get status of AKS addons (monitoring, policy, etc.)
9. **get_aks_upgrade_history** - Get Kubernetes version upgrade history
10. **get_aks_resource_usage** - Get CPU and memory usage metrics

### Kubernetes Observability Functions

11. **list_k8s_namespaces** - List all namespaces in the cluster
12. **get_k8s_pod_status** - Get detailed pod status with events and conditions
13. **get_k8s_service_endpoints** - Get service endpoints and load balancers
14. **get_k8s_persistent_volumes** - Get persistent volume and PVC status
15. **get_k8s_secrets_configmaps** - List secrets and configmaps (names only)
16. **get_k8s_ingress_status** - Get ingress controllers and rules
17. **get_k8s_deployment_status** - Get deployment rollout status
18. **get_k8s_statefulset_status** - Get StatefulSet status
19. **get_k8s_daemonset_status** - Get DaemonSet status
20. **get_k8s_jobs_cronjobs** - Get Job and CronJob status
21. **get_k8s_node_conditions** - Get node conditions and health status
22. **get_k8s_events** - Get recent cluster events for troubleshooting

### AKS Remediation Functions

23. **scale_aks_nodepool** - Scale an AKS nodepool
24. **restart_k8s_deployment** - Restart a Kubernetes deployment
25. **cordon_node** - Mark a Kubernetes node as unschedulable
26. **uncordon_node** - Mark a Kubernetes node as schedulable
27. **update_aks_kubernetes_version** - Upgrade cluster Kubernetes version
28. **update_aks_nodepool_version** - Upgrade nodepool Kubernetes version
29. **add_aks_nodepool** - Add a new nodepool to cluster
30. **delete_aks_nodepool** - Delete a nodepool from cluster
31. **enable_aks_addon** - Enable an AKS addon
32. **disable_aks_addon** - Disable an AKS addon
33. **drain_k8s_node** - Drain a node for maintenance
34. **delete_k8s_pod** - Delete a problematic pod
35. **scale_k8s_deployment** - Scale a Kubernetes deployment
36. **rollback_k8s_deployment** - Rollback deployment to previous revision
37. **apply_k8s_manifest** - Apply a Kubernetes manifest

### AKS Best Practices Functions

38. **check_aks_best_practices** - Comprehensive best practices check
39. **check_aks_security_config** - Security configuration assessment
40. **check_aks_cost_optimization** - Cost optimization recommendations
41. **check_aks_upgrade_readiness** - Assess cluster upgrade readiness

## Security Features

### Approval Required
All remediation functions require explicit approval:
```python
request.approve = True  # Required for destructive operations
```

### Rate Limiting
Remediation functions are rate-limited to prevent abuse:
- Maximum actions per minute configurable via `MAX_ACTIONS_PER_MINUTE`
- Returns HTTP 429 when rate limit exceeded

### Action Logging
All remediation actions are logged via `log_action()`:
```python
log_action("scale_aks_nodepool", {
    "cluster": request.cluster_name,
    "nodepool": request.nodepool_name
}, success=True)
```

## Dependencies

### Azure SDK
- `azure.mgmt.containerservice.ContainerServiceClient` - AKS management
- `azure.mgmt.monitor.MonitorManagementClient` - Monitoring and diagnostics

### Models
All request models are imported from `models.py`:
- `BaseRequest`, `AKSRequest`, `AKSPodsRequest`, etc.

### Utilities
Helper functions from `utils.py`:
- `check_rate_limit()` - Rate limiting enforcement
- `log_action()` - Action logging and audit trail

## Error Handling

All functions include comprehensive error handling:
- HTTP 404 for resource not found
- HTTP 403 for approval required
- HTTP 429 for rate limit exceeded
- HTTP 500 for internal errors
- Detailed error logging for debugging

## Integration Example

```python
from fastapi import FastAPI
from aks_tools import (
    list_aks_clusters,
    get_aks_status,
    scale_aks_nodepool,
    check_aks_best_practices
)

app = FastAPI()
auth_manager = AuthManager()

# Register observability endpoints
app.post("/tools/list_aks_clusters")(list_aks_clusters(auth_manager))
app.post("/tools/get_aks_status")(get_aks_status(auth_manager))

# Register remediation endpoints
app.post("/tools/scale_aks_nodepool")(scale_aks_nodepool(auth_manager))

# Register best practices endpoints
app.post("/tools/check_aks_best_practices")(check_aks_best_practices(auth_manager))
```

## Notes

- Some Kubernetes functions require kubeconfig and direct K8s API access
- Resource usage metrics are available via Azure Monitor APIs
- Upgrade history is available via Azure Activity Log
- Best practices checks are based on Microsoft's AKS recommendations

## Future Enhancements

Potential additions:
- Direct Kubernetes API integration via kubeconfig
- Real-time metrics from Azure Monitor
- Automated remediation workflows
- Cost analysis integration
- Security policy enforcement
