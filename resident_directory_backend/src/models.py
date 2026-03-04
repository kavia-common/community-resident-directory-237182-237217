"""
Pydantic models for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# Authentication models
class LoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: dict = Field(..., description="User information")


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password")
    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")
    phone: Optional[str] = Field(None, description="Phone number")
    unit_number: Optional[str] = Field(None, description="Unit number")
    floor_number: Optional[int] = Field(None, description="Floor number")
    building: Optional[str] = Field(None, description="Building name")


# Resident models
class ResidentProfile(BaseModel):
    """Resident profile information."""
    id: Optional[int] = None
    user_id: int
    first_name: str
    last_name: str
    phone: Optional[str] = None
    unit_number: Optional[str] = None
    floor_number: Optional[int] = None
    building: Optional[str] = None
    move_in_date: Optional[datetime] = None
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None


class ResidentListResponse(BaseModel):
    """Paginated list of residents."""
    residents: List[ResidentProfile]
    total: int
    page: int
    page_size: int


class UpdateResidentProfile(BaseModel):
    """Update resident profile request."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    unit_number: Optional[str] = None
    floor_number: Optional[int] = None
    building: Optional[str] = None
    move_in_date: Optional[datetime] = None
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None


# Invitation models
class CreateInvitation(BaseModel):
    """Create invitation request."""
    email: EmailStr = Field(..., description="Invitee email address")
    unit_number: Optional[str] = Field(None, description="Unit number")
    floor_number: Optional[int] = Field(None, description="Floor number")
    expires_days: int = Field(default=7, ge=1, le=30, description="Days until expiration")


class InvitationResponse(BaseModel):
    """Invitation details."""
    id: int
    email: str
    invitation_code: str
    status: str
    unit_number: Optional[str] = None
    floor_number: Optional[int] = None
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime


class AcceptInvitation(BaseModel):
    """Accept invitation request."""
    password: str = Field(..., min_length=6, description="New password")
    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")
    phone: Optional[str] = Field(None, description="Phone number")
    building: Optional[str] = Field(None, description="Building name")


# Announcement models
class CreateAnnouncement(BaseModel):
    """Create announcement request."""
    title: str = Field(..., min_length=1, max_length=200, description="Announcement title")
    content: str = Field(..., min_length=1, description="Announcement content")
    priority: str = Field(default="normal", description="Priority level")
    is_published: bool = Field(default=False, description="Published status")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    
    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'normal', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, normal, high, urgent')
        return v


class UpdateAnnouncement(BaseModel):
    """Update announcement request."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    priority: Optional[str] = None
    is_published: Optional[bool] = None
    expires_at: Optional[datetime] = None
    
    @validator('priority')
    def validate_priority(cls, v):
        if v and v not in ['low', 'normal', 'high', 'urgent']:
            raise ValueError('Priority must be one of: low, normal, high, urgent')
        return v


class AnnouncementResponse(BaseModel):
    """Announcement details."""
    id: int
    title: str
    content: str
    priority: str
    is_published: bool
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    author_name: Optional[str] = None
    created_at: datetime


# Message models
class SendMessage(BaseModel):
    """Send message request."""
    recipient_id: int = Field(..., description="Recipient user ID")
    subject: str = Field(..., min_length=1, max_length=200, description="Message subject")
    content: str = Field(..., min_length=1, description="Message content")
    parent_message_id: Optional[int] = Field(None, description="Parent message ID for threading")


class MessageResponse(BaseModel):
    """Message details."""
    id: int
    subject: str
    content: str
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    parent_message_id: Optional[int] = None


# Audit log models
class AuditLogResponse(BaseModel):
    """Audit log entry."""
    id: int
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    created_at: datetime


# Generic response models
class SuccessResponse(BaseModel):
    """Generic success response."""
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    detail: str
