# WhatTheCV Backend

A FastAPI-based backend for resume analysis and job matching with AI-powered insights.

## Quick Start

### Using Simplified Setup Scripts

#### Option 1: Using Make (Easiest)

```bash
# Clone the repository
git clone https://github.com/yourusername/whatthecv-backend.git
cd whatthecv-backend

# View available commands
make help

# Setup local environment
make setup

# Start the application
make start

# Use Docker
make docker-up
make docker-down
```

#### Option 2: Local Setup (Recommended for Development)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/whatthecv-backend.git
cd whatthecv-backend
```

2. Run the setup script:
```bash
./run.sh setup
```

3. Start the application:
```bash
./run.sh start
```

The API will be available at http://localhost:8000.

#### Option 3: Docker Setup (Recommended for Production)

1. Clone the repository:
```bash
git clone https://github.com/yourusername/whatthecv-backend.git
cd whatthecv-backend
```

2. Use the Docker start script:
```bash
./docker-start.sh up      # Start the application
./docker-start.sh down    # Stop the application
./docker-start.sh logs    # View logs
./docker-start.sh rebuild # Rebuild and restart
./docker-start.sh shell   # Access shell in container
```

The API will be available at http://localhost:8000.

## Manual Setup

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/whatthecv-backend.git
cd whatthecv-backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables (copy from .env.example):
```bash
cp .env.example .env
# Edit .env with your configuration values
```

5. Run the application:
```bash
python start.py
# Or use the original method
python main.py
```

The API will be available at http://localhost:8000.

### Supabase Integration

This application integrates with Supabase for both PostgreSQL database and authentication:

1. Create a Supabase project at https://supabase.com
2. Get your database connection details from Supabase Dashboard → Project Settings → Database
3. Set up authentication in Supabase Dashboard → Authentication → Providers:
   - Enable Email auth with "Confirm email" option
   - Configure Google OAuth if needed
4. Update your `.env` file with Supabase credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
SUPABASE_HOST=your-supabase-postgres-host.supabase.co
SUPABASE_PASSWORD=your-supabase-postgres-password
SUPABASE_USER=postgres
SUPABASE_PORT=5432
SUPABASE_DB=postgres
```

5. Run the migration script to add Supabase fields to your database:
```bash
python -m app.db.migrations.add_supabase_id
```

### Authentication Features with Supabase

With Supabase integration, the application provides:
- Enhanced security with Supabase's auth infrastructure
- Email/password authentication with passwordless options
- Social login providers configuration through Supabase
- Single source of truth for user management
- Easy migration path between local and Supabase auth

### Docker Deployment

This project includes Docker and docker-compose files for easy deployment:

1. Build and start containers:
```bash
docker-compose up -d
```

2. Stop the containers:
```bash
docker-compose down
```

3. View logs:
```bash
docker-compose logs -f
```

## API Documentation

Once the server is running, access the interactive API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Required Environment Variables

- `SECRET_KEY`: JWT secret key
- `ALGORITHM`: JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT token expiration time
- `GOOGLE_CLIENT_ID`: Google OAuth client ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `GOOGLE_REDIRECT_URI`: Google OAuth redirect URI
- `GOOGLE_AI_API_KEY`: Google AI Gemini API key
- `SMTP_*`: Email server configuration for OTP
- `SUPABASE_*`: Supabase/PostgreSQL database configuration

## File Upload and Storage

The API includes endpoints for uploading and storing resume files:

- `POST /api/v1/resume/upload/with-file`: Upload a resume file and store both the extracted text and original file
- `GET /api/v1/resume/files/{file_id}`: Download a stored resume file
- `GET /api/v1/resume/files`: List all resume files for the current user

Files are stored in the database as binary data, making deployment easier across different environments. 
