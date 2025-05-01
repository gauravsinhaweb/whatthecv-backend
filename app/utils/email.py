import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

async def send_email(to_email: str, subject: str, html_content: str) -> bool:
    try:
        message = MIMEMultipart()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to_email
        message["Subject"] = subject
        
        message.attach(MIMEText(html_content, "html"))
        
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, message.as_string())
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

async def send_otp_email(email: str, otp: str, purpose: str) -> bool:
    subject_map = {
        "signup": "Verify Your Email Registration",
        "login": "Your Login Verification Code",
        "reset_password": "Reset Your Password"
    }
    
    subject = subject_map.get(purpose, "Verification Code")
    
    html_content = f"""
    <html>
    <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2>Your Verification Code</h2>
            <p>Use the following code to {purpose.replace('_', ' ')}:</p>
            <div style="background-color: #f0f0f0; padding: 15px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">
                {otp}
            </div>
            <p>This code will expire in 10 minutes.</p>
            <p>If you didn't request this code, you can safely ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    return await send_email(email, subject, html_content) 