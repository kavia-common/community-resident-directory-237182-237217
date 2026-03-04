# Resident Directory Backend API

FastAPI backend service for the Resident Directory application with JWT authentication, role-based access control, and complete CRUD operations.

## Features

- **JWT Authentication** - Secure token-based authentication with bcrypt password hashing
- **Role-Based Access Control (RBAC)** - Admin and resident roles with permission enforcement
- **PostgreSQL Integration** - Direct database access using psycopg2
- **Resident Management** - Complete CRUD operations for resident profiles
- **Invitation System** - Send and manage invitations for new residents
- **Announcements** - Community announcements with priority levels
- **Messaging** - Direct messaging between residents
- **Audit Logging** - Comprehensive activity tracking for security and compliance
- **OpenAPI Documentation** - Auto-generated interactive API documentation

## Tech Stack

- **FastAPI** - Modern Python web framework
- **psycopg2** - PostgreSQL database adapter
- **PyJWT** - JSON Web Token implementation
- **bcrypt** - Password hashing
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

## Prerequisites

- Python 3.8+
- PostgreSQL database (configured in database container)
- Environment variables configured in `.env` file

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Update database connection variables (already configured by database container)
   - **Important:** Change `JWT_SECRET_KEY` to a secure random string in production

3. **Verify database connection:**
   The database connection parameters are provided by the database container:
   - Host: localhost
   - Port: 5000
   - Database: myapp
   - User: appuser
   - Password: dbuser123

## Running the Application

**Development mode:**
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --reload
```

**Production mode:**
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 3001 --workers 4
```

## API Documentation

Once the server is running, access the interactive documentation:

- **Swagger UI:** http://localhost:3001/docs
- **ReDoc:** http://localhost:3001/redoc
- **OpenAPI Spec:** http://localhost:3001/openapi.json

## Authentication

### Login

```bash
curl -X POST "http://localhost:3001/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@building.com", "password": "admin123"}'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {...}
}
```

### Using the Token

Include the token in the Authorization header:

```bash
curl -X GET "http://localhost:3001/residents" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

## Test Credentials

### Admin Account
- Email: `admin@building.com`
- Password: `admin123`
- Role: admin

### Resident Accounts
- Email: `john.doe@email.com`
- Password: `resident123`
- Role: resident

(Additional test accounts available in database seed data)

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/register` - Register new user
- `GET /auth/me` - Get current user profile

### Residents
- `GET /residents` - List residents (with search/filter)
- `GET /residents/{id}` - Get resident details
- `PUT /residents/me` - Update own profile
- `PUT /residents/{id}` - Update resident (admin only)
- `DELETE /residents/{id}` - Delete resident (admin only)
- `PATCH /residents/{id}/status` - Activate/deactivate (admin only)

### Invitations
- `GET /admin/invitations` - List invitations (admin only)
- `POST /admin/invitations` - Create invitation (admin only)
- `DELETE /admin/invitations/{id}` - Cancel invitation (admin only)
- `GET /invitations/{code}` - Verify invitation code
- `POST /invitations/{code}/accept` - Accept invitation

### Announcements
- `GET /announcements` - List published announcements
- `GET /announcements/{id}` - Get announcement details
- `GET /admin/announcements` - List all announcements (admin only)
- `POST /admin/announcements` - Create announcement (admin only)
- `PUT /admin/announcements/{id}` - Update announcement (admin only)
- `DELETE /admin/announcements/{id}` - Delete announcement (admin only)

### Messages
- `GET /messages/inbox` - Get received messages
- `GET /messages/sent` - Get sent messages
- `GET /messages/unread-count` - Get unread count
- `GET /messages/{id}` - Get message details
- `POST /messages` - Send message
- `PATCH /messages/{id}/read` - Mark as read
- `DELETE /messages/{id}` - Delete message

### Audit Logs
- `GET /admin/audit-logs` - List audit logs (admin only)
- `GET /admin/audit-logs/stats` - Get statistics (admin only)

## Project Structure

```
resident_directory_backend/
├── src/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py           # Authentication endpoints
│   │   │   ├── residents.py      # Resident management
│   │   │   ├── invitations.py    # Invitation system
│   │   │   ├── announcements.py  # Announcements
│   │   │   ├── messages.py       # Messaging
│   │   │   └── audit_logs.py     # Audit logs
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI application
│   │   └── generate_openapi.py   # OpenAPI spec generator
│   ├── __init__.py
│   ├── config.py                 # Configuration
│   ├── database.py               # Database connection
│   ├── auth.py                   # Auth utilities
│   ├── models.py                 # Pydantic models
│   └── audit.py                  # Audit logging
├── interfaces/
│   └── openapi.json              # Generated OpenAPI spec
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

## Database Schema

The backend connects to PostgreSQL with the following schema:

- **roles** - User roles (admin, resident)
- **users** - User accounts with authentication
- **resident_profiles** - Extended resident information
- **invitations** - Invitation and onboarding
- **announcements** - Community announcements
- **messages** - Direct messaging
- **audit_logs** - Activity audit trail

See database container documentation for complete schema details.

## Security Features

- ✅ Bcrypt password hashing (cost factor 12)
- ✅ JWT token authentication with expiration
- ✅ Role-based access control (RBAC)
- ✅ Parameterized SQL queries (SQL injection prevention)
- ✅ Comprehensive audit logging
- ✅ Input validation with Pydantic
- ✅ CORS configuration
- ✅ Secure token generation for invitations

## Development

### Code Quality

Run linting:
```bash
flake8 src/
```

### Generate OpenAPI Spec

```bash
python -m src.api.generate_openapi
```

This generates `interfaces/openapi.json` for frontend integration.

## Environment Variables

Required environment variables (see `.env.example`):

- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `POSTGRES_DB` - Database name
- `POSTGRES_PORT` - Database port
- `JWT_SECRET_KEY` - Secret key for JWT signing
- `JWT_ALGORITHM` - JWT algorithm (default: HS256)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time
- `ALLOWED_ORIGINS` - CORS allowed origins
- `PORT` - Server port

## Troubleshooting

### Database Connection Issues

1. Verify database is running: `psql postgresql://appuser:dbuser123@localhost:5000/myapp`
2. Check environment variables in `.env`
3. Review logs for connection errors

### Authentication Issues

1. Verify JWT_SECRET_KEY is set
2. Check token expiration time
3. Ensure passwords are correctly hashed in database

### CORS Issues

1. Add frontend URL to `ALLOWED_ORIGINS`
2. Verify CORS middleware configuration

## Support

For questions or issues, please refer to:
- API Documentation: http://localhost:3001/docs
- Database Documentation: `../resident_directory_database/BACKEND_QUICKSTART.md`

## License

Proprietary - Resident Directory Application
