from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import os
import logging
import httpx
import json
from datetime import datetime
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    asyncpg = None

try:
    from databricks import sql as databricks_sql
    DATABRICKS_SQL_AVAILABLE = True
except ImportError:
    DATABRICKS_SQL_AVAILABLE = False
    databricks_sql = None

import asyncio
import subprocess
from config import DATABASE_CONFIG, APP_CONFIG, DASHBOARD_CONFIG, GENIE_CONFIG

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration loaded from environment variables
# See config.py for configuration management

# Database connection pool
db_pool = None

# Warehouse feature removed - using database only

async def init_db_pool():
    """Initialize database connection pool"""
    global db_pool
    
    if not ASYNCPG_AVAILABLE:
        logger.warning("asyncpg not available - running in development mode without database")
        return
    
    try:
        db_pool = await asyncpg.create_pool(
            host=DATABASE_CONFIG["host"],
            port=DATABASE_CONFIG["port"],
            database=DATABASE_CONFIG["database"],
            user=DATABASE_CONFIG["user"],
            password=DATABASE_CONFIG["password"],
            ssl="require",
            min_size=1,
            max_size=5
        )
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database pool: {e}")
        logger.warning("Continuing without database connection - will use sample data")

async def close_db_pool():
    """Close database connection pool"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")

# Warehouse functions removed

# Databricks access token function removed - was only used for warehouse

# Warehouse query function removed

# Warehouse mapping function removed



app = FastAPI(
    title="Danone POS Analytics",
    description="Point of Sales Data Visualization for Danone",
    version="1.0.0"
)

# Startup and shutdown events
@app.on_event("startup")
async def startup():
    await init_db_pool()
    # Database tables and data prepared during deployment
    if db_pool:
        logger.info("📊 Database ready - tables and data populated during deployment")

@app.on_event("shutdown")
async def shutdown():
    await close_db_pool()

# Add CORS middleware for Databricks Apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all for development
        "https://*.databricksapps.com",  # Databricks Apps domains
        "https://*.azuredatabricksapps.com",  # Azure Databricks Apps domains
        "https://*.gcp.databricksapps.com",  # GCP Databricks Apps domains
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "app": "Danone POS Analytics"}

# Database health check endpoint
@app.get("/health/database")
async def database_health_check():
    """Check database connectivity and basic functionality"""
    global db_pool
    
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "database": {
            "status": "unknown",
            "connection": False,
            "asyncpg_available": ASYNCPG_AVAILABLE,
            "pool_status": bool(db_pool),
            "test_query": False,
            "schema_access": False,
            "table_access": False,
            "data_count": 0
        },
        "overall_status": "unhealthy"
    }
    
    # Check if asyncpg is available
    if not ASYNCPG_AVAILABLE:
        health_status["database"]["status"] = "asyncpg_not_available"
        health_status["database"]["message"] = "asyncpg module not available - using sample data"
        health_status["overall_status"] = "degraded"
        return health_status
    
    # Check if database pool exists
    if not db_pool:
        health_status["database"]["status"] = "no_connection_pool"
        health_status["database"]["message"] = "Database connection pool not initialized - using sample data"
        health_status["overall_status"] = "degraded"
        return health_status
    
    try:
        async with db_pool.acquire() as conn:
            health_status["database"]["connection"] = True
            
            # Test basic query
            try:
                result = await conn.fetchval("SELECT 1")
                health_status["database"]["test_query"] = True
            except Exception as e:
                health_status["database"]["test_query_error"] = str(e)
            
            # Test schema access
            try:
                schema_result = await conn.fetchval("""
                    SELECT COUNT(*) FROM information_schema.schemata 
                    WHERE schema_name = 'public'
                """)
                health_status["database"]["schema_access"] = schema_result > 0
            except Exception as e:
                health_status["database"]["schema_error"] = str(e)
            
            # Test table access and data count
            try:
                count_result = await conn.fetchval("""
                    SELECT COUNT(*) FROM public.businesses 
                    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                """)
                health_status["database"]["table_access"] = True
                health_status["database"]["data_count"] = count_result
            except Exception as e:
                health_status["database"]["table_error"] = str(e)
            
            # Determine overall status
            if (health_status["database"]["test_query"] and 
                health_status["database"]["schema_access"] and 
                health_status["database"]["table_access"]):
                health_status["database"]["status"] = "healthy"
                health_status["overall_status"] = "healthy"
            else:
                health_status["database"]["status"] = "partial"
                health_status["overall_status"] = "degraded"
                
    except Exception as e:
        health_status["database"]["status"] = "connection_failed"
        health_status["database"]["error"] = str(e)
        health_status["database"]["message"] = "Database connection failed - using sample data"
        health_status["overall_status"] = "degraded"
    
    return health_status

# Enhanced Claude connectivity and authentication diagnostics
@app.get("/health/claude")
async def claude_health_check(request: Request):
    """Comprehensive Claude endpoint and authentication diagnostics per Databricks recommendations"""
    
    # Step 1: Extract all possible authentication tokens and headers
    user_obo_token = request.headers.get("x-forwarded-access-token")
    user_obo_token_alt = request.headers.get("X-Forwarded-Access-Token") 
    auth_header = request.headers.get("authorization", "")
    auth_header_alt = request.headers.get("Authorization", "")
    
    # Step 2: Determine authentication flow
    auth_flow_type = "unknown"
    active_token = None
    
    if user_obo_token or user_obo_token_alt:
        auth_flow_type = "user_obo"  # On-Behalf-Of (user token passthrough)
        active_token = user_obo_token or user_obo_token_alt
    elif auth_header.startswith("Bearer ") or auth_header_alt.startswith("Bearer "):
        auth_flow_type = "service_principal"  # Service principal token
        active_token = auth_header.replace("Bearer ", "") or auth_header_alt.replace("Bearer ", "")
    
    # Step 3: Comprehensive diagnostics result
    result = {
        "timestamp": datetime.now().isoformat(),
        "claude_endpoint": CLAUDE_ENDPOINT,
        "authentication_analysis": {
            "flow_type": auth_flow_type,
            "token_present": bool(active_token),
            "token_length": len(active_token) if active_token else 0,
            "token_prefix": active_token[:20] + "..." if active_token and len(active_token) > 20 else None,
            "user_obo_header": bool(user_obo_token or user_obo_token_alt),
            "service_principal_header": bool(auth_header.startswith("Bearer ") or auth_header_alt.startswith("Bearer ")),
        },
        "headers_analysis": {
            "total_headers": len(request.headers),
            "auth_related_headers": [h for h in request.headers.keys() if any(x in h.lower() for x in ['auth', 'token', 'forward'])],
            "all_headers": dict(request.headers.items()),
        },
        "databricks_troubleshooting": {
            "step_1_auth_flow": f"Using {auth_flow_type} authentication flow",
            "step_2_oauth_scopes": "Check if app has 'serving.serving-endpoints' or 'all-apis' scope",
            "step_3_permissions": "Verify 'Can Query' permission on Claude endpoint",
            "step_4_logs": "Check workspace audit logs for 'serverlessRealTimeInference' events",
        },
        "status": "diagnostics_complete"
    }
    
    if not active_token:
        result["status"] = "no_token"
        result["error"] = "No authentication token found in any expected headers"
        result["next_steps"] = [
            "Verify app OAuth configuration includes required scopes",
            "Check if user needs to re-consent to app permissions",
            "Ensure app is properly deployed with authentication enabled"
        ]
        return result
    
    # Step 4: Test Claude connectivity with detailed error analysis
    try:
        logger.info(f"Testing Claude connectivity with {auth_flow_type} token")
        test_response = await call_claude_api(active_token, "Hello, please respond with 'Claude is working'")
        
        result["status"] = "success"
        result["claude_test"] = {
            "response_received": True,
            "response_length": len(test_response),
            "response_preview": test_response[:200] + "..." if len(test_response) > 200 else test_response
        }
        result["message"] = f"Claude endpoint accessible via {auth_flow_type} authentication"
        
    except httpx.HTTPStatusError as e:
        result["status"] = "http_error"
        result["error"] = {
            "status_code": e.response.status_code,
            "error_type": "HTTPStatusError",
            "error_message": str(e),
            "response_text": e.response.text if hasattr(e.response, 'text') else "No response text",
        }
        
        # Enhanced 403 error analysis per Databricks recommendations
        if e.response.status_code == 403:
            result["error"]["databricks_403_analysis"] = {
                "likely_causes": [
                    "Missing 'serving.serving-endpoints' or 'all-apis' OAuth scope",
                    "User token lacks 'Can Query' permission on Claude endpoint",
                    "Stale OAuth scopes - app needs restart and user re-consent",
                    "Service principal lacks proper endpoint permissions"
                ],
                "immediate_actions": [
                    "Check app OAuth configuration in Databricks workspace",
                    "Verify user has 'Can Query' access to databricks-claude-3-7-sonnet endpoint",
                    "Try restarting app and clearing browser cache/cookies",
                    "Test with different user or service principal"
                ],
                "auth_flow_specific": {
                    auth_flow_type: "Current authentication method - verify permissions for this specific flow"
                }
            }
            
    except Exception as e:
        result["status"] = "connection_error"
        result["error"] = {
            "error_type": type(e).__name__,
            "error_message": str(e),
            "troubleshooting": [
                "Verify Claude endpoint URL is correct",
                "Check network connectivity from Databricks Apps",
                "Confirm endpoint is active and accepting requests"
            ]
        }
    
    return result

# OAuth scope and permission testing endpoint
@app.get("/diagnostic/oauth-test")
async def oauth_scope_test(request: Request):
    """Test OAuth scopes and permissions per Databricks troubleshooting recommendations"""
    
    # Extract authentication information
    user_obo_token = request.headers.get("x-forwarded-access-token")
    user_obo_token_alt = request.headers.get("X-Forwarded-Access-Token") 
    auth_header = request.headers.get("authorization", "")
    service_principal_token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "test_summary": "OAuth scope and authentication flow testing",
        "databricks_recommendations": {
            "step_1": "Triple-check Authentication Flow and Identity",
            "step_2": "Validate OAuth Scopes (serving.serving-endpoints or all-apis)",
            "step_3": "Check Behavior Using Both Auth Flows",
            "step_4": "Look at Workspace/Endpoint Logs"
        },
        "tests": {}
    }
    
    # Test 1: User OBO (On-Behalf-Of) flow
    if user_obo_token or user_obo_token_alt:
        token = user_obo_token or user_obo_token_alt
        results["tests"]["user_obo_flow"] = {
            "available": True,
            "token_length": len(token),
            "token_prefix": token[:20] + "..." if len(token) > 20 else token,
            "description": "Using user's delegated token (x-forwarded-access-token)",
            "requirements": [
                "User must have 'Can Query' permission on Claude endpoint",
                "App OAuth config must include 'serving.serving-endpoints' or 'all-apis' scope"
            ]
        }
        
        # Test Claude access with user token
        try:
            logger.info("Testing Claude access with user OBO token")
            test_result = await call_claude_api(token, "Test: OAuth scope validation")
            results["tests"]["user_obo_flow"]["claude_test"] = {
                "status": "success",
                "response_preview": test_result[:100] + "..." if len(test_result) > 100 else test_result
            }
        except Exception as e:
            results["tests"]["user_obo_flow"]["claude_test"] = {
                "status": "failed",
                "error": str(e),
                "troubleshooting": [
                    "Check user's 'Can Query' permission on databricks-claude-3-7-sonnet",
                    "Verify app OAuth scopes include required permissions",
                    "Try user re-consent to app"
                ]
            }
    else:
        results["tests"]["user_obo_flow"] = {
            "available": False,
            "description": "No x-forwarded-access-token header found",
            "implications": "App is not using user delegation (OBO) flow"
        }
    
    # Test 2: Service Principal flow
    if service_principal_token:
        results["tests"]["service_principal_flow"] = {
            "available": True,
            "token_length": len(service_principal_token),
            "token_prefix": service_principal_token[:20] + "..." if len(service_principal_token) > 20 else service_principal_token,
            "description": "Using app's service principal token (Authorization header)",
            "requirements": [
                "Service principal must have 'Can Query' permission on Claude endpoint",
                "App must be configured to use service principal authentication"
            ]
        }
        
        # Test Claude access with service principal token
        try:
            logger.info("Testing Claude access with service principal token")
            test_result = await call_claude_api(service_principal_token, "Test: Service principal access")
            results["tests"]["service_principal_flow"]["claude_test"] = {
                "status": "success",
                "response_preview": test_result[:100] + "..." if len(test_result) > 100 else test_result
            }
        except Exception as e:
            results["tests"]["service_principal_flow"]["claude_test"] = {
                "status": "failed",
                "error": str(e),
                "troubleshooting": [
                    "Check service principal permissions on databricks-claude-3-7-sonnet",
                    "Verify app deployment configuration",
                    "Check app OAuth configuration"
                ]
            }
    else:
        results["tests"]["service_principal_flow"] = {
            "available": False,
            "description": "No Authorization: Bearer header found",
            "implications": "App is not using service principal authentication"
        }
    
    # Summary and recommendations
    user_available = results["tests"]["user_obo_flow"]["available"]
    sp_available = results["tests"]["service_principal_flow"]["available"]
    
    if not user_available and not sp_available:
        results["recommendation"] = {
            "priority": "high",
            "action": "No valid authentication tokens found",
            "steps": [
                "Check app OAuth configuration in Databricks workspace",
                "Verify app deployment includes authentication setup",
                "Ensure proper scopes are configured",
                "Try restarting the app"
            ]
        }
    elif user_available and not sp_available:
        results["recommendation"] = {
            "priority": "medium", 
            "action": "Using user delegation (OBO) flow only",
            "steps": [
                "This is normal for user-facing apps",
                "Focus on user permissions and OAuth scopes",
                "Verify 'serving.serving-endpoints' scope is included"
            ]
        }
    elif not user_available and sp_available:
        results["recommendation"] = {
            "priority": "medium",
            "action": "Using service principal flow only", 
            "steps": [
                "This is normal for backend-only apps",
                "Focus on service principal permissions",
                "Verify service principal has Claude endpoint access"
            ]
        }
    else:
        results["recommendation"] = {
            "priority": "low",
            "action": "Both authentication flows available",
            "steps": [
                "Compare test results to identify which flow is failing",
                "Focus troubleshooting on the failing authentication method",
                "Consider using the working method as primary"
            ]
        }
    
    return results

# API endpoint to get user info (for Databricks authentication)
@app.get("/api/user")
async def get_user_info(request: Request):
    """Get user information from Databricks headers"""
    user_token = request.headers.get("x-forwarded-access-token")
    user_email = request.headers.get("x-forwarded-user")
    
    logger.info(f"User access: {user_email}")
    
    return {
        "authenticated": bool(user_token),
        "user_email": user_email or "anonymous",
        "has_token": bool(user_token)
    }

# Sample API endpoint for POS data (can be extended for real data integration)
@app.get("/api/pos-data")
async def get_pos_data(request: Request):
    """Get POS data - placeholder for real Databricks data integration"""
    user_token = request.headers.get("x-forwarded-access-token")
    
    if not user_token:
        return {"error": "Authentication required"}
    
    # In a real scenario, you would use the user_token to query Databricks APIs
    # For now, return success status
    return {
        "status": "success",
        "message": "POS data endpoint ready for integration",
        "data_source": "sample_data"
    }

@app.get("/api/pos-submissions")
async def get_pos_submissions(request: Request):
    """Get business data from Databricks Postgres database"""
    global db_pool
    
    # If no database connection, return sample data
    if not db_pool or not ASYNCPG_AVAILABLE:
        logger.info("No database connection available, returning sample data")
        sample_data = generate_sample_pos_data()
        return {
            "status": "success",
            "data": sample_data,
            "count": len(sample_data),
            "data_source": "sample_data",
            "retrieved_at": datetime.now().isoformat(),
            "note": "Using sample data - database not available"
        }
    
    try:
        async with db_pool.acquire() as conn:
            # Query the businesses table in the public schema
            query = """
                SELECT 
                    id,
                    name,
                    type,
                    address,
                    latitude,
                    longitude,
                    is_danone_customer,
                    last_photo_date,
                    menu_items,
                    created_at,
                    updated_at
                FROM public.businesses
                WHERE latitude IS NOT NULL 
                  AND longitude IS NOT NULL
                ORDER BY last_photo_date DESC NULLS LAST, created_at DESC
            """
            
            rows = await conn.fetch(query)
            
            # Transform database rows to POS data format
            pos_data = []
            for row in rows:
                # Parse menu_items if it's JSON
                menu_items = []
                if row['menu_items']:
                    try:
                        if isinstance(row['menu_items'], str):
                            menu_items = json.loads(row['menu_items'])
                        else:
                            menu_items = row['menu_items']
                    except json.JSONDecodeError:
                        menu_items = []
                
                # Map menu items to standard product families
                product_families = []
                total_items = 0
                total_value = 0
                
                for item in menu_items:
                    if isinstance(item, dict):
                        category = item.get('category', '').lower()
                        product_name = item.get('productName', '').lower()
                        price_str = item.get('detectedPrice', '€0')
                        times_detected = item.get('timesDetected', 1)
                        
                        # Extract price value
                        try:
                            price_value = float(price_str.replace('€', '').replace(',', '.'))
                            total_value += price_value * times_detected
                            total_items += times_detected
                        except:
                            pass
                        
                        # Map to Danone product families based on category and product name
                        if 'water' in category or any(keyword in product_name for keyword in ['evian', 'volvic', 'badoit']):
                            product_families.append('Waters')
                        elif 'yogurt' in category or 'yoghurt' in category or 'dessert' in category:
                            product_families.append('Yogurt & Desserts')
                        elif any(keyword in product_name for keyword in ['baby', 'infant', 'formula']):
                            product_families.append('Baby Nutrition')
                        elif any(keyword in product_name for keyword in ['plant', 'oat', 'almond', 'soy']):
                            product_families.append('Plant-Based')
                        elif any(keyword in product_name for keyword in ['medical', 'nutrition', 'health']):
                            product_families.append('Medical Nutrition')
                        else:
                            product_families.append('Dairy Alternatives')
                
                # Remove duplicates and ensure at least one product family
                product_families = list(set(product_families))
                if not product_families:
                    product_families = ['Waters']  # Default for businesses
                
                # Use business type from database or map from name
                business_type = row['type'] or 'Restaurant'  # Default
                if not business_type or business_type.lower() == 'unknown':
                    business_name_lower = (row['name'] or '').lower()
                    if any(keyword in business_name_lower for keyword in ['hypermarket', 'hyper']):
                        business_type = 'Hypermarket'
                    elif any(keyword in business_name_lower for keyword in ['supermarket', 'super']):
                        business_type = 'Supermarket'
                    elif any(keyword in business_name_lower for keyword in ['convenience', 'corner', 'mini']):
                        business_type = 'Convenience Store'
                    elif any(keyword in business_name_lower for keyword in ['pharmacy', 'pharma']):
                        business_type = 'Pharmacy'
                    elif any(keyword in business_name_lower for keyword in ['café', 'cafe', 'restaurant', 'bistro']):
                        business_type = 'Restaurant'
                    else:
                        business_type = 'Restaurant'
                
                # Calculate estimated sales volume based on menu items and business type
                base_volume = max(total_value * 100, 10000)  # Base estimation from menu pricing
                if business_type == 'Hypermarket':
                    sales_volume = base_volume * 4
                elif business_type == 'Supermarket':
                    sales_volume = base_volume * 2
                elif business_type == 'Restaurant':
                    sales_volume = base_volume * 1.5
                else:
                    sales_volume = base_volume
                
                # Calculate points based on customer status and menu items
                points_earned = 0
                if row['is_danone_customer']:
                    points_earned += 50
                points_earned += len(menu_items) * 10  # 10 points per menu item
                
                pos_data.append({
                    "id": f"biz_{row['id']}",
                    "name": row['name'] or f"Business {row['id']}",
                    "latitude": float(row['latitude']),
                    "longitude": float(row['longitude']),
                    "businessType": business_type,
                    "productFamilies": product_families,
                    "salesVolume": int(sales_volume),
                    "city": extract_city_from_address(row['address']),
                    "country": extract_country_from_address(row['address']),
                    "address": row['address'] or '',
                    "submissionData": {
                        "user_name": "Scout Network",
                        "photo_url": None,
                        "points_earned": points_earned,
                        "submitted_at": row['last_photo_date'].isoformat() if row['last_photo_date'] else None,
                        "detected_products": menu_items,
                        "is_danone_customer": row['is_danone_customer'],
                        "menu_items": menu_items,
                        "total_menu_items": len(menu_items),
                        "last_updated": row['last_photo_date'].isoformat() if row['last_photo_date'] else None
                    }
                })
            
            logger.info(f"Retrieved {len(pos_data)} submissions from database")
            
            return {
                "status": "success",
                "data": pos_data,
                "count": len(pos_data),
                "data_source": "databricks_postgres",
                "retrieved_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Database query error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Enhanced Analytics Endpoints

@app.get("/api/analytics/volume")
async def get_volume_analytics(request: Request):
    """Get volume analytics data for dashboard"""
    global db_pool
    
    if not db_pool:
        return {"error": "Database not available", "data": []}
    
    try:
        async with db_pool.acquire() as conn:
            # Debug database connection
            current_user = await conn.fetchval("SELECT current_user")
            database_name = await conn.fetchval("SELECT current_database()")
            logger.info(f"🔍 Volume analytics - DB: user='{current_user}', database='{database_name}'")
            
            # Check if volume_analytics table exists
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'volume_analytics'
                )
            """)
            logger.info(f"📊 volume_analytics table exists: {table_exists}")
            
            if not table_exists:
                logger.error("❌ volume_analytics table does not exist!")
                return {"error": "volume_analytics table not found", "data": []}
            # Get volume data by month and region
            query = """
                SELECT 
                    month,
                    region,
                    country,
                    business_type,
                    SUM(volume_sold) as total_volume,
                    SUM(revenue) as total_revenue,
                    COUNT(DISTINCT business_id) as business_count,
                    AVG(volume_sold) as avg_volume_per_business
                FROM public.volume_analytics
                GROUP BY month, region, country, business_type
                ORDER BY month DESC, total_volume DESC
            """
            
            rows = await conn.fetch(query)
            
            volume_data = []
            for row in rows:
                volume_data.append({
                    "month": row["month"],
                    "region": row["region"],
                    "country": row["country"],
                    "business_type": row["business_type"],
                    "total_volume": int(row["total_volume"]),
                    "total_revenue": float(row["total_revenue"]),
                    "business_count": int(row["business_count"]),
                    "avg_volume_per_business": float(row["avg_volume_per_business"])
                })
            
            return {
                "status": "success",
                "data": volume_data,
                "retrieved_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Volume analytics error: {e}")
        return {"error": str(e), "data": []}

