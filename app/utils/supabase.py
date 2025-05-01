from supabase import create_client, Client
from app.core.config import settings

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