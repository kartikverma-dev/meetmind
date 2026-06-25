"""Payments routes for Razorpay subscription integration with mock fallback - disabled in Beta."""

import logging
from fastapi import APIRouter, Depends

from routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/create-subscription")
async def create_subscription(current_user = Depends(get_current_user)):
    """Placeholder for beta mode: subscription creation disabled."""
    return {
        "status": "beta_free",
        "message": "MeetMind is in Free Beta. No subscription is required."
    }

@router.post("/webhook")
async def razorpay_webhook():
    """Placeholder for beta mode: webhook endpoint disabled."""
    return {
        "status": "disabled",
        "message": "Payments webhook disabled in beta."
    }

@router.post("/mock-upgrade")
async def mock_upgrade(current_user = Depends(get_current_user)):
    """Placeholder for beta mode: upgrade endpoint disabled."""
    return {
        "status": "disabled",
        "message": "Upgrades disabled. All users have full access in beta."
    }
