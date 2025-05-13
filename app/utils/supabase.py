from supabase import create_client, Client
from app.core.config import settings
import uuid
import os
import logging

logger = logging.getLogger(__name__)

def get_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

async def create_supabase_user(email: str, password: str):
    client = get_supabase_client()
    return client.auth.sign_up({
        "email": email,
        "password": password
    })

async def authenticate_supabase_user(email: str, password: str):
    client = get_supabase_client()
    return client.auth.sign_in_with_password({
        "email": email,
        "password": password
    })

async def sign_out_supabase_user(access_token: str):
    client = get_supabase_client()
    client.auth.set_session(access_token, None)
    return client.auth.sign_out()

async def get_supabase_user(access_token: str):
    client = get_supabase_client()
    client.auth.set_session(access_token, None)
    return client.auth.get_user()

async def update_supabase_user(access_token: str, user_details: dict):
    client = get_supabase_client()
    client.auth.set_session(access_token, None)
    return client.auth.update_user(user_details)

async def reset_password_supabase(email: str):
    client = get_supabase_client()
    return client.auth.reset_password_for_email(email)

async def google_sign_in_supabase():
    client = get_supabase_client()
    return client.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": settings.GOOGLE_REDIRECT_URI
        }
    })

async def upload_file_to_supabase_storage(file_content: bytes, file_name: str, content_type: str = None):
    # Try with direct service key (from environment variable)
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    # Create a unique filename to avoid collisions
    unique_file_name = f"{uuid.uuid4()}-{file_name}"
    bucket_name = "whatthecv"
    
    # Log key details (without revealing the actual keys)
    logger.info(f"Using service key: {'Present' if service_key else 'Missing'}")
    logger.info(f"Using regular key: {'Present' if settings.SUPABASE_KEY else 'Missing'}")
    
    # Check if the bucket exists and create it if needed
    if service_key:
        try:
            admin_client = create_client(settings.SUPABASE_URL, service_key)
            
            # Get bucket information - this returns a SyncBucket object
            try:
                # Try to get the bucket directly - if it doesn't exist, this will fail
                logger.info(f"Checking if bucket '{bucket_name}' exists")
                admin_client.storage.get_bucket(bucket_name)
                logger.info(f"Bucket '{bucket_name}' exists")
                bucket_exists = True
            except Exception as e:
                logger.info(f"Bucket check error: {str(e)}")
                bucket_exists = False
            
            if not bucket_exists:
                logger.info(f"Bucket '{bucket_name}' does not exist, attempting to create it")
                try:
                    # Create bucket with public access
                    admin_client.storage.create_bucket(bucket_name, {"public": True})
                    logger.info(f"Successfully created bucket '{bucket_name}'")
                    
                    # Add a public access policy to the bucket
                    try:
                        # This SQL would need to be run directly on the database or through the Supabase dashboard
                        # We'll log it for reference
                        policy_sql = f"""
                        CREATE POLICY "Allow public access" 
                        ON storage.objects 
                        FOR SELECT 
                        TO anon 
                        USING (bucket_id = '{bucket_name}');
                        """
                        logger.info(f"SQL to create public access policy: {policy_sql}")
                    except Exception as policy_error:
                        logger.error(f"Error creating policy note: {str(policy_error)}")
                except Exception as bucket_error:
                    logger.error(f"Failed to create bucket '{bucket_name}': {str(bucket_error)}")
        except Exception as e:
            logger.error(f"Error checking/creating bucket: {str(e)}")
    
    # Try multiple folder paths that might have different RLS policies
    folder_paths = [
        "public",                            # Try public folder
        "resumes",                           # Try resumes folder
        "uploads",                           # Try uploads folder
        ""                                   # Try root folder
    ]
    
    options = {}
    if content_type:
        options["content_type"] = content_type
    
    # Set up file options with content type
    file_options = {}
    if content_type:
        file_options["contentType"] = content_type
    
    # First try with the service key if available
    if service_key:
        try:
            admin_client = create_client(settings.SUPABASE_URL, service_key)
            
            # Try each folder path
            for folder_path in folder_paths:
                try:
                    # Construct the full path
                    full_path = f"{folder_path}/{unique_file_name}" if folder_path else unique_file_name
                    
                    logger.info(f"Attempting upload to {bucket_name}/{full_path} with service key")
                    
                    # Try the upload with different parameters
                    try:
                        # First attempt: standard upload
                        response = admin_client.storage.from_(bucket_name).upload(
                            path=full_path,
                            file=file_content,
                            file_options=file_options
                        )
                        logger.info(f"Standard upload succeeded: {response}")
                    except Exception as upload_error:
                        logger.warning(f"Standard upload failed: {str(upload_error)}")
                        
                        try:
                            # Second attempt: upsert
                            logger.info(f"Trying upsert for {full_path}")
                            response = admin_client.storage.from_(bucket_name).upload(
                                path=full_path,
                                file=file_content,
                                file_options={**file_options, "upsert": "true"}
                            )
                            logger.info(f"Upsert upload succeeded: {response}")
                        except Exception as upsert_error:
                            logger.error(f"Upsert upload also failed: {str(upsert_error)}")
                            raise upsert_error
                    
                    # Get the public URL for the uploaded file
                    public_url = admin_client.storage.from_(bucket_name).get_public_url(full_path)
                    
                    logger.info(f"Upload successful to {full_path}")
                    return {
                        "file_name": full_path,
                        "public_url": public_url
                    }
                except Exception as e:
                    logger.error(f"Failed to upload to {folder_path} with service key: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"Error with service key: {str(e)}")
    
    # Then try with the regular key
    try:
        regular_client = get_supabase_client()
        
        # Try each folder path
        for folder_path in folder_paths:
            try:
                # Construct the full path
                full_path = f"{folder_path}/{unique_file_name}" if folder_path else unique_file_name
                
                logger.info(f"Attempting upload to {bucket_name}/{full_path} with regular key")
                response = regular_client.storage.from_(bucket_name).upload(
                    path=full_path,
                    file=file_content,
                    file_options=file_options
                )
                
                public_url = regular_client.storage.from_(bucket_name).get_public_url(full_path)
                
                logger.info(f"Upload successful to {full_path}")
                return {
                    "file_name": full_path,
                    "public_url": public_url
                }
            except Exception as e:
                logger.error(f"Failed to upload to {folder_path} with regular key: {str(e)}")
                continue
    except Exception as client_error:
        logger.error(f"Error with regular client: {str(client_error)}")
    
    # If both clients fail, try a direct API call using requests
    try:
        logger.info("Attempting direct API upload as last resort")
        import requests
        
        upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{bucket_name}/public/{unique_file_name}"
        
        # Try uploading with service key if available
        headers = {
            "Authorization": f"Bearer {service_key or settings.SUPABASE_KEY}",
            "Content-Type": content_type or "application/octet-stream"
        }
        
        response = requests.post(upload_url, data=file_content, headers=headers)
        
        if response.status_code == 200:
            public_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/public/{unique_file_name}"
            logger.info(f"Direct API upload successful: {response.status_code}")
            return {
                "file_name": f"public/{unique_file_name}",
                "public_url": public_url
            }
        else:
            logger.error(f"Direct API upload failed: {response.status_code} - {response.text}")
    except Exception as api_error:
        logger.error(f"Direct API upload error: {str(api_error)}")
    
    # If all upload attempts failed, generate a fallback URL
    logger.warning("All upload attempts failed, returning fallback URL")
    
    # Construct a fallback URL format
    fallback_url = f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket_name}/public/{unique_file_name}"
    
    return {
        "file_name": unique_file_name,
        "public_url": fallback_url,
        "upload_failed": True,
        "error": "Could not upload file due to permissions. Please check Supabase bucket settings."
    } 