"""
Messaging routes: send, receive, and manage direct messages between users.
"""
from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
import logging

from src.models import SendMessage, SuccessResponse
from src.auth import get_current_user
from src.database import get_db_connection, get_db_cursor
from src.audit import create_audit_log, get_client_ip, get_user_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("/inbox", summary="Get received messages")
async def get_inbox(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get messages received by the current user.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Requires authentication.
    """
    try:
        offset = (page - 1) * page_size
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        m.id, m.subject, m.content, m.is_read, m.read_at, m.created_at,
                        m.parent_message_id,
                        sender_rp.first_name || ' ' || sender_rp.last_name as sender_name,
                        sender_u.email as sender_email
                    FROM messages m
                    LEFT JOIN users sender_u ON m.sender_id = sender_u.id
                    LEFT JOIN resident_profiles sender_rp ON sender_u.id = sender_rp.user_id
                    WHERE m.recipient_id = %s
                    ORDER BY m.created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, page_size, offset))
                
                messages = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "messages": messages,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error getting inbox: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )


@router.get("/sent", summary="Get sent messages")
async def get_sent(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get messages sent by the current user.
    
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    
    Requires authentication.
    """
    try:
        offset = (page - 1) * page_size
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        m.id, m.subject, m.content, m.is_read, m.read_at, m.created_at,
                        m.parent_message_id,
                        recipient_rp.first_name || ' ' || recipient_rp.last_name as recipient_name,
                        recipient_u.email as recipient_email
                    FROM messages m
                    LEFT JOIN users recipient_u ON m.recipient_id = recipient_u.id
                    LEFT JOIN resident_profiles recipient_rp ON recipient_u.id = recipient_rp.user_id
                    WHERE m.sender_id = %s
                    ORDER BY m.created_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, page_size, offset))
                
                messages = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "messages": messages,
                    "page": page,
                    "page_size": page_size
                }
                
    except Exception as e:
        logger.error(f"Error getting sent messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )


@router.get("/unread-count", summary="Get unread message count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """
    Get the count of unread messages for the current user.
    
    Requires authentication.
    """
    try:
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as unread_count
                    FROM messages
                    WHERE recipient_id = %s AND is_read = false
                """, (user_id,))
                
                result = cursor.fetchone()
                
                return {
                    "unread_count": result['unread_count']
                }
                
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread count"
        )


@router.get("/{message_id}", summary="Get message details")
async def get_message(
    message_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get detailed information about a specific message.
    
    - **message_id**: ID of the message
    
    Requires authentication. User must be sender or recipient.
    """
    try:
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    SELECT 
                        m.id, m.subject, m.content, m.is_read, m.read_at, 
                        m.created_at, m.parent_message_id, m.sender_id, m.recipient_id,
                        sender_rp.first_name || ' ' || sender_rp.last_name as sender_name,
                        sender_u.email as sender_email,
                        recipient_rp.first_name || ' ' || recipient_rp.last_name as recipient_name,
                        recipient_u.email as recipient_email
                    FROM messages m
                    LEFT JOIN users sender_u ON m.sender_id = sender_u.id
                    LEFT JOIN resident_profiles sender_rp ON sender_u.id = sender_rp.user_id
                    LEFT JOIN users recipient_u ON m.recipient_id = recipient_u.id
                    LEFT JOIN resident_profiles recipient_rp ON recipient_u.id = recipient_rp.user_id
                    WHERE m.id = %s
                """, (message_id,))
                
                message = cursor.fetchone()
                
                if not message:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Message not found"
                    )
                
                # Verify user is sender or recipient
                if message['sender_id'] != user_id and message['recipient_id'] != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied"
                    )
                
                # Remove internal IDs from response
                result = dict(message)
                result.pop('sender_id', None)
                result.pop('recipient_id', None)
                
                return result
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message"
        )


@router.post("", response_model=SuccessResponse, summary="Send message")
async def send_message(
    message_data: SendMessage,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Send a message to another user.
    
    - **recipient_id**: ID of the recipient user
    - **subject**: Message subject (max 200 characters)
    - **content**: Message content
    - **parent_message_id**: Optional parent message ID for threading
    
    Requires authentication.
    """
    try:
        sender_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Verify recipient exists
                cursor.execute("SELECT id FROM users WHERE id = %s AND is_active = true", 
                             (message_data.recipient_id,))
                if not cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Recipient not found"
                    )
                
                # Send message
                cursor.execute("""
                    INSERT INTO messages (sender_id, recipient_id, subject, content, parent_message_id)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, subject, created_at
                """, (sender_id, message_data.recipient_id, message_data.subject,
                      message_data.content, message_data.parent_message_id))
                
                result = cursor.fetchone()
                
                # Create audit log
                create_audit_log(
                    user_id=sender_id,
                    action="message_sent",
                    entity_type="message",
                    entity_id=result['id'],
                    details={"recipient_id": message_data.recipient_id},
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Message sent successfully",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


@router.patch("/{message_id}/read", summary="Mark message as read")
async def mark_as_read(
    message_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Mark a message as read.
    
    - **message_id**: ID of the message
    
    Requires authentication. User must be the recipient.
    """
    try:
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                cursor.execute("""
                    UPDATE messages
                    SET is_read = true, read_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND recipient_id = %s
                    RETURNING id, is_read, read_at
                """, (message_id, user_id))
                
                result = cursor.fetchone()
                
                if not result:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Message not found or access denied"
                    )
                
                return SuccessResponse(
                    message="Message marked as read",
                    data=dict(result)
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking message as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark message as read"
        )


@router.delete("/{message_id}", summary="Delete message")
async def delete_message(
    message_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a message.
    
    - **message_id**: ID of the message
    
    Requires authentication. User must be sender or recipient.
    """
    try:
        user_id = current_user['id']
        
        with get_db_connection() as conn:
            with get_db_cursor(conn) as cursor:
                # Delete message (only if user is sender or recipient)
                cursor.execute("""
                    DELETE FROM messages 
                    WHERE id = %s AND (sender_id = %s OR recipient_id = %s)
                """, (message_id, user_id, user_id))
                
                if cursor.rowcount == 0:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Message not found or access denied"
                    )
                
                # Create audit log
                create_audit_log(
                    user_id=user_id,
                    action="message_deleted",
                    entity_type="message",
                    entity_id=message_id,
                    ip_address=get_client_ip(request),
                    user_agent=get_user_agent(request)
                )
                
                return SuccessResponse(
                    message="Message deleted successfully"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )
