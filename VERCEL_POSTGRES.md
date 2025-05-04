# Setting up PostgreSQL for WhatthecV API on Vercel

This document provides step-by-step instructions for setting up PostgreSQL with your WhatthecV API deployment on Vercel.

## Option 1: Vercel Postgres (Recommended)

Vercel offers a built-in PostgreSQL database service that integrates seamlessly with your project.

### Steps:

1. **Login to your Vercel Dashboard**:
   - Go to https://vercel.com/dashboard
   - Select your project

2. **Add Storage**:
   - Navigate to the "Storage" tab
   - Click "Connect Database"
   - Select "Postgres"
   - Follow the prompts to create a new PostgreSQL database

3. **Link to your project**:
   - After creating the database, link it to your project
   - Vercel will automatically add a `POSTGRES_URL` environment variable to your project

4. **Redeploy your project**:
   ```bash
   vercel --prod
   ```

5. **Verify connection**:
   - Visit `https://your-vercel-domain.vercel.app/api/v1/debug/db`
   - Confirm that the connection test shows "success": true

## Option 2: Supabase PostgreSQL

If you prefer using Supabase, follow these steps:

### Steps:

1. **Create a Supabase Account**:
   - Go to https://supabase.com/
   - Sign up or log in
   - Create a new project

2. **Get Database Credentials**:
   - In your Supabase project, go to Settings > Database
   - Find your connection information
   - Note the Host, Database Name, Port, and Password

3. **Add Environment Variables to Vercel**:
   - Go to your Vercel project settings
   - Navigate to "Environment Variables"
   - Add the following variables:
     ```
     SUPABASE_HOST=db.xxxxxxxxxxxx.supabase.co
     SUPABASE_PASSWORD=your-database-password
     SUPABASE_USER=postgres
     SUPABASE_PORT=5432
     SUPABASE_DB=postgres
     ```

4. **Redeploy your project**:
   ```bash
   vercel --prod
   ```

5. **Verify connection**:
   - Visit `https://your-vercel-domain.vercel.app/api/v1/debug/db`
   - Confirm that the connection test shows "success": true

## Option 3: Other PostgreSQL Providers

You can use any PostgreSQL provider and set a direct connection URL:

1. **Get your PostgreSQL Connection URL**:
   - Format: `postgresql://username:password@host:port/database`

2. **Add as Environment Variable to Vercel**:
   - Go to your Vercel project settings
   - Navigate to "Environment Variables"
   - Add the POSTGRES_URL variable with your connection string:
     ```
     POSTGRES_URL=postgresql://username:password@host:port/database
     ```

3. **Redeploy your project**:
   ```bash
   vercel --prod
   ```

## Troubleshooting

If you encounter issues with the database connection:

1. **Check Database Credentials**:
   - Verify your username, password, host, and port are correct
   - Ensure your database user has the necessary permissions

2. **Check Network Access**:
   - Make sure your database allows connections from Vercel's IP ranges
   - For Supabase: Enable "Enable Database Connection Pooling"

3. **Use the Debug Endpoints**:
   - Visit `/version` to see if database config is detected
   - Visit `/api/v1/debug/db` for detailed connection diagnostics

4. **Check Vercel Logs**:
   - Run `vercel logs` to see any database connection errors

5. **SSL Configuration**:
   - Some providers require specific SSL settings
   - If needed, you can modify the connection string to include SSL parameters

## Testing your API with PostgreSQL

After setting up PostgreSQL, you should be able to use all endpoints including `/api/v1/resume/upload/with-file`.

Test with:
```bash
curl -X POST -F "file=@your_resume.pdf" https://your-vercel-domain.vercel.app/api/v1/resume/upload/with-file
``` 