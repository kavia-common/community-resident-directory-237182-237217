"""
Resident management routes: CRUD operations, search, and filtering.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import Optional
import logging

from src.models import ResidentListResponse, UpdateResidentProfile, SuccessResponse
from src.auth import get_current_user, get_current_admin_user
from src.database import get_db_connection, get_db_cursor
from src.audit import create_audit_log, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/residents", tags=["Residents"])


@router.get("", response_model=ResidentListResponse, summary="List all residents")
async def list_residents(
    search: Optional[str] = Query(None, description="Search by name"),
    unit: Optional[str] = Query(None, description="Filter by unit number"),
    floor: Optional[int] = Query(None, description="Filter by floor number"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all residents with optional search and filtering.
    
    - **search**: Search by first or last name (case-insensitive)
    - **unit**: Filter by unit number
    - **floor**: Filter by floor number
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Requires authentication. Returns paginated list of residents.
    """
    try:
        offset = (page - 1) * page_size
        search_pattern = f"%{search}%" if search else ""
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Get total count
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM resident_profiles rp
                    JOIN users u ON rp.user_id = u.id
                    WHERE 
                        (%s = '' OR rp.first_name ILIKE %s OR rp.last_name ILIKE %s)
                        AND (%s IS NULL OR rp.unit_number = %s)
                        AND (%s IS NULL OR rp.floor_number = %s)
                """, (search_pattern, search_pattern, search_pattern,
                      unit, unit, floor, floor))
                
                total = cursor.fetchone()['total']
                
                # Get residents
                cursor.execute("""
                    SELECT 
                        rp.id, rp.user_id, rp.first_name, rp.last_name, rp.phone,
                        rp.unit_number, rp.floor_number, rp.building,
                        rp.move_in_date, rp.profile_image_url, rp.bio,
                        u.email, u.is_active
                    FROM resident_profiles rp
                    JOIN users u ON rp.user_id = u.id
                    WHERE 
                        (%s = '' OR rp.first_name ILIKE %s OR rp.last_name ILIKE %s)
                        AND (%s IS NULL OR rp.unit_number = %s)
                        AND (%s IS NULL OR rp.floor_number = %s)
                    ORDER BY rp.last_name, rp.first_name
                    LIMIT %s OFFSET %s
                """, (search_pattern, search_pattern, search_pattern,
                      unit, unit, floor, floor, page_size, offset))
                
                residents = [dict(row) for row in cursor.fetchall()]
                
                return ResidentListResponse(
                    residents=residents,
                    total=total,
                    page=page,
                    page_size=page_size
                )
                
    except Exception as e:
        logger.error(f"Error listing residents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve residents"
        )


@router.get("/{resident_id}", summary="Get resident by ID")
async def get_resident(
    resident_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific resident.
    
    - **resident_id**: User ID of the resident
    
    Requires authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        rp.id, rp.user_id, rp.first_name, rp.last_name, rp.phone,
                        rp.unit_number, rp.floor_number, rp.building,
                        rp.move_in_date, rp.profile_image_url, rp.bio,
                        u.email, u.is_active
                    FROM resident_profiles rp
                    JOIN users u ON rp.user_id = u.id
                    WHERE rp.user_id = %s
                """, (resident_id,))
                
                resident = cursor.fetchone()
                
                if not resident:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Resident not found"
                    )
                
                return dict(resident)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resident {resident_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resident"
        )