@app.get("/api/analytics/competition")
async def get_competition_analytics(request: Request):
    """Get competition analysis data"""
    global db_pool
    
    if not db_pool:
        return {"error": "Database not available", "data": []}
    
    try:
        async with db_pool.acquire() as conn:
            # Get competition data with market share and pricing analysis
            query = """
                SELECT 
                    danone_product,
                    competitor_brand,
                    region,
                    AVG(danone_price) as avg_danone_price,
                    AVG(competitor_price) as avg_competitor_price,
                    AVG(price_difference) as avg_price_difference,
                    AVG(market_share) as avg_market_share,
                    COUNT(*) as occurrence_count,
                    SUM(CASE WHEN availability THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as availability_rate
                FROM public.competition_analytics
                GROUP BY danone_product, competitor_brand, region
                ORDER BY avg_market_share DESC, occurrence_count DESC
            """
            
            rows = await conn.fetch(query)
            
            competition_data = []
            for row in rows:
                competition_data.append({
                    "danone_product": row["danone_product"],
                    "competitor_brand": row["competitor_brand"],
                    "region": row["region"],
                    "avg_danone_price": round(float(row["avg_danone_price"]), 2),
                    "avg_competitor_price": round(float(row["avg_competitor_price"]), 2),
                    "avg_price_difference": round(float(row["avg_price_difference"]), 2),
                    "avg_market_share": round(float(row["avg_market_share"]) * 100, 1),
                    "occurrence_count": int(row["occurrence_count"]),
                    "availability_rate": round(float(row["availability_rate"]) * 100, 1)
                })
            
            return {
                "status": "success",
                "data": competition_data,
                "retrieved_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Competition analytics error: {e}")
        return {"error": str(e), "data": []}

