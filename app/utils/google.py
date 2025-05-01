import httpx
from google.oauth2 import id_token
from google.auth.transport import requests

from app.core.config import settings

async def get_google_auth_url() -> str:
    return (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={settings.GOOGLE_CLIENT_ID}&"
        f"redirect_uri={settings.GOOGLE_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline"
    )

async def exchange_code_for_token(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }
        response = await client.post(token_url, data=data)
        return response.json()

async def get_google_user_info(id_token_jwt: str) -> dict:
    try:
        user_info = id_token.verify_oauth2_token(
            id_token_jwt, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )
        
        if user_info["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer")
            
        return user_info
    except Exception as e:
        print(f"Error verifying Google token: {e}")
        raise 