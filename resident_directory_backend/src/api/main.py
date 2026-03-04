"""
Resident Directory Backend API
FastAPI application with JWT authentication, RBAC, and complete CRUD operations.
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from src.config import settings
from src.database import init_db_pool, close_db_pool, test_db_connection
from src.api.routes import auth, residents, invitations, announcements, messages, audit_logs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown events."""
    # Startup
    logger.info("Starting Resident Directory Backend API...")
    try:
        init_db_pool()
        if test_db_connection():
            logger.info("✓ Database connection successful")
        else:
            logger.error("✗ Database connection failed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Resident Directory Backend API...")
    close_db_pool()


# Create FastAPI application
app = FastAPI(
    title="Resident Directory API",
    description="""
    Backend API for the Resident Directory application.
    
    ## Features
    
    * **JWT Authentication** - Secure token-based authentication
    * **Role-Based Access Control** - Admin and resident roles
    * **Resident Management** - CRUD operations for resident profiles
    * **Invitations** - Send and manage invitations for new residents
    * **Announcements** - Community announcements with priorities
    * **Messaging** - Direct messaging between residents
    * **Audit Logs** - Comprehensive activity tracking
    
    ## Authentication
    
    Most endpoints require authentication. Include the JWT token in the Authorization header:
    
    ```
    Authorization: Bearer <your_token>
    ```
    
    Get your token by calling the `/auth/login` endpoint.
    
    ## Roles
    
    * **Admin** - Full access to all endpoints, including user management
    * **Resident** - Access to view residents, send messages, view announcements
    """,
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Login, registration, and user profile endpoints"
        },
        {
            "name": "Residents",
            "description": "Resident profile management and search"
        },
        {
            "name": "Admin - Invitations",
            "description": "Admin endpoints for managing invitations (Admin only)"
        },
        {
            "name": "Invitations",
            "description": "Public endpoints for viewing and accepting invitations"
        },
        {
            "name": "Announcements",
            "description": "View community announcements"
        },
        {
            "name": "Admin - Announcements",
            "description": "Admin endpoints for managing announcements (Admin only)"
        },
        {
            "name": "Messages",
            "description": "Direct messaging between users"
        },
        {
            "name": "Admin - Audit Logs",
            "description": "View audit logs and activity statistics (Admin only)"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# Health check endpoint
@app.get("/", tags=["Health"])
def health_check():
    """
    Health check endpoint.
    
    Returns API status and database connection status.
    """
    db_healthy = test_db_connection()
    return {
        "message": "Resident Directory API",
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
        "version": "1.0.0"
    }


# Register routers
app.include_router(auth.router)
app.include_router(residents.router)
app.include_router(invitations.router)
app.include_router(invitations.admin_router)
app.include_router(announcements.router)
app.include_router(announcements.admin_router)
app.include_router(messages.router)
app.include_router(audit_logs.router)


# Documentation endpoint
@app.get("/docs-info", tags=["Documentation"])
def docs_info():
    """
    Information about API documentation.
    
    Returns links to interactive API documentation.
    """
    return {
        "message": "API Documentation",
        "swagger_ui": "/docs",
        "redoc": "/redoc",
        "openapi_spec": "/openapi.json"
    }