@app.get("/api/analytics/pricing")
async def get_pricing_analytics(request: Request):
    """Get pricing evolution and margin analysis"""
    global db_pool
    
    if not db_pool:
        return {"error": "Database not available", "data": []}
    
    try:
        async with db_pool.acquire() as conn:
            # Get pricing trends and margin analysis
            query = """
                SELECT 
                    product_name,
                    product_category,
                    month,
                    region,
                    business_type,
                    AVG(retail_price) as avg_retail_price,
                    AVG(supplier_cost) as avg_supplier_cost,
                    AVG(margin) as avg_margin,
                    AVG(price_vs_rrp) as avg_price_vs_rrp,
                    COUNT(*) as sample_size
                FROM public.price_evolution
                GROUP BY product_name, product_category, month, region, business_type
                ORDER BY month DESC, product_name, region
            """
            
            rows = await conn.fetch(query)
            
            pricing_data = []
            for row in rows:
                pricing_data.append({
                    "product_name": row["product_name"],
                    "product_category": row["product_category"],
                    "month": row["month"],
                    "region": row["region"],
                    "business_type": row["business_type"],
                    "avg_retail_price": round(float(row["avg_retail_price"]), 2),
                    "avg_supplier_cost": round(float(row["avg_supplier_cost"]), 2),
                    "avg_margin": round(float(row["avg_margin"]), 1),
                    "avg_price_vs_rrp": round(float(row["avg_price_vs_rrp"]), 1),
                    "sample_size": int(row["sample_size"])
                })
            
            return {
                "status": "success",
                "data": pricing_data,
                "retrieved_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Pricing analytics error: {e}")
        return {"error": str(e), "data": []}

