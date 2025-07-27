from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import app.db
from app.db import fix_mongo_id

router = APIRouter()
security = HTTPBearer()

class EmailData(BaseModel):
    user_id: str
    tenant_email: str
    subject: str
    body: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return True

@router.post("/send")
async def send_billing_email(email_data: EmailData, user=Depends(get_current_user)):
    # Get SMTP config (for demo, use env vars)
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    if not sender_email or not sender_password:
        raise HTTPException(status_code=500, detail="Email config not set")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email_data.tenant_email
    msg['Subject'] = email_data.subject
    msg.attach(MIMEText(email_data.body, 'plain'))
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email_data.tenant_email, msg.as_string())
        server.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")
    # Log email
    await app.db.db.email_logs.insert_one({
        "user_id": email_data.user_id,
        "tenant_email": email_data.tenant_email,
        "subject": email_data.subject,
        "body": email_data.body
    })
    return {"message": "Billing email sent successfully"} 