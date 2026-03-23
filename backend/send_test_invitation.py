"""
Send invitation email with a real token from the database
Usage: python send_test_invitation.py <token>
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.auth_usermanagement.database import SessionLocal
from app.auth_usermanagement.services.email_service import send_invitation_email
from app.auth_usermanagement.services.invitation_service import get_invitation_by_token
from app.config import get_settings


async def main():
    """Send test invitation email"""
    if len(sys.argv) < 2:
        print("Usage: python send_test_invitation.py <token>")
        sys.exit(1)
    
    token = sys.argv[1]
    settings = get_settings()
    db = SessionLocal()
    
    try:
        # Get invitation
        invitation = get_invitation_by_token(db, token)
        
        if not invitation:
            print(f"❌ Invitation not found with token: {token}")
            return
        
        invite_url = f"{settings.frontend_url}/invite/{invitation.token}"
        
        print(f"📧 Sending invitation email...")
        print(f"   To: {invitation.email}")
        print(f"   Tenant: {invitation.tenant.name}")
        print(f"   Role: {invitation.target_role_name}")
        print(f"   URL: {invite_url}")
        print()
        
        result = await send_invitation_email(
            to_email=invitation.email,
            invite_url=invite_url,
            tenant_name=invitation.tenant.name
        )
        
        if result.sent:
            print("✅ Email sent successfully!")
            print(f"   Provider: {result.provider}")
            print(f"   Message ID: {result.message_id}")
        else:
            print("❌ Email failed to send")
            print(f"   Detail: {result.detail}")
            
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
