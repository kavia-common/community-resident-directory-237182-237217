"""
Audit log routes: view audit logs and activity statistics (Admin only).
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
import logging

from src.auth import get_current_admin_user
from src.database import get_db_connection, get_db_cursor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/audit-logs", tags=["Admin - Audit Logs"])


@router.get("", summary="List audit logs (Admin only)")
async def list_audit_logs(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List audit logs with optional filtering (Admin only).
    
    - **user_id**: Filter by user ID
    - **action**: Filter by action type
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Requires admin authentication.
    """
    try:
        offset = (page - 1) * page_size
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        al.id, al.action, al.entity_type, al.entity_id, al.details,
                        al.ip_address, al.created_at,
                        u.email as user_email,
                        rp.first_name || ' ' || rp.last_name as user_name
                    FROM audit_logs al
                    LEFT JOIN users u ON al.user_id = u.id
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    WHERE 
                        (%s IS NULL OR al.user_id = %s)
                        AND (%s IS NULL OR al.action = %s)
                    ORDER BY al.created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, user_id, action, action, page_size, offset))
                
                logs = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "audit_logs": logs,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error listing audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/stats", summary="Get audit statistics (Admin only)")
async def get_audit_stats(current_user: dict = Depends(get_current_admin_user)):
    """
    Get audit log statistics (Admin only).
    
    Returns counts by action type and recent activity summary.
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Get counts by action
                cursor.execute("""
                    SELECT action, COUNT(*) as count
                    FROM audit_logs
                    GROUP BY action
                    ORDER BY count DESC
                """)
                
                action_counts = [dict(row) for row in cursor.fetchall()]
                
                # Get recent activity
                cursor.execute("""
                    SELECT 
                        al.action, al.entity_type, al.created_at,
                        rp.first_name || ' ' || rp.last_name as user_name
                    FROM audit_logs al
                    LEFT JOIN users u ON al.user_id = u.id
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    ORDER BY al.created_at DESC
                    LIMIT 10
                """)
                
                recent_activity = [dict(row) for row in cursor.fetchall()]
                
                # Get total count
                cursor.execute("SELECT COUNT(*) as total FROM audit_logs")
                total = cursor.fetchone()['total']
                
                return {
                    "total_logs": total,
                    "action_counts": action_counts,
                    "recent_activity": recent_activity
                }
                
    except Exception as e:
        logger.error(f"Error getting audit stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit statistics"
        )