@app.get("/api/analytics/summary")
async def get_analytics_summary(request: Request):
    """Get comprehensive analytics summary for dashboard"""
    global db_pool
    
    if not db_pool:
        return {"error": "Database not available", "data": {}}
    
    try:
        async with db_pool.acquire() as conn:
            # Get key metrics summary
            volume_summary = await conn.fetchrow("""
                SELECT 
                    SUM(volume_sold) as total_volume,
                    SUM(revenue) as total_revenue,
                    COUNT(DISTINCT business_id) as total_businesses,
                    AVG(volume_sold) as avg_volume_per_business
                FROM public.volume_analytics
                WHERE month >= (SELECT MAX(month) FROM public.volume_analytics)
            """)
            
            competition_summary = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT competitor_brand) as competitor_count,
                    AVG(price_difference) as avg_price_difference,
                    AVG(market_share) as avg_competitor_market_share
                FROM public.competition_analytics
            """)
            
            pricing_summary = await conn.fetchrow("""
                SELECT 
                    AVG(margin) as avg_margin,
                    AVG(price_vs_rrp) as avg_price_vs_rrp,
                    COUNT(DISTINCT product_name) as products_tracked
                FROM public.price_evolution
                WHERE month >= (SELECT MAX(month) FROM public.price_evolution)
            """)
            
            # Get top performing regions
            top_regions = await conn.fetch("""
                SELECT 
                    region,
                    SUM(volume_sold) as total_volume,
                    SUM(revenue) as total_revenue
                FROM public.volume_analytics
                WHERE month >= (SELECT MAX(month) FROM public.volume_analytics)
                GROUP BY region
                ORDER BY total_volume DESC
                LIMIT 5
            """)
            
            summary = {
                "volume_metrics": {
                    "total_volume": int(volume_summary["total_volume"] or 0),
                    "total_revenue": round(float(volume_summary["total_revenue"] or 0), 2),
                    "total_businesses": int(volume_summary["total_businesses"] or 0),
                    "avg_volume_per_business": round(float(volume_summary["avg_volume_per_business"] or 0), 0)
                },
                "competition_metrics": {
                    "competitor_count": int(competition_summary["competitor_count"] or 0),
                    "avg_price_difference": round(float(competition_summary["avg_price_difference"] or 0), 2),
                    "avg_competitor_market_share": round(float(competition_summary["avg_competitor_market_share"] or 0) * 100, 1)
                },
                "pricing_metrics": {
                    "avg_margin": round(float(pricing_summary["avg_margin"] or 0), 1),
                    "avg_price_vs_rrp": round(float(pricing_summary["avg_price_vs_rrp"] or 0), 1),
                    "products_tracked": int(pricing_summary["products_tracked"] or 0)
                },
                "top_regions": [
                    {
                        "region": row["region"],
                        "total_volume": int(row["total_volume"]),
                        "total_revenue": round(float(row["total_revenue"]), 2)
                    } for row in top_regions
                ]
            }
            
            return {
                "status": "success",
                "data": summary,
                "retrieved_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Analytics summary error: {e}")
        return {"error": str(e), "data": {}}

@app.get("/api/dashboard/config")
async def get_dashboard_config(request: Request):
    """Get Databricks dashboard configuration for embedded dashboard"""
    try:
        return {
            "status": "success",
            "data": {
                "instance_url": DASHBOARD_CONFIG["instance_url"],
                "workspace_id": DASHBOARD_CONFIG["workspace_id"],
                "dashboard_id": DASHBOARD_CONFIG["dashboard_id"],
                "token": DASHBOARD_CONFIG["token"],
                "embed_url": f"{DASHBOARD_CONFIG['instance_url']}/embed/dashboardsv3/{DASHBOARD_CONFIG['dashboard_id']}?o={DASHBOARD_CONFIG['workspace_id']}"
            },
            "retrieved_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Dashboard config error: {e}")
        return {"error": str(e), "data": {}}

# Genie API endpoints
@app.post("/api/genie/conversations/start")
async def start_genie_conversation(request: Request):
    """Start a new conversation with Genie"""
    try:
        data = await request.json()
        content = data.get("content", "")
        
        if not content:
            return {"error": "Content is required", "data": None}
        
        # Make request to Databricks Genie API
        genie_url = f"{GENIE_CONFIG['instance_url']}{GENIE_CONFIG['api_base']}/spaces/{GENIE_CONFIG['space_id']}/start-conversation"
        
        headers = {
            "Authorization": f"Bearer {GENIE_CONFIG['token']}",
            "Content-Type": "application/json"
        }
        
        payload = {"content": content}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(genie_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Genie API error: {response.status_code} - {response.text}")
                return {"error": f"Genie API error: {response.status_code}", "data": None}
                
    except Exception as e:
        logger.error(f"Start conversation error: {e}")
        return {"error": str(e), "data": None}

@app.get("/api/genie/conversations/{conversation_id}/messages/{message_id}")
async def get_genie_message(conversation_id: str, message_id: str, request: Request):
    """Get a specific message from a Genie conversation"""
    try:
        genie_url = f"{GENIE_CONFIG['instance_url']}{GENIE_CONFIG['api_base']}/spaces/{GENIE_CONFIG['space_id']}/conversations/{conversation_id}/messages/{message_id}"
        
        headers = {
            "Authorization": f"Bearer {GENIE_CONFIG['token']}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(genie_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Genie API error: {response.status_code} - {response.text}")
                return {"error": f"Genie API error: {response.status_code}", "data": None}
                
    except Exception as e:
        logger.error(f"Get message error: {e}")
        return {"error": str(e), "data": None}

@app.get("/api/genie/conversations/{conversation_id}/messages/{message_id}/query-result/{attachment_id}")
async def get_genie_query_result(conversation_id: str, message_id: str, attachment_id: str, request: Request):
    """Get query results from a Genie message attachment"""
    try:
        genie_url = f"{GENIE_CONFIG['instance_url']}{GENIE_CONFIG['api_base']}/spaces/{GENIE_CONFIG['space_id']}/conversations/{conversation_id}/messages/{message_id}/query-result/{attachment_id}"
        
        headers = {
            "Authorization": f"Bearer {GENIE_CONFIG['token']}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:  # Longer timeout for query results
            response = await client.get(genie_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Genie API error: {response.status_code} - {response.text}")
                return {"error": f"Genie API error: {response.status_code}", "data": None}
                
    except Exception as e:
        logger.error(f"Get query result error: {e}")
        return {"error": str(e), "data": None}

@app.post("/api/genie/conversations/{conversation_id}/messages")
async def send_genie_followup(conversation_id: str, request: Request):
    """Send a follow-up message in an existing Genie conversation"""
    try:
        data = await request.json()
        content = data.get("content", "")
        
        if not content:
            return {"error": "Content is required", "data": None}
        
        genie_url = f"{GENIE_CONFIG['instance_url']}{GENIE_CONFIG['api_base']}/spaces/{GENIE_CONFIG['space_id']}/conversations/{conversation_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {GENIE_CONFIG['token']}",
            "Content-Type": "application/json"
        }
        
        payload = {"content": content}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(genie_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "status": "success",
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                logger.error(f"Genie API error: {response.status_code} - {response.text}")
                return {"error": f"Genie API error: {response.status_code}", "data": None}
                
    except Exception as e:
        logger.error(f"Send followup error: {e}")
        return {"error": str(e), "data": None}

@app.get("/api/genie/config")
async def get_genie_config(request: Request):
    """Get Genie configuration for frontend"""
    try:
        return {
            "status": "success",
            "data": {
                "space_id": GENIE_CONFIG["space_id"],
                "instance_url": GENIE_CONFIG["instance_url"],
                "space_url": f"{GENIE_CONFIG['instance_url']}/genie/rooms/{GENIE_CONFIG['space_id']}"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Genie config error: {e}")
        return {"error": str(e), "data": {}}

def extract_city_from_address(address: Optional[str]) -> str:
    """Extract city from address string"""
    if not address:
        return "Unknown"
    
    # Simple extraction - could be improved with more sophisticated parsing
    parts = address.split(',')
    if len(parts) >= 2:
        return parts[-2].strip()
    return address.split(' ')[-1] if address else "Unknown"

def extract_country_from_address(address: Optional[str]) -> str:
    """Extract country from address string"""
    if not address:
        return "Unknown"
    
    # Simple extraction - could be improved with more sophisticated parsing
    parts = address.split(',')
    if len(parts) >= 1:
        last_part = parts[-1].strip().upper()
        # Map common country codes/names
        country_map = {
            'FR': 'France', 'FRANCE': 'France',
            'DE': 'Germany', 'GERMANY': 'Germany', 'DEUTSCHLAND': 'Germany',
            'UK': 'United Kingdom', 'GB': 'United Kingdom', 'UNITED KINGDOM': 'United Kingdom',
            'ES': 'Spain', 'SPAIN': 'Spain', 'ESPAÑA': 'Spain',
            'IT': 'Italy', 'ITALY': 'Italy', 'ITALIA': 'Italy',
            'NL': 'Netherlands', 'NETHERLANDS': 'Netherlands',
            'BE': 'Belgium', 'BELGIUM': 'Belgium'
        }
        return country_map.get(last_part, last_part.title())
    
    return "Unknown"

def generate_sample_pos_data():
    """Generate sample POS data for development/fallback purposes"""
    import random
    
    PRODUCT_FAMILIES = [
        'Yogurt & Desserts',
        'Baby Nutrition',
        'Medical Nutrition', 
        'Waters',
        'Plant-Based',
        'Dairy Alternatives'
    ]
    
    BUSINESS_TYPES = [
        'Supermarket',
        'Hypermarket',
        'Convenience Store',
        'Pharmacy',
        'Baby Store',
        'Health Food Store',
        'Online Retailer'
    ]
    
    sample_locations = [
        {"city": "Paris", "country": "France", "lat": 48.8566, "lng": 2.3522},
        {"city": "London", "country": "UK", "lat": 51.5074, "lng": -0.1278},
        {"city": "Berlin", "country": "Germany", "lat": 52.5200, "lng": 13.4050},
        {"city": "Madrid", "country": "Spain", "lat": 40.4168, "lng": -3.7038},
        {"city": "Rome", "country": "Italy", "lat": 41.9028, "lng": 12.4964},
        {"city": "Amsterdam", "country": "Netherlands", "lat": 52.3676, "lng": 4.9041},
        {"city": "Brussels", "country": "Belgium", "lat": 50.8503, "lng": 4.3517},
        {"city": "Vienna", "country": "Austria", "lat": 48.2082, "lng": 16.3738},
        {"city": "Zurich", "country": "Switzerland", "lat": 47.3769, "lng": 8.5417},
        {"city": "Stockholm", "country": "Sweden", "lat": 59.3293, "lng": 18.0686}
    ]
    
    pos_data = []
    
    for index, location in enumerate(sample_locations):
        # Generate 2-3 POS locations per city
        num_pos = random.randint(2, 3)
        
        for i in range(num_pos):
            # Add some random offset to coordinates
            lat_offset = (random.random() - 0.5) * 0.1
            lng_offset = (random.random() - 0.5) * 0.1
            
            business_type = random.choice(BUSINESS_TYPES)
            
            # Generate 1-3 product families per POS
            num_families = random.randint(1, 3)
            product_families = random.sample(PRODUCT_FAMILIES, num_families)
            
            # Generate sales volume based on business type
            base_volume = 50000
            if business_type == 'Hypermarket':
                base_volume = 200000
            elif business_type == 'Supermarket':
                base_volume = 100000
            elif business_type == 'Convenience Store':
                base_volume = 30000
            elif business_type == 'Pharmacy':
                base_volume = 25000
                
            sales_volume = int(base_volume + (random.random() * base_volume * 0.8))
            
            pos_data.append({
                "id": f"sample_{index}_{i}",
                "name": f"{business_type} {location['city']} {i + 1}",
                "latitude": location["lat"] + lat_offset,
                "longitude": location["lng"] + lng_offset,
                "businessType": business_type,
                "productFamilies": product_families,
                "salesVolume": sales_volume,
                "city": location["city"],
                "country": location["country"],
                "address": f"{random.randint(1, 999)} Main Street, {location['city']}",
                "submissionData": {
                    "user_name": "sample_user",
                    "points_earned": random.randint(10, 100),
                    "submitted_at": datetime.now().isoformat(),
                    "detected_products": [{"name": family.split()[0].lower()} for family in product_families]
                }
            })
    
    return pos_data

async def call_claude_api(user_token: str, prompt: str) -> str:
    """Call Claude API with user token - Enhanced with 403 error diagnostics"""
    claude_endpoint = "https://fe-vm-vdm-serverless-nmmvdg.cloud.databricks.com/serving-endpoints/databricks-claude-sonnet-4/invocations"
    
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    try:
        logger.info(f"Calling Claude endpoint: {claude_endpoint}")
        logger.info(f"Token prefix: {user_token[:20]}...{user_token[-10:] if len(user_token) > 30 else 'short_token'}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(claude_endpoint, json=payload, headers=headers)
            
            # Log response details for debugging
            logger.info(f"Claude API response status: {response.status_code}")
            logger.info(f"Claude API response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "Unable to generate recommendations")
            logger.info(f"Claude API success - response length: {len(content)}")
            return content
    
    except httpx.HTTPStatusError as e:
        logger.error(f"Claude API HTTP error: {e.response.status_code} - {e}")
        logger.error(f"Response body: {e.response.text}")
        
        # Enhanced 403 error handling per Databricks recommendations
        if e.response.status_code == 403:
            error_details = {
                "status_code": 403,
                "endpoint": CLAUDE_ENDPOINT,
                "token_prefix": user_token[:20] + "..." if len(user_token) > 20 else user_token,
                "response_body": e.response.text,
                "databricks_troubleshooting": {
                    "step_1": "Verify OAuth scopes include 'serving.serving-endpoints' or 'all-apis'",
                    "step_2": "Check 'Can Query' permission on databricks-claude-3-7-sonnet endpoint",
                    "step_3": "Try restarting app and user re-consent",
                    "step_4": "Check workspace audit logs for serverlessRealTimeInference events"
                }
            }
            logger.error(f"403 Forbidden Error Details: {error_details}")
            return f"403 Forbidden: Check OAuth scopes and endpoint permissions. Error: {e.response.text[:200]}"
        
        return f"API Error {e.response.status_code}: {e.response.text[:200] if hasattr(e.response, 'text') else str(e)}"
        
    except Exception as e:
        logger.error(f"Claude API connection error: {e}")
        return f"Connection Error: {str(e)}"

@app.post("/api/recommendations")
async def get_recommendations(request: Request, pos_data: List[Dict[str, Any]]):
    """Generate AI recommendations based on POS data"""
    # Try multiple header formats for Databricks token
    user_token = (
        request.headers.get("x-forwarded-access-token") or
        request.headers.get("X-Forwarded-Access-Token") or 
        request.headers.get("authorization", "").replace("Bearer ", "") or
        request.headers.get("Authorization", "").replace("Bearer ", "")
    )
    
    logger.info(f"Token received: {'Yes' if user_token else 'No'}")
    logger.info(f"Available headers: {list(request.headers.keys())}")
    
    if not user_token:
        # For local development, provide mock recommendations
        logger.info("No token found, using mock recommendations")
        return {
            "recommendations": [
                {
                    "type": "growth_opportunity",
                    "title": "Expand Baby Nutrition in Germany", 
                    "description": "Germany shows strong potential for Baby Nutrition products with only 23% market penetration compared to 45% in France.",
                    "priority": "high",
                    "impact": "Could increase revenue by 15-20% in German markets"
                },
                {
                    "type": "optimization",
                    "title": "Focus on Hypermarket Channel",
                    "description": "Hypermarkets show 40% higher sales volume than supermarkets but represent only 25% of our POS locations.",
                    "priority": "medium", 
                    "impact": "Opportunity to increase average sales per location"
                }
            ],
            "summary": "Analysis shows strong opportunities in Baby Nutrition expansion and hypermarket channel optimization.",
            "generated_at": datetime.now().isoformat()
        }
    
    # Prepare data summary for Claude
    total_locations = len(pos_data)
    total_sales = sum(pos.get("salesVolume", 0) for pos in pos_data)
    business_types = {}
    product_families = {}
    countries = {}
    
    for pos in pos_data:
        # Count business types
        bt = pos.get("businessType", "Unknown")
        business_types[bt] = business_types.get(bt, 0) + 1
        
        # Count product families
        for pf in pos.get("productFamilies", []):
            product_families[pf] = product_families.get(pf, 0) + 1
            
        # Count countries
        country = pos.get("country", "Unknown")
        countries[country] = countries.get(country, 0) + 1
    
    # Create prompt for Claude
    prompt = f"""As a business analyst for Danone, analyze this POS data and provide strategic recommendations:

