"""
Infrastructure Best Practices Tools for Azure Operator MCP Server
All infrastructure best practices and compliance checking functions
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.monitor import MonitorManagementClient

from models import BaseRequest, ResourceGroupRequest
from utils import check_rate_limit, log_action

logger = logging.getLogger(__name__)


# ============================================================================
# Infrastructure Best Practices Tools
# ============================================================================

def check_resource_tagging(auth_manager):
    """Create route handler for checking resource tagging compliance"""
    async def handler(request: ResourceGroupRequest):
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
    return handler


def check_network_security(auth_manager):
    """Create route handler for checking Network Security Group configurations"""
    async def handler(request: ResourceGroupRequest):
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
    return handler


def check_key_vault_security(auth_manager):
    """Create route handler for checking Key Vault security configuration"""
    async def handler(request: BaseRequest):
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
    return handler


def check_monitoring_coverage(auth_manager):
    """Create route handler for assessing monitoring coverage across resources"""
    async def handler(request: ResourceGroupRequest):
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
                except Exception:
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
    return handler


def check_resource_locks(auth_manager):
    """Create route handler for checking resource lock configuration"""
    async def handler(request: ResourceGroupRequest):
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
    return handler


def get_alerts_last_24h(auth_manager):
    """Create route handler for getting alerts fired in the last 24 hours"""
    async def handler(request: BaseRequest):
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
            except Exception:
                pass
            
            return {
                "alerts": alerts,
                "note": "Alert history requires Activity Log or Alert History API"
            }
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    return handler
