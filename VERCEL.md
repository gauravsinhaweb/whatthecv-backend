# Deploying WhatthecV Backend on Vercel

This guide explains how to deploy the WhatthecV Backend API on Vercel.

## Prerequisites

1. A [Vercel](https://vercel.com) account
2. [Vercel CLI](https://vercel.com/docs/cli) installed (optional, for local testing)

## Deployment Steps

### 1. Set up Environment Variables

Before deploying, you need to set up the following environment variables in your Vercel project:

```
# API Configuration
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google Configuration
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://your-vercel-domain.vercel.app/api/v1/auth/google/callback

# Google AI Configuration
GOOGLE_AI_API_KEY=your_google_ai_api_key
GEMINI_MODEL_NAME=gemini-1.5-flash

# Email Configuration
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_smtp_username
SMTP_PASSWORD=your_smtp_password
EMAIL_FROM=noreply@example.com

# Supabase Configuration (Optional)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_JWT_SECRET=your_supabase_jwt_secret
```

### 2. Deploy to Vercel

You can deploy to Vercel in several ways:

#### Option 1: Using GitHub Integration

1. Push your code to a GitHub repository
2. Import the repository in Vercel dashboard
3. Set up the environment variables as mentioned above
4. Deploy

#### Option 2: Using Vercel CLI

1. Install Vercel CLI: `npm i -g vercel`
2. Log in to your Vercel account: `vercel login`
3. Deploy from your project directory: `vercel`
4. Follow the prompts to set up your project

### 3. SQLite Limitations on Vercel

Vercel uses serverless functions which have some limitations with SQLite:

1. **Ephemeral Filesystem**: The filesystem is not persistent between function invocations. This means SQLite database changes will be lost.
2. **Cold Starts**: Each cold start will recreate the SQLite database.

#### Alternative Database Options

For production use, consider:

1. **PostgreSQL with Supabase**: Update the database connection in `app/db/base.py`
2. **MongoDB Atlas**: Would require changes to the ORM approach
3. **Planetscale**: MySQL-compatible serverless database

### 4. Testing Your Deployment

After deploying, you can test your API at:

```
https://your-vercel-domain.vercel.app/
```

The API should respond with: `{"message":"WhatthecV API is running on Vercel! 🍾"}`

### 5. Custom Domain (Optional)

In your Vercel Dashboard, you can set up a custom domain for your API under the project settings. 