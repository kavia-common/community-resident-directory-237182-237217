"""
Invitation management routes: create, list, accept, and cancel invitations.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from typing import Optional
from datetime import datetime, timedelta
import secrets
import logging

from src.models import CreateInvitation, InvitationResponse, AcceptInvitation, SuccessResponse
from src.auth import get_current_admin_user, hash_password
from src.database import get_db_connection, get_db_cursor
from src.audit import create_audit_log, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])
admin_router = APIRouter(prefix="/admin/invitations", tags=["Admin - Invitations"])


def generate_invitation_code() -> str:
    """Generate a unique invitation code."""
    return secrets.token_urlsafe(16)


@admin_router.post("", response_model=InvitationResponse, summary="Create invitation (Admin only)")
async def create_invitation(
    invitation_data: CreateInvitation,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Create a new invitation for a resident (Admin only).
    
    - **email**: Email address of the invitee
    - **unit_number**: Optional unit number
    - **floor_number**: Optional floor number
    - **expires_days**: Days until expiration (default: 7, max: 30)
    
    Requires admin authentication. Returns invitation details with code.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Check if email already has an account
                cursor.execute("SELECT id FROM users WHERE email = %s", (invitation_data.email,))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User with this email already exists"
                    )
                
                # Check for existing pending invitation
                cursor.execute("""
                    SELECT id FROM invitations 
                    WHERE email = %s AND status = 'pending' AND expires_at > NOW()
                """, (invitation_data.email,))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Pending invitation already exists for this email"
                    )
                
                # Generate unique invitation code
                invitation_code = generate_invitation_code()
                expires_at = datetime.utcnow() + timedelta(days=invitation_data.expires_days)
                
                # Create invitation
                cursor.execute("""
                    INSERT INTO invitations 
                        (email, invitation_code, invited_by, unit_number, floor_number, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, email, invitation_code, unit_number, floor_number, expires_at, created_at
                """, (invitation_data.email, invitation_code, current_user['id'],
                      invitation_data.unit_number, invitation_data.floor_number, expires_at))
                
                result = cursor.fetchone()
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="invitation_sent",
                    entity_type="invitation",
                    entity_id=result['id'],
                    details={"email": invitation_data.email},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return InvitationResponse(
                    id=result['id'],
                    email=result['email'],
                    invitation_code=result['invitation_code'],
                    status='pending',
                    unit_number=result['unit_number'],
                    floor_number=result['floor_number'],
                    expires_at=result['expires_at'],
                    accepted_at=None,
                    created_at=result['created_at']
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create invitation"
        )


@admin_router.get("", summary="List invitations (Admin only)")
async def list_invitations(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_admin_user)
):
    """
    List all invitations with optional filtering (Admin only).
    
    - **status**: Filter by invitation status (pending, accepted, expired)
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Requires admin authentication.
    """
    try:
        offset = (page - 1) * page_size
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Get invitations
                cursor.execute("""
                    SELECT 
                        i.id, i.email, i.invitation_code, i.status,
                        i.unit_number, i.floor_number, i.expires_at, i.accepted_at, i.created_at,
                        u.email as invited_by_email
                    FROM invitations i
                    LEFT JOIN users u ON i.invited_by = u.id
                    WHERE (%s IS NULL OR i.status = %s)
                    ORDER BY i.created_at DESC
                    LIMIT %s OFFSET %s
                """, (status_filter, status_filter, page_size, offset))
                
                invitations = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "invitations": invitations,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error listing invitations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invitations"
        )


@admin_router.delete("/{invitation_id}", summary="Cancel invitation (Admin only)")
async def cancel_invitation(
    invitation_id: int,
    request: Request,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Cancel a pending invitation (Admin only).
    
    - **invitation_id**: ID of the invitation to cancel
    
    Requires admin authentication.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Check if invitation exists
                cursor.execute("SELECT id, email FROM invitations WHERE id = %s", (invitation_id,))
                invitation = cursor.fetchone()
                
                if not invitation:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Invitation not found"
                    )
                
                # Delete invitation
                cursor.execute("DELETE FROM invitations WHERE id = %s", (invitation_id,))
                
                # Create audit log
                create_audit_log(
                    user_id=current_user['id'],
                    action="invitation_cancelled",
                    entity_type="invitation",
                    entity_id=invitation_id,
                    details={"email": invitation['email']},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Invitation cancelled successfully"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel invitation"
        )


@router.get("/{code}", summary="Verify invitation code")
async def verify_invitation(code: str):
    """
    Verify an invitation code (public endpoint).
    
    - **code**: Invitation code to verify
    
    Returns invitation details if valid and not expired.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT id, email, invitation_code, status, 
                           unit_number, floor_number, expires_at, accepted_at
                    FROM invitations
                    WHERE invitation_code = %s
                """, (code,))
                
                invitation = cursor.fetchone()
                
                if not invitation:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Invalid invitation code"
                    )
                
                if invitation['status'] != 'pending':
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invitation has already been {invitation['status']}"
                    )
                
                if invitation['expires_at'] < datetime.utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invitation has expired"
                    )
                
                return dict(invitation)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify invitation"
        )


@router.post("/{code}/accept", summary="Accept invitation")
async def accept_invitation(
    code: str,
    accept_data: AcceptInvitation,
    request: Request
):
    """
    Accept an invitation and create user account (public endpoint).
    
    - **code**: Invitation code
    - **password**: Password for the new account
    - **first_name**: User's first name
    - **last_name**: User's last name
    - **phone**: Optional phone number
    - **building**: Optional building name
    
    Creates a new user account and resident profile.
    """
    try:
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Verify and update invitation
                cursor.execute("""
                    UPDATE invitations
                    SET status = 'accepted', accepted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE invitation_code = %s AND status = 'pending' AND expires_at > NOW()
                    RETURNING id, email, unit_number, floor_number
                """, (code,))
                
                invitation = cursor.fetchone()
                
                if not invitation:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid, expired, or already used invitation"
                    )
                
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE email = %s", (invitation['email'],))
                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User already exists"
                    )
                
                # Get resident role ID
                cursor.execute("SELECT id FROM roles WHERE name = 'resident'")
                role = cursor.fetchone()
                
                # Hash password
                hashed_password = hash_password(accept_data.password)
                
                # Create user
                cursor.execute("""
                    INSERT INTO users (email, password_hash, role_id, is_active)
                    VALUES (%s, %s, %s, true)
                    RETURNING id
                """, (invitation['email'], hashed_password, role['id']))
                
                user_result = cursor.fetchone()
                user_id = user_result['id']
                
                # Create resident profile
                cursor.execute("""
                    INSERT INTO resident_profiles 
                        (user_id, first_name, last_name, phone, unit_number, 
                         floor_number, building)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (user_id, accept_data.first_name, accept_data.last_name,
                      accept_data.phone, invitation['unit_number'],
                      invitation['floor_number'], accept_data.building))
                
                profile_result = cursor.fetchone()
                
                # Create audit log
                create_audit_log(
                    user_id=user_id,
                    action="invitation_accepted",
                    entity_type="invitation",
                    entity_id=invitation['id'],
                    details={"email": invitation['email']},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Invitation accepted successfully",
                    data={
                        "user_id": user_id,
                        "profile_id": profile_result['id'],
                        "email": invitation['email']
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept invitation"
        )
