"""
Configuration Template for Intelligent Dashboard Demo App

🎯 REQUIRED: Replace placeholder values with your own

📖 How to find your IDs:
   - Dashboard ID: Open your dashboard, check URL /dashboardsv3/{YOUR_ID}
   - Genie Space ID: Open your Genie space, check URL /genie/rooms/{YOUR_ID}
   - Token: User Settings → Access Tokens → Generate New Token
   - Workspace URL: Your Databricks workspace URL (e.g., https://xxx.cloud.databricks.com)

💡 TIP: Use environment variables in production instead of hardcoding values
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file (optional)
load_dotenv()

def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables or defaults
    
    TEMPLATE USERS: Update the default values below with your own IDs
    """
    
    # ============================================================================
    # DATABASE CONFIGURATION (Optional)
    # ============================================================================
    database_config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),  # REQUIRED: Set via environment variable
        "ssl": "require"
    }
    
    # ============================================================================
    # APPLICATION CONFIGURATION
    # ============================================================================
    app_config = {
        "env": os.getenv("ENV", "development"),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "db_schema": os.getenv("DB_SCHEMA", "public")
    }
    
    # ============================================================================
    # 📊 DASHBOARD CONFIGURATION
    # ============================================================================
    dashboard_config = {
        # Your Databricks workspace URL (REQUIRED)
        "instance_url": os.getenv("DATABRICKS_INSTANCE_URL"),
        
        # Your workspace ID (REQUIRED)
        "workspace_id": os.getenv("DATABRICKS_WORKSPACE_ID"),
        
        # Your dashboard ID (REQUIRED)
        "dashboard_id": os.getenv("DATABRICKS_DASHBOARD_ID"),
        
        # Your Databricks access token (REQUIRED - NEVER commit this!)
        "token": os.getenv("DATABRICKS_DASHBOARD_TOKEN")
    }
    
    # ============================================================================
    # 🤖 GENIE AI CONFIGURATION
    # ============================================================================
    genie_config = {
        # Your Databricks workspace URL (REQUIRED)
        "instance_url": os.getenv("DATABRICKS_GENIE_INSTANCE_URL"),
        
        # Your Genie space ID (REQUIRED)
        "space_id": os.getenv("DATABRICKS_GENIE_SPACE_ID"),
        
        # Your Databricks access token (REQUIRED - NEVER commit this!)
        "token": os.getenv("DATABRICKS_GENIE_TOKEN"),
        
        # API base path
        "api_base": "/api/2.0/genie"
    }
    
    return {
        "database": database_config,
        "app": app_config,
        "dashboard": dashboard_config,
        "genie": genie_config
    }

# Load configuration
CONFIG = load_config()

# Export for easy access
DATABASE_CONFIG = CONFIG["database"]
APP_CONFIG = CONFIG["app"]
DASHBOARD_CONFIG = CONFIG["dashboard"]
GENIE_CONFIG = CONFIG["genie"]
