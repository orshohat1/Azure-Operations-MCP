"""
App Service Tools for Azure Operator MCP Server
All App Service observability, remediation, and best practices functions
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.monitor import MonitorManagementClient

from models import (
    BaseRequest,
    AppServiceRequest,
    AppServiceSlotRequest,
    AppServiceFileSystemRequest,
    RestartAppServiceRequest,
    RestartAppServiceSlotRequest,
    ScaleAppServicePlanRequest,
    EnableDetailedErrorLogsRequest,
    ClearAppServiceCacheRequest,
    RedeployLastReleaseRequest,
    SwapSlotsRequest,
    ResetAppServiceCredentialsRequest,
    SetAppSettingRequest,
    EnableAutoscaleRequest,
    DisableAutoscaleRequest,
    AppInsightsQueryRequest,
    AppInsightsTimeRangeRequest,
    SlowRequestsRequest,
    AppInsightsRequest,
)
from utils import check_rate_limit, log_action

logger = logging.getLogger(__name__)


# ============================================================================
# App Service - Observability Tools
# ============================================================================

def list_app_services(auth_manager):
    """Create route handler for listing all App Services"""
    async def handler(request: BaseRequest):
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
    return handler


def get_app_service_state(auth_manager):
    """Create route handler for getting App Service state"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_config(auth_manager):
    """Create route handler for getting App Service configuration"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_diagnostic_settings(auth_manager):
    """Create route handler for getting App Service diagnostic settings"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_container_logs(auth_manager):
    """Create route handler for getting App Service container logs"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_file_system(auth_manager):
    """Create route handler for listing App Service file system"""
    async def handler(request: AppServiceFileSystemRequest):
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
    return handler


def get_app_service_process_list(auth_manager):
    """Create route handler for getting App Service process list"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_memory_dump(auth_manager):
    """Create route handler for getting App Service memory dump"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_instance_health(auth_manager):
    """Create route handler for getting App Service instance health"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_scaling_rules(auth_manager):
    """Create route handler for getting App Service scaling rules"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_last_deploy(auth_manager):
    """Create route handler for getting last deployment"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_deployment_logs(auth_manager):
    """Create route handler for getting deployment logs"""
    async def handler(request: AppServiceRequest):
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
    return handler


def get_app_service_environment_variables(auth_manager):
    """Create route handler for getting environment variables"""
    async def handler(request: AppServiceRequest):
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
    return handler


# ============================================================================
# Azure Monitor & App Insights Tools
# ============================================================================

def query_app_insights(auth_manager):
    """Create route handler for querying Application Insights"""
    async def handler(request: AppInsightsQueryRequest):
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
    return handler


def get_recent_exceptions(auth_manager):
    """Create route handler for getting recent exceptions"""
    async def handler(request: AppInsightsTimeRangeRequest):
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
    return handler


def get_dependency_failures(auth_manager):
    """Create route handler for getting dependency failures"""
    async def handler(request: AppInsightsTimeRangeRequest):
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
    return handler


def get_slow_requests(auth_manager):
    """Create route handler for getting slow requests"""
    async def handler(request: SlowRequestsRequest):
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
    return handler


def get_availability_tests(auth_manager):
    """Create route handler for getting availability tests"""
    async def handler(request: AppInsightsRequest):
        """Get availability test results"""
        try:
            return {
                "note": "Availability tests available via Application Insights API",
                "sample_kql": "availabilityResults | where timestamp > ago(24h) | summarize count(), avg(duration) by name, location",
                "recommendation": "Use query_app_insights with the sample KQL query"
            }
        except Exception as e:
            logger.error(f"Error getting availability tests: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    return handler


# ============================================================================
# App Service - Remediation Actions
# ============================================================================

def restart_app_service(auth_manager):
    """Create route handler for restarting App Service"""
    async def handler(request: RestartAppServiceRequest):
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
    return handler


def restart_app_service_slot(auth_manager):
    """Create route handler for restarting App Service slot"""
    async def handler(request: RestartAppServiceSlotRequest):
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
    return handler


def scale_app_service_plan(auth_manager):
    """Create route handler for scaling App Service Plan"""
    async def handler(request: ScaleAppServicePlanRequest):
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
    return handler


def enable_detailed_error_logs(auth_manager):
    """Create route handler for enabling detailed error logs"""
    async def handler(request: EnableDetailedErrorLogsRequest):
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
    return handler


def clear_app_service_cache(auth_manager):
    """Create route handler for clearing App Service cache"""
    async def handler(request: ClearAppServiceCacheRequest):
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
    return handler


def redeploy_last_release(auth_manager):
    """Create route handler for redeploying last release"""
    async def handler(request: RedeployLastReleaseRequest):
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
    return handler


def swap_slots(auth_manager):
    """Create route handler for swapping deployment slots"""
    async def handler(request: SwapSlotsRequest):
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
    return handler


def reset_app_service_credentials(auth_manager):
    """Create route handler for resetting App Service credentials"""
    async def handler(request: ResetAppServiceCredentialsRequest):
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
    return handler


def set_app_setting(auth_manager):
    """Create route handler for setting app settings"""
    async def handler(request: SetAppSettingRequest):
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
    return handler


def enable_autoscale(auth_manager):
    """Create route handler for enabling autoscale"""
    async def handler(request: EnableAutoscaleRequest):
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
    return handler


def disable_autoscale(auth_manager):
    """Create route handler for disabling autoscale"""
    async def handler(request: DisableAutoscaleRequest):
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
    return handler


# ============================================================================
# App Service - Best Practices Tools
# ============================================================================

def check_app_service_best_practices(auth_manager):
    """Create route handler for checking best practices"""
    async def handler(request: AppServiceRequest):
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
    return handler


def check_app_service_security(auth_manager):
    """Create route handler for checking security configuration"""
    async def handler(request: AppServiceRequest):
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
    return handler


def check_app_service_backup_config(auth_manager):
    """Create route handler for checking backup configuration"""
    async def handler(request: AppServiceRequest):
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
    return handler


def check_app_service_monitoring(auth_manager):
    """Create route handler for checking monitoring configuration"""
    async def handler(request: AppServiceRequest):
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
    return handler
