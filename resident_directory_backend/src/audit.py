"""
Audit logging utilities for tracking user actions.
"""
import logging
from typing import Optional, Dict, Any
from fastapi import Request

from src.database import get_db_connection, get_db_cursor

logger = logging.getLogger(__name__)


# PUBLIC_INTERFACE
def create_audit_log(
    user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[int]:
    """
    Create an audit log entry.
    
    Args:
        user_id: ID of the user performing the action
        action: Action performed (e.g., 'user_login', 'profile_update')
        entity_type: Type of entity affected (e.g., 'user', 'resident_profile')
        entity_id: ID of the affected entity
        details: Additional details as JSON
        ip_address: IP address of the requester
        user_agent: User agent string
        
    Returns:
        ID of the created audit log entry, or None if failed
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    INSERT INTO audit_logs 
                        (user_id, action, entity_type, entity_id, details, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, action, entity_type, entity_id, 
                      details if details else None, ip_address, user_agent))
                
                result = cursor.fetchone()
                audit_id = result['id'] if result else None
                logger.info(f"Audit log created: action={action}, user_id={user_id}, entity_type={entity_type}")
                return audit_id
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        return None


# PUBLIC_INTERFACE
def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract client IP address from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        IP address string or None
    """
    # Check for X-Forwarded-For header (proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Get the first IP in the chain
        return forwarded.split(",")[0].strip()
    
    # Fallback to direct client IP
    if request.client:
        return request.client.host
    
    return None


# PUBLIC_INTERFACE
def get_user_agent(request: Request) -> Optional[str]:
    """
    Extract user agent from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User agent string or None
    """
    return request.headers.get("User-Agent")
