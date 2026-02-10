"""
Authentication management for Azure Operator MCP Server
"""

import os
import logging
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


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
