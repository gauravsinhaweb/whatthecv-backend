# WhatTheCV Backend

A FastAPI-based backend for resume analysis and job matching with AI-powered insights.

## Features

- **Authentication**
  - Email/Password registration with OTP verification
  - Google OAuth authentication
  - Secure JWT-based authorization

- **Resume Analysis**
  - Check if a document is a resume
  - Analyze resumes against job descriptions
  - Get suggestions for resume improvements
  - Section-specific improvement recommendations
  - Extract text from PDF, DOCX, and TXT files
  - Store original resume files in database

## Setup

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
python main.py
```

The API will be available at http://localhost:8000.

### Supabase Integration

This application can be connected to a Supabase PostgreSQL database for production use:

1. Create a Supabase project at https://supabase.com
2. Get your database connection details from Supabase Dashboard → Project Settings → Database
3. Update your `.env` file with Supabase credentials:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_HOST=your-supabase-postgres-host.supabase.co
SUPABASE_PASSWORD=your-supabase-postgres-password
SUPABASE_USER=postgres
SUPABASE_PORT=5432
SUPABASE_DB=postgres
```

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