# App Service Tools Module

This module contains all App Service related endpoint functions extracted from `server.py`.

## Overview

The `app_service_tools.py` module provides 33 functions organized into 4 categories:

1. **Observability Tools** (13 functions) - Monitor and inspect App Services
2. **Application Insights Tools** (5 functions) - Query and analyze telemetry data
3. **Remediation Actions** (11 functions) - Fix issues and manage App Services
4. **Best Practices Tools** (4 functions) - Assess configuration and security

## Architecture

Each function follows this pattern:

```python
def function_name(auth_manager):
    """Create route handler for <operation>"""
    async def handler(request: RequestModel):
        """<Operation description>"""
        try:
            # Implementation
            pass
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    return handler
```

## Usage in server.py

To use these functions in your FastAPI server:

```python
from fastapi import FastAPI
from auth import AuthManager
import app_service_tools

app = FastAPI()
auth_manager = AuthManager()

# Register observability tools
app.post("/tools/list_app_services")(
    app_service_tools.list_app_services(auth_manager)
)

app.post("/tools/get_app_service_state")(
    app_service_tools.get_app_service_state(auth_manager)
)

# Register remediation actions
app.post("/tools/restart_app_service")(
    app_service_tools.restart_app_service(auth_manager)
)

# And so on...
```

## Dependencies

### External Packages
- `fastapi` - Web framework
- `azure.mgmt.web` - Azure Web/App Service management
- `azure.mgmt.monitor` - Azure Monitor management

### Local Modules
- `models` - Pydantic request/response models
- `utils` - Utility functions (check_rate_limit, log_action)

## Function Categories

### 1. Observability Tools

| Function | Description | Request Model |
|----------|-------------|---------------|
| `list_app_services` | List all App Services in subscription | `BaseRequest` |
| `get_app_service_state` | Get current state of App Service | `AppServiceRequest` |
| `get_app_service_config` | Get configuration and settings | `AppServiceRequest` |
| `get_app_service_diagnostic_settings` | Get diagnostic settings | `AppServiceRequest` |
| `get_app_service_container_logs` | Get container logs info | `AppServiceRequest` |
| `get_app_service_file_system` | List files in file system | `AppServiceFileSystemRequest` |
| `get_app_service_process_list` | Get running processes | `AppServiceRequest` |
| `get_app_service_memory_dump` | Get memory metrics | `AppServiceRequest` |
| `get_app_service_instance_health` | Get instance health status | `AppServiceRequest` |
| `get_app_service_scaling_rules` | Get autoscale configuration | `AppServiceRequest` |
| `get_app_service_last_deploy` | Get last deployment info | `AppServiceRequest` |
| `get_app_service_deployment_logs` | Get deployment logs | `AppServiceRequest` |
| `get_app_service_environment_variables` | Get app settings (masked) | `AppServiceRequest` |

### 2. Application Insights Tools

| Function | Description | Request Model |
|----------|-------------|---------------|
| `query_app_insights` | Execute KQL query | `AppInsightsQueryRequest` |
| `get_recent_exceptions` | Get recent exceptions | `AppInsightsTimeRangeRequest` |
| `get_dependency_failures` | Get dependency failures | `AppInsightsTimeRangeRequest` |
| `get_slow_requests` | Get slow requests (P95) | `SlowRequestsRequest` |
| `get_availability_tests` | Get availability test results | `AppInsightsRequest` |

### 3. Remediation Actions

All remediation actions require:
- `approve=true` in the request
- Rate limit check passes
- Proper authentication

| Function | Description | Request Model |
|----------|-------------|---------------|
| `restart_app_service` | Restart App Service | `RestartAppServiceRequest` |
| `restart_app_service_slot` | Restart deployment slot | `RestartAppServiceSlotRequest` |
| `scale_app_service_plan` | Scale App Service Plan | `ScaleAppServicePlanRequest` |
| `enable_detailed_error_logs` | Enable detailed logging | `EnableDetailedErrorLogsRequest` |
| `clear_app_service_cache` | Clear cache | `ClearAppServiceCacheRequest` |
| `redeploy_last_release` | Redeploy last release | `RedeployLastReleaseRequest` |
| `swap_slots` | Swap deployment slots | `SwapSlotsRequest` |
| `reset_app_service_credentials` | Reset credentials | `ResetAppServiceCredentialsRequest` |
| `set_app_setting` | Update app setting | `SetAppSettingRequest` |
| `enable_autoscale` | Enable autoscaling | `EnableAutoscaleRequest` |
| `disable_autoscale` | Disable autoscaling | `DisableAutoscaleRequest` |

### 4. Best Practices Tools

| Function | Description | Request Model |
|----------|-------------|---------------|
| `check_app_service_best_practices` | Comprehensive best practices check | `AppServiceRequest` |
| `check_app_service_security` | Security assessment | `AppServiceRequest` |
| `check_app_service_backup_config` | Check backup configuration | `AppServiceRequest` |
| `check_app_service_monitoring` | Check monitoring setup | `AppServiceRequest` |

## Security Features

1. **Secrets Masking**: Environment variables containing keywords like 'password', 'secret', 'key', 'token', or 'connection' are automatically masked
2. **Rate Limiting**: Remediation actions are rate-limited (configurable via `MAX_ACTIONS_PER_MINUTE`)
3. **Action Logging**: All actions are logged with timestamps and parameters
4. **Approval Required**: All remediation actions require explicit approval (`approve=true`)

## Error Handling

All functions include:
- Try-catch blocks for exception handling
- Proper HTTP status codes (404 for not found, 403 for unauthorized, 429 for rate limit, 500 for server errors)
- Detailed error logging
- User-friendly error messages

## Example Request

```python
# List App Services
request = {
    "subscription_id": "your-subscription-id"
}

# Restart App Service (requires approval)
request = {
    "subscription_id": "your-subscription-id",
    "app_name": "my-app-service",
    "approve": True
}
```

## Testing

To test the module:

```bash
# Syntax check
python3 -m py_compile app_service_tools.py

# Import test (requires dependencies)
python3 -c "import app_service_tools; print('OK')"
```

## Notes

- Some functions return placeholder responses indicating additional API integration needed (e.g., Kudu API access)
- Functions that interact with Azure APIs require proper authentication via `auth_manager`
- All async handlers are compatible with FastAPI's async support
