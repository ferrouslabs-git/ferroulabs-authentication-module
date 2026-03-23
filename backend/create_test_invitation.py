"""
Create a real test invitation in the database
"""
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.auth_usermanagement.database import SessionLocal
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.invitation_service import create_invitation
from app.config import get_settings


def main():
    """Create a test invitation"""
    settings = get_settings()
    db = SessionLocal()
    
    try:
        # Get or create a test tenant
        tenant = db.query(Tenant).first()
        
        if not tenant:
            print("❌ No tenant found in database.")
            print("Please create a tenant first by logging into the app.")
            return
        
        # Get a test user to be the inviter
        user = db.query(User).first()
        
        if not user:
            print("❌ No user found in database.")
            print("Please create a user first by logging into the app.")
            return
        
        # Create invitation
        test_email = "ali@ferrouslabs.co.uk"
        invitation = create_invitation(
            db=db,
            tenant_id=tenant.id,
            email=test_email,
            role="admin",
            created_by=user.id,
            expires_in_days=7
        )
        
        invite_url = f"{settings.frontend_url}/invite/{invitation.token}"
        
        print("✅ Test invitation created successfully!")
        print(f"   Tenant: {tenant.name}")
        print(f"   Email: {invitation.email}")
        print(f"   Role: {invitation.target_role_name}")
        print(f"   Token: {invitation.token}")
        print(f"   Expires: {invitation.expires_at}")
        print()
        print(f"🔗 Invitation URL:")
        print(f"   {invite_url}")
        print()
        print("📧 To send email, use:")
        print(f"   python send_test_invitation.py {invitation.token}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
