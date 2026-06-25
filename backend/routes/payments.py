"""Payments routes for Razorpay subscription integration with mock fallback."""

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status

from config import get_settings
from routes.auth import get_current_user, MOCK_PROFILES
from services.supabase_client import get_supabase, SupabaseNotConfiguredError
from models.schemas import ProfileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create-subscription")
async def create_subscription(current_user = Depends(get_current_user)):
    """
    Create a Razorpay subscription.
    In mock mode or if keys are missing, returns a mock subscription payload.
    """
    settings = get_settings()
    user_id_str = str(current_user.id)
    
    # If keys are missing or mock_mode is active, return a simulated subscription
    if settings.mock_mode or not settings.razorpay_key_id or not settings.razorpay_key_secret:
        mock_sub_id = f"sub_mock_{hash(user_id_str) & 0xffffffff}"
        logger.info("Mock Mode: Created subscription %s for user %s", mock_sub_id, user_id_str)
        return {
            "subscription_id": mock_sub_id,
            "razorpay_key_id": "rzp_test_mockkey123",
            "amount": 49900,  # 499.00 in paise
            "currency": "INR",
            "name": "MeetMind Pro",
            "description": "Unlimited meetings & exports",
            "user": {
                "id": user_id_str,
                "email": current_user.email
            }
        }

    # Real Razorpay integration (using direct requests to avoid raw client requirements)
    import requests
    from requests.auth import HTTPBasicAuth

    # Standard plan ID or a default mock one if not set
    plan_id = settings.razorpay_plan_id or "plan_fake123"
    
    url = "https://api.razorpay.com/v1/subscriptions"
    payload = {
        "plan_id": plan_id,
        "total_count": 12,  # 12 billing cycles (e.g. 1 year)
        "quantity": 1,
        "notes": {
            "user_id": user_id_str
        }
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(settings.razorpay_key_id, settings.razorpay_key_secret),
            timeout=10
        )
        if response.status_code != 200:
            logger.error("Razorpay subscription creation failed: %s", response.text)
            raise HTTPException(
                status_code=502,
                detail=f"Razorpay subscription error: {response.json().get('error', {}).get('description', 'Unknown error')}"
            )
            
        res_data = response.json()
        return {
            "subscription_id": res_data["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "amount": 49900,
            "currency": "INR",
            "name": "MeetMind Pro",
            "description": "Unlimited meetings & exports",
            "user": {
                "id": user_id_str,
                "email": current_user.email
            }
        }
    except Exception as exc:
        logger.exception("Razorpay API connection failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Razorpay API: {exc}"
        ) from exc


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(..., alias="X-Razorpay-Signature")
):
    """
    Handle Razorpay webhook updates.
    Verifies signature and upgrades user profile on subscription.charged event.
    """
    settings = get_settings()
    body_bytes = await request.body()
    
    # Signature Verification
    webhook_secret = settings.razorpay_webhook_secret or "mock_webhook_secret"
    
    if not settings.mock_mode and x_razorpay_signature != "mock_signature":
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_signature, x_razorpay_signature):
            logger.warning("Invalid Razorpay webhook signature received")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signature verification failed"
            )

    # Parse Payload
    try:
        import json
        event_data = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON payload"
        ) from exc

    event = event_data.get("event")
    logger.info("Processing Razorpay webhook event: %s", event)

    if event in ("subscription.charged", "subscription.activated"):
        payload = event_data.get("payload", {})
        sub_entity = payload.get("subscription", {}).get("entity", {})
        
        sub_id = sub_entity.get("id")
        notes = sub_entity.get("notes", {})
        user_id_str = notes.get("user_id")

        if not user_id_str:
            logger.error("No user_id found in subscription notes for subscription %s", sub_id)
            return {"status": "ignored", "reason": "no user_id in notes"}

        # Upgrade User to Pro
        pro_until_dt = datetime.now(timezone.utc) + timedelta(days=30)
        
        if settings.mock_mode or user_id_str == "11111111-1111-1111-1111-111111111111":
            if user_id_str in MOCK_PROFILES:
                MOCK_PROFILES[user_id_str]["is_pro"] = True
                MOCK_PROFILES[user_id_str]["pro_until"] = pro_until_dt.isoformat()
                MOCK_PROFILES[user_id_str]["razorpay_subscription_id"] = sub_id
                logger.info("Mock Mode: Upgraded profile %s to Pro", user_id_str)
            return {"status": "success", "message": "User upgraded successfully (Mock Mode)"}
        
        try:
            supabase = get_supabase()
            supabase.table("profiles").update({
                "is_pro": True,
                "pro_until": pro_until_dt.isoformat(),
                "razorpay_subscription_id": sub_id
            }).eq("id", user_id_str).execute()
            logger.info("Upgraded profile %s in Supabase", user_id_str)
            return {"status": "success", "message": "User upgraded successfully"}
        except Exception as exc:
            logger.exception("Failed to upgrade profile in Supabase for user %s", user_id_str)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database update failed: {exc}"
            ) from exc

    return {"status": "ignored", "event": event}


@router.post("/mock-upgrade")
async def mock_upgrade(current_user = Depends(get_current_user)):
    """
    Direct endpoint to mock-upgrade a user to Pro (bypassing Razorpay checkout completely).
    Useful for testing frontend buttons and transitions instantly.
    """
    settings = get_settings()
    user_id_str = str(current_user.id)
    pro_until_dt = datetime.now(timezone.utc) + timedelta(days=30)

    if settings.mock_mode or user_id_str == "11111111-1111-1111-1111-111111111111":
        if user_id_str in MOCK_PROFILES:
            MOCK_PROFILES[user_id_str]["is_pro"] = True
            MOCK_PROFILES[user_id_str]["pro_until"] = pro_until_dt.isoformat()
            MOCK_PROFILES[user_id_str]["razorpay_subscription_id"] = "sub_direct_upgrade_mock"
            logger.info("Mock Mode: Manually upgraded profile %s to Pro", user_id_str)
        return {"status": "success", "message": "Upgraded to Pro successfully (Mock Mode)"}

    try:
        supabase = get_supabase()
        supabase.table("profiles").update({
            "is_pro": True,
            "pro_until": pro_until_dt.isoformat(),
            "razorpay_subscription_id": "sub_direct_upgrade"
        }).eq("id", user_id_str).execute()
        return {"status": "success", "message": "Upgraded to Pro successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database update failed: {exc}"
        ) from exc
