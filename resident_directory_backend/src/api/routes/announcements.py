"""
Announcement management routes: CRUD operations for community announcements.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from datetime import datetime
import logging

from src.models import CreateAnnouncement, UpdateAnnouncement, AnnouncementResponse, SuccessResponse
from src.auth import get_current_user, get_current_admin_user
from src.database import get_db_connection, get_db_cursor
from src.audit import create_audit_log, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/announcements", tags=["Announcements"])
admin_router = APIRouter(prefix="/admin/announcements", tags=["Admin - Announcements"])


@router.get("", summary="List published announcements")
async def list_announcements(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    List published announcements (for all authenticated users).
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Returns only published announcements that haven't expired.
    """
    try:
        offset = (page - 1) * page_size
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        a.id, a.title, a.content, a.priority, a.published_at, a.expires_at, a.created_at,
                        rp.first_name || ' ' || rp.last_name as author_name
                    FROM announcements a
                    LEFT JOIN users u ON a.author_id = u.id
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    WHERE a.is_published = true 
                        AND (a.expires_at IS NULL OR a.expires_at > NOW())
                    ORDER BY a.published_at DESC
                    LIMIT %s OFFSET %s
                """, (page_size, offset))
                
                announcements = [dict(row) for row in cursor.fetchall()]
                
                # Add is_published to match model
                for announcement in announcements:
                    announcement['is_published'] = True
                
                return {
                    "announcements": announcements,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error listing announcements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve announcements"
        )


@router.get("/{announcement_id}", summary="Get announcement details")
async def get_announcement(
    announcement_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific announcement.
    
    - **announcement_id**: ID of the announcement
    
    Requires authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        a.id, a.title, a.content, a.priority, a.is_published,
                        a.published_at, a.expires_at, a.created_at, a.updated_at,
                        rp.first_name || ' ' || rp.last_name as author_name,
                        u.email as author_email
                    FROM announcements a
                    LEFT JOIN users u ON a.author_id = u.id
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    WHERE a.id = %s
                """, (announcement_id,))
                
                announcement = cursor.fetchone()
                
                if not announcement:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Announcement not found"
                    )
                
                return dict(announcement)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting announcement {announcement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve announcement"
        )


@admin_router.get("", summary="List all announcements (Admin only)")
async def list_all_announcements(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all announcements including unpublished (Admin only).
    
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
                        a.id, a.title, a.content, a.priority, a.is_published, 
                        a.published_at, a.expires_at, a.created_at,
                        rp.first_name || ' ' || rp.last_name as author_name
                    FROM announcements a
                    LEFT JOIN users u ON a.author_id = u.id
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    ORDER BY a.created_at DESC
                    LIMIT %s OFFSET %s
                """, (page_size, offset))
                
                announcements = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "announcements": announcements,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error listing all announcements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve announcements"
        )


@admin_router.post("", response_model=AnnouncementResponse, summary="Create announcement (Admin only)")
async def create_announcement(
    announcement_data: CreateAnnouncement,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Create a new announcement (Admin only).
    
    - **title**: Announcement title (max 200 characters)
    - **content**: Announcement content
    - **priority**: Priority level (low, normal, high, urgent)
    - **is_published**: Whether to publish immediately
    - **expires_at**: Optional expiration date
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                published_at = datetime.utcnow() if announcement_data.is_published else None
                
                cursor.execute("""
                    INSERT INTO announcements 
                        (title, content, author_id, priority, is_published, published_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, title, priority, is_published, published_at, created_at
                """, (announcement_data.title, announcement_data.content, current_user['id'],
                      announcement_data.priority, announcement_data.is_published,
                      published_at, announcement_data.expires_at))
                
                result = cursor.fetchone()
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="announcement_created",
                    entity_type="announcement",
                    entity_id=result['id'],
                    details={"title": announcement_data.title},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return AnnouncementResponse(
                    id=result['id'],
                    title=result['title'],
                    content=announcement_data.content,
                    priority=result['priority'],
                    is_published=result['is_published'],
                    published_at=result['published_at'],
                    expires_at=announcement_data.expires_at,
                    author_name=f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}",
                    created_at=result['created_at']
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating announcement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create announcement"
        )


@admin_router.put("/{announcement_id}", summary="Update announcement (Admin only)")
async def update_announcement(
    announcement_id: int,
    announcement_data: UpdateAnnouncement,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update an announcement (Admin only).
    
    - **announcement_id**: ID of the announcement to update
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Build dynamic update query
                updates = []
                params = []
                
                if announcement_data.title is not None:
                    updates.append("title = %s")
                    params.append(announcement_data.title)
                if announcement_data.content is not None:
                    updates.append("content = %s")
                    params.append(announcement_data.content)
                if announcement_data.priority is not None:
                    updates.append("priority = %s")
                    params.append(announcement_data.priority)
                if announcement_data.is_published is not None:
                    updates.append("is_published = %s")
                    params.append(announcement_data.is_published)
                    if announcement_data.is_published:
                        updates.append("published_at = CURRENT_TIMESTAMP")
                if announcement_data.expires_at is not None:
                    updates.append("expires_at = %s")
                    params.append(announcement_data.expires_at)
                
                if not updates:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No fields to update"
                    )
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(announcement_id)
                
                query = f"""
                    UPDATE announcements
                    SET {', '.join(updates)}
                    WHERE id = %s
                    RETURNING id, title, priority, is_published, published_at, updated_at
                """
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Announcement not found"
                    )
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="announcement_updated",
                    entity_type="announcement",
                    entity_id=announcement_id,
                    details=announcement_data.dict(exclude_none=True),
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Announcement updated successfully",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating announcement {announcement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update announcement"
        )


@admin_router.delete("/{announcement_id}", summary="Delete announcement (Admin only)")
async def delete_announcement(
    announcement_id: int,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Delete an announcement (Admin only).
    
    - **announcement_id**: ID of the announcement to delete
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Check if announcement exists
                cursor.execute("SELECT id, title FROM announcements WHERE id = %s", (announcement_id,))
                announcement = cursor.fetchone()
                
                if not announcement:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Announcement not found"
                    )
                
                # Delete announcement
                cursor.execute("DELETE FROM announcements WHERE id = %s", (announcement_id,))
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="announcement_deleted",
                    entity_type="announcement",
                    entity_id=announcement_id,
                    details={"title": announcement['title']},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Announcement deleted successfully"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting announcement {announcement_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete announcement"
        )
