import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000/api/v1"

def signup_user(email, password):
    response = requests.post(
        f"{BASE_URL}/auth/signup",
        json={"email": email, "password": password}
    )
    return response.json()

def verify_signup(email, code):
    response = requests.post(
        f"{BASE_URL}/auth/signup/verify",
        json={"email": email, "code": code}
    )
    return response.json()

def login_user(email, password):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": email, "password": password}
    )
    return response.json()

def get_user_profile(token):
    response = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

def logout_user(token):
    response = requests.post(
        f"{BASE_URL}/auth/logout",
        headers={"Authorization": f"Bearer {token}"}
    )
    return response.json()

def reset_password(email):
    response = requests.post(
        f"{BASE_URL}/auth/password/reset",
        json={"email": email}
    )
    return response.json()

def google_login_url():
    response = requests.get(f"{BASE_URL}/auth/google")
    return response.url

if __name__ == "__main__":
    # Example usage
    email = "example@example.com"
    password = "securepassword123"
    
    # 1. Sign up a new user
    signup_result = signup_user(email, password)
    print(f"Signup result: {signup_result}")
    
    # 2. Get OTP from console input (in a real app, user would get this via email)
    otp_code = input("Enter the verification code received via email: ")
    
    # 3. Verify the signup with OTP
    verify_result = verify_signup(email, otp_code)
    print(f"Verification result: {verify_result}")
    
    # 4. Login with the new account
    login_result = login_user(email, password)
    print(f"Login result: {login_result}")
    
    # Get access token
    token = login_result.get("access_token")
    
    # 5. Get user profile
    if token:
        profile = get_user_profile(token)
        print(f"User profile: {profile}")
        
        # 6. Logout
        logout_result = logout_user(token)
        print(f"Logout result: {logout_result}")
    
    # 7. Password reset example
    reset_result = reset_password(email)
    print(f"Password reset result: {reset_result}")
    
    # 8. Get Google login URL
    google_url = google_login_url()
    print(f"Google login URL: {google_url}") 