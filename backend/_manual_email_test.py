"""
Quick test script to verify SES email sending works
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.auth_usermanagement.services.email_service import send_invitation_email
from app.config import get_settings


async def test_send_invitation():
    """Test sending an invitation email"""
    
    settings = get_settings()
    
    # Generate a realistic test token to show the URL format
    test_token = "AbCdEf123456789_test_token_example"
    
    # Test data
    to_email = "ali@ferrouslabs.co.uk"  # Using verified email
    invite_url = f"{settings.frontend_url}/invite/{test_token}"
    tenant_name = "FerrousLabs Test"
    
    print(f"Testing SES email sending...")
    print(f"  Region: {settings.ses_region}")
    print(f"  Sender: {settings.ses_sender_email}")
    print(f"  Recipient: {to_email}")
    print(f"  Invite URL: {invite_url}")
    print()
    
    try:
        result = await send_invitation_email(
            to_email=to_email,
            invite_url=invite_url,
            tenant_name=tenant_name
        )
        
        if result.sent:
            print("✅ Email sent successfully!")
            print(f"   Provider: {result.provider}")
            print(f"   Message ID: {result.message_id}")
        else:
            print("❌ Email failed to send")
            print(f"   Detail: {result.detail}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_send_invitation())