Data Summary:
- Total POS Locations: {total_locations}
- Total Sales Volume: €{total_sales:,}
- Countries: {len(countries)} ({', '.join(list(countries.keys())[:5])})
- Business Types: {dict(list(business_types.items())[:3])}
- Top Product Families: {dict(list(product_families.items())[:3])}

Please provide 2-3 specific, actionable recommendations for Danone focusing on:
1. Growth opportunities in underperforming segments
2. Optimization strategies for existing channels
3. Geographic expansion or intensification

Format as JSON with: type, title, description, priority (high/medium/low), impact"""

    try:
        logger.info("Calling Claude API with user token")
        claude_response = await call_claude_api(user_token, prompt)
        logger.info(f"Claude API response received: {len(claude_response)} characters")
        # Try to parse Claude response as JSON
        if claude_response.startswith("{") or claude_response.startswith("["):
            recommendations_data = json.loads(claude_response)
        else:
            # If not JSON, create structured response from text
            recommendations_data = {
                "recommendations": [
                    {
                        "type": "ai_insight",
                        "title": "AI Analysis",
                        "description": claude_response[:500] + "..." if len(claude_response) > 500 else claude_response,
                        "priority": "medium",
                        "impact": "Based on current data patterns"
                    }
                ]
            }
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude response as JSON")
        recommendations_data = {
            "recommendations": [
                {
                    "type": "ai_insight", 
                    "title": "AI Analysis",
                    "description": claude_response[:500] + "..." if len(claude_response) > 500 else claude_response,
                    "priority": "medium",
                    "impact": "Based on current data patterns"
                }
            ]
        }
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        recommendations_data = {
            "recommendations": [
                {
                    "type": "error",
                    "title": "AI Service Error",
                    "description": f"Claude API error: {str(e)}. Using fallback recommendations.",
                    "priority": "medium",
                    "impact": "Verify token permissions and Claude endpoint access in Databricks"
                }
            ]
        }
    
    recommendations_data["generated_at"] = datetime.now().isoformat()
    recommendations_data["summary"] = f"Analysis of {total_locations} POS locations across {len(countries)} countries"
    
    return recommendations_data

@app.get("/api/analytics")
async def get_analytics_data(request: Request):
    """Get enhanced analytics data for dashboard with AI recommendations"""
    user_token = request.headers.get("x-forwarded-access-token")
    global db_pool
    
    if not db_pool:
        # Return basic structure if no database
        return {
            "error": "Database not available",
            "revenue_by_country": [],
            "competition_analysis": [],
            "pricing_trends": [],
            "ai_recommendations": [],
            "generated_at": datetime.now().isoformat()
        }
    
    try:
        async with db_pool.acquire() as conn:
            # Get revenue by country
            revenue_by_country = await conn.fetch("""
                SELECT 
                    country,
                    SUM(revenue) as total_revenue,
                    SUM(volume_sold) as total_volume,
                    COUNT(DISTINCT business_id) as business_count
                FROM public.volume_analytics
                WHERE month >= (
                    SELECT TO_CHAR(DATE_TRUNC('month', TO_DATE(MAX(month), 'YYYY-MM') - INTERVAL '3 months'), 'YYYY-MM')
                    FROM public.volume_analytics
                )
                GROUP BY country
                ORDER BY total_revenue DESC
            """)
            
            # Get competition analysis
            competition_analysis = await conn.fetch("""
                SELECT 
                    competitor_brand,
                    COUNT(DISTINCT danone_product) as competing_products,
                    AVG(price_difference) as avg_price_difference,
                    AVG(market_share) * 100 as avg_market_share,
                    SUM(CASE WHEN availability THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as availability_rate
                FROM public.competition_analytics
                GROUP BY competitor_brand
                ORDER BY avg_market_share DESC
                LIMIT 10
            """)
            
            # Get pricing trends  
            pricing_trends = await conn.fetch("""
                SELECT 
                    product_category,
                    month,
                    AVG(retail_price) as avg_price,
                    AVG(margin) as avg_margin,
                    AVG(price_vs_rrp) as price_vs_rrp
                FROM public.price_evolution
                GROUP BY product_category, month
                ORDER BY month DESC, product_category
            """)
            
            # Prepare data for AI analysis
            analytics_summary = {
        "revenue_by_country": [
                    {
                        "country": row["country"],
                        "revenue": float(row["total_revenue"]),
                        "volume": int(row["total_volume"]),
                        "business_count": int(row["business_count"])
                    } for row in revenue_by_country
                ],
                "competition_analysis": [
                    {
                        "competitor": row["competitor_brand"],
                        "competing_products": int(row["competing_products"]),
                        "avg_price_difference": round(float(row["avg_price_difference"]), 2),
                        "market_share": round(float(row["avg_market_share"]), 1),
                        "availability_rate": round(float(row["availability_rate"]), 1)
                    } for row in competition_analysis
                ],
                "pricing_trends": [
                    {
                        "category": row["product_category"],
                        "month": row["month"],
                        "avg_price": round(float(row["avg_price"]), 2),
                        "avg_margin": round(float(row["avg_margin"]), 1),
                        "price_vs_rrp": round(float(row["price_vs_rrp"]), 1)
                    } for row in pricing_trends
                ]
            }
            
            # Generate AI recommendations
            ai_recommendations = []
            if user_token:
                try:
                    # Prepare prompt for AI analysis
                    prompt = f"""As a Danone sales strategy expert, analyze this scout intelligence data and provide 3-4 specific, actionable recommendations for sales reps:

REVENUE BY COUNTRY:
{json.dumps(analytics_summary['revenue_by_country'][:5], indent=2)}

COMPETITION ANALYSIS:
{json.dumps(analytics_summary['competition_analysis'][:5], indent=2)}

PRICING TRENDS (Latest 3 months):
{json.dumps(analytics_summary['pricing_trends'][:10], indent=2)}

Focus on:
1. Pricing optimization opportunities (where our prices vs RRP indicate margin improvement potential)
2. Competitive threats and response strategies (competitors gaining market share)
3. Geographic expansion opportunities (countries with high volume but low business count)
4. Product category recommendations (trends showing growth or decline)

Provide recommendations in JSON format:
[
  {{
    "type": "pricing_optimization|competitive_response|market_expansion|product_focus",
    "title": "Clear actionable title",
    "description": "Specific recommendation with numbers",
    "priority": "high|medium|low",
    "impact": "Expected business impact",
    "action_items": ["Specific step 1", "Specific step 2"]
  }}
]"""

                    claude_response = await call_claude_api(user_token, prompt)
                    
                    # Try to parse AI response
                    try:
                        if claude_response.strip().startswith('['):
                            ai_recommendations = json.loads(claude_response)
                        else:
                            # Extract JSON from response if wrapped in text
                            import re
                            json_match = re.search(r'\[.*\]', claude_response, re.DOTALL)
                            if json_match:
                                ai_recommendations = json.loads(json_match.group())
                            else:
                                # Fallback structured response
                                ai_recommendations = [{
                                    "type": "ai_insight",
                                    "title": "AI Analysis",
                                    "description": claude_response[:300] + "..." if len(claude_response) > 300 else claude_response,
                                    "priority": "medium",
                                    "impact": "Strategic insight from field intelligence",
                                    "action_items": ["Review full AI analysis", "Implement recommendations"]
                                }]
                    except json.JSONDecodeError:
                        ai_recommendations = [{
                            "type": "ai_insight",
                            "title": "Strategic Analysis",
                            "description": claude_response[:300] + "..." if len(claude_response) > 300 else claude_response,
                            "priority": "medium", 
                            "impact": "AI-powered market intelligence",
                            "action_items": ["Review recommendations", "Prioritize actions"]
                        }]
                        
                except Exception as e:
                    logger.error(f"AI recommendation error: {e}")
                    ai_recommendations = [{
                        "type": "system_info",
                        "title": "AI Recommendations Unavailable",
                        "description": f"Unable to generate AI recommendations: {str(e)}",
                        "priority": "low",
                        "impact": "Manual analysis required",
                        "action_items": ["Review data manually", "Check AI service status"]
                    }]
            
            return {
                **analytics_summary,
                "ai_recommendations": ai_recommendations,
        "generated_at": datetime.now().isoformat()
    }
    
    except Exception as e:
        logger.error(f"Analytics data error: {e}")
        return {
            "error": str(e),
            "revenue_by_country": [],
            "competition_analysis": [],
            "pricing_trends": [],
            "ai_recommendations": [],
            "generated_at": datetime.now().isoformat()
        }

# Configure static directories
static_root_dir = os.path.join(os.path.dirname(__file__), "static")
static_assets_dir = os.path.join(static_root_dir, "static")

# Mount the nested static directory for JS/CSS assets
if os.path.exists(static_assets_dir):
    app.mount("/static", StaticFiles(directory=static_assets_dir), name="static")
    logger.info(f"Serving static assets from: {static_assets_dir}")

# Serve the React app
@app.get("/{path:path}")
async def serve_frontend(path: str):
    """Serve the React frontend"""
    # First, try to serve files from the main static directory (index.html, manifest.json, etc.)
    static_file_path = os.path.join(static_root_dir, path)
    
    # If the file exists in the root static directory, serve it
    if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
        return FileResponse(static_file_path)
    
    # For React routing and any other requests, serve index.html
    index_path = os.path.join(static_root_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    # Fallback
    return {"error": "Frontend not built. Please run 'npm run build' in the frontend directory."}

# Explicit routes for important static files that need to be publicly accessible
@app.get("/manifest.json")
async def serve_manifest():
    """Serve manifest.json with proper headers for PWA support - PUBLIC ENDPOINT"""
    manifest_path = os.path.join(static_root_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(
            manifest_path,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Expose-Headers": "*",
                "Access-Control-Allow-Credentials": "false",
                "X-Public-Resource": "true",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "SAMEORIGIN"
            }
        )
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.options("/manifest.json")
async def manifest_options():
    """Handle CORS preflight for manifest.json"""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*",
            "Access-Control-Allow-Credentials": "false",
            "Access-Control-Max-Age": "86400",
            "X-Public-Resource": "true"
        }
    )

# Additional debug endpoint for manifest
@app.get("/debug/manifest")
async def debug_manifest():
    """Debug endpoint to check manifest availability"""
    manifest_path = os.path.join(static_root_dir, "manifest.json")
    return {
        "manifest_exists": os.path.exists(manifest_path),
        "manifest_path": manifest_path,
        "static_root": static_root_dir,
        "timestamp": datetime.now().isoformat(),
        "note": "This endpoint helps debug manifest.json accessibility"
    }

# Ultra-simple manifest endpoint for maximum public access
@app.get("/static-manifest.json")
async def serve_static_manifest():
    """Ultra-simple manifest endpoint - FULLY PUBLIC"""
    return Response(
        content='{"name":"Danone POS Analytics","short_name":"Danone POS","theme_color":"#0066cc","background_color":"#ffffff","display":"standalone","start_url":"/"}',
        media_type="application/json",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*", 
            "Access-Control-Allow-Headers": "*",
            "Cache-Control": "public, max-age=3600",
            "X-Public-Endpoint": "true"
        }
    )

# Alternative manifest endpoint that might bypass authentication
@app.get("/public/manifest.json")
async def serve_public_manifest():
    """Alternative public manifest endpoint"""
    manifest_path = os.path.join(static_root_dir, "manifest.json")
    if os.path.exists(manifest_path):
        return FileResponse(
            manifest_path,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "X-Public-Resource": "true"
            }
        )
    raise HTTPException(status_code=404, detail="Manifest not found")

@app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon.ico"""
    favicon_path = os.path.join(static_root_dir, "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(
            favicon_path,
            headers={"Access-Control-Allow-Origin": "*"}
        )
    raise HTTPException(status_code=404, detail="Favicon not found")

@app.get("/asset-manifest.json")
async def serve_asset_manifest():
    """Serve asset-manifest.json with proper headers"""
    asset_manifest_path = os.path.join(static_root_dir, "asset-manifest.json")
    if os.path.exists(asset_manifest_path):
        return FileResponse(
            asset_manifest_path,
            headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            }
        )
    raise HTTPException(status_code=404, detail="Asset manifest not found")

# Root route
@app.get("/")
async def root():
    """Serve the main React app"""
    index_path = os.path.join(static_root_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    return {
        "message": "Danone POS Analytics API",
        "status": "Frontend not built",
        "instructions": "Please run 'npm run build' in the frontend directory"
    }