@router.put("/me", summary="Update own profile")
async def update_my_profile(
    profile_data: UpdateResidentProfile,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the current user's resident profile.
    
    Requires authentication. Users can only update their own profile.
    """
    try:
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Build dynamic update query
                updates = []
                params = []
                
                if profile_data.first_name is not None:
                    updates.append("first_name = %s")
                    params.append(profile_data.first_name)
                if profile_data.last_name is not None:
                    updates.append("last_name = %s")
                    params.append(profile_data.last_name)
                if profile_data.phone is not None:
                    updates.append("phone = %s")
                    params.append(profile_data.phone)
                if profile_data.unit_number is not None:
                    updates.append("unit_number = %s")
                    params.append(profile_data.unit_number)
                if profile_data.floor_number is not None:
                    updates.append("floor_number = %s")
                    params.append(profile_data.floor_number)
                if profile_data.building is not None:
                    updates.append("building = %s")
                    params.append(profile_data.building)
                if profile_data.move_in_date is not None:
                    updates.append("move_in_date = %s")
                    params.append(profile_data.move_in_date)
                if profile_data.profile_image_url is not None:
                    updates.append("profile_image_url = %s")
                    params.append(profile_data.profile_image_url)
                if profile_data.bio is not None:
                    updates.append("bio = %s")
                    params.append(profile_data.bio)
                
                if not updates:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No fields to update"
                    )
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(user_id)
                
                query = f"""
                    UPDATE resident_profiles
                    SET {', '.join(updates)}
                    WHERE user_id = %s
                    RETURNING id, user_id, first_name, last_name, updated_at
                """
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Profile not found"
                    )
                
                # Create audit log
                create_audit_log(
                    user_id=user_id,
                    action="profile_update",
                    entity_type="resident_profile",
                    entity_id=result['id'],
                    details=profile_data.dict(exclude_none=True),
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Profile updated successfully",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )


@router.put("/{resident_id}", summary="Update resident (Admin only)")
async def update_resident(
    resident_id: int,
    profile_data: UpdateResidentProfile,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Update a resident's profile (Admin only).
    
    - **resident_id**: User ID of the resident to update
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Build dynamic update query
                updates = []
                params = []
                
                if profile_data.first_name is not None:
                    updates.append("first_name = %s")
                    params.append(profile_data.first_name)
                if profile_data.last_name is not None:
                    updates.append("last_name = %s")
                    params.append(profile_data.last_name)
                if profile_data.phone is not None:
                    updates.append("phone = %s")
                    params.append(profile_data.phone)
                if profile_data.unit_number is not None:
                    updates.append("unit_number = %s")
                    params.append(profile_data.unit_number)
                if profile_data.floor_number is not None:
                    updates.append("floor_number = %s")
                    params.append(profile_data.floor_number)
                if profile_data.building is not None:
                    updates.append("building = %s")
                    params.append(profile_data.building)
                if profile_data.move_in_date is not None:
                    updates.append("move_in_date = %s")
                    params.append(profile_data.move_in_date)
                if profile_data.profile_image_url is not None:
                    updates.append("profile_image_url = %s")
                    params.append(profile_data.profile_image_url)
                if profile_data.bio is not None:
                    updates.append("bio = %s")
                    params.append(profile_data.bio)
                
                if not updates:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No fields to update"
                    )
                
                updates.append("updated_at = CURRENT_TIMESTAMP")
                params.append(resident_id)
                
                query = f"""
                    UPDATE resident_profiles
                    SET {', '.join(updates)}
                    WHERE user_id = %s
                    RETURNING id, user_id, first_name, last_name, updated_at
                """
                
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Resident not found"
                    )
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="resident_update",
                    entity_type="resident_profile",
                    entity_id=result['id'],
                    details={"updated_user_id": resident_id, **profile_data.dict(exclude_none=True)},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Resident updated successfully",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating resident {resident_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resident"
        )


@router.delete("/{resident_id}", summary="Delete resident (Admin only)")
async def delete_resident(
    resident_id: int,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Delete a resident account (Admin only).
    
    - **resident_id**: User ID of the resident to delete
    
    Requires admin authentication. This will cascade delete the user's profile.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Check if resident exists
                cursor.execute("""
                    SELECT u.id, u.email, rp.first_name, rp.last_name
                    FROM users u
                    LEFT JOIN resident_profiles rp ON u.id = rp.user_id
                    WHERE u.id = %s
                """, (resident_id,))
                
                resident = cursor.fetchone()
                
                if not resident:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Resident not found"
                    )
                
                # Delete user (cascades to profile)
                cursor.execute("DELETE FROM users WHERE id = %s", (resident_id,))
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="resident_deleted",
                    entity_type="user",
                    entity_id=resident_id,
                    details={
                        "deleted_email": resident['email'],
                        "deleted_name": f"{resident.get('first_name', '')} {resident.get('last_name', '')}"
                    },
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Resident deleted successfully"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting resident {resident_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resident"
        )


@router.patch("/{resident_id}/status", summary="Update resident status (Admin only)")
async def update_resident_status(
    resident_id: int,
    is_active: bool,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Activate or deactivate a resident account (Admin only).
    
    - **resident_id**: User ID of the resident
    - **is_active**: True to activate, False to deactivate
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET is_active = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id, email, is_active
                """, (is_active, resident_id))
                
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Resident not found"
                    )
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="resident_status_changed",
                    entity_type="user",
                    entity_id=resident_id,
                    details={"is_active": is_active},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message=f"Resident {'activated' if is_active else 'deactivated'} successfully",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating resident status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resident status"
        )
