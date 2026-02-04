"""
Utility functions for Azure Operator MCP Server
"""

import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Rate limiting storage
action_history = defaultdict(list)
MAX_ACTIONS_PER_MINUTE = int(os.getenv("MAX_ACTIONS_PER_MINUTE", "10"))


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
        "error": error
    }
    logger.info(f"ACTION LOG: {log_entry}")
