"""Authentication routes using Supabase Auth with mock_mode fallback, cookies, lockout, and rate limits."""

import re
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from middleware.rate_limit import limiter, LIMIT_LOGIN, LIMIT_SIGNUP

from config import get_settings
from services.supabase_client import get_supabase, SupabaseNotConfiguredError
from models.schemas import UserCredentials, TokenResponse, UserResponse, ProfileResponse
from utils.logger import user_id_var

logger = logging.getLogger(__name__)

# In-memory mock database of profiles for mock mode
MOCK_PROFILES = {
    "11111111-1111-1111-1111-111111111111": {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "demo@meetmind.ai",
        "is_pro": False,
        "pro_until": None,
        "meetings_used": 1,
        "razorpay_subscription_id": None
    }
}

router = APIRouter(prefix="/auth", tags=["auth"])

async def get_current_user(request: Request):
    """
    Dependency to validate the access token (JWT) against Supabase Auth.
    Checks the httpOnly cookie first, falling back to Authorization header.
    """
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        )
        
    settings = get_settings()
    
    if settings.mock_mode or token.startswith("mock_token_"):
        mock_user = UserResponse(
            id="11111111-1111-1111-1111-111111111111",
            email="demo@meetmind.ai"
        )
        user_id_var.set(str(mock_user.id))
        return mock_user

    try:
        supabase = get_supabase()
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token or user not found",
            )
        user_id_var.set(str(user_response.user.id))
        return user_response.user
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.warning("Token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

def check_failed_attempts(email: str, ip_address: str):
    """Check if IP or email has >= 5 failed login attempts in the past hour."""
    settings = get_settings()
    if settings.mock_mode:
        return
    try:
        supabase = get_supabase()
        one_hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        
        email_res = supabase.table("failed_logins").select("id").eq("email", email).gte("attempted_at", one_hour_ago).execute()
        email_attempts = len(email_res.data) if email_res.data else 0
        
        ip_res = supabase.table("failed_logins").select("id").eq("ip_address", ip_address).gte("attempted_at", one_hour_ago).execute()
        ip_attempts = len(ip_res.data) if ip_res.data else 0
        
        if email_attempts >= 5 or ip_attempts >= 5:
            from middleware.security import log_suspicious_activity
            log_suspicious_activity("lockout_triggered", ip_address, None, {"email": email})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account temporarily locked due to too many failed login attempts. Try again in an hour."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking account lockout: %s", e)

def record_failed_attempt(email: str, ip_address: str):
    """Record a failed login attempt in Supabase."""
    settings = get_settings()
    if settings.mock_mode:
        return
    try:
        supabase = get_supabase()
        supabase.table("failed_logins").insert({
            "email": email,
            "ip_address": ip_address
        }).execute()
    except Exception as e:
        logger.error("Failed to record failed login attempt: %s", e)

def clear_failed_attempts(email: str, ip_address: str):
    """Clear failed login records for the given email and IP."""
    settings = get_settings()
    if settings.mock_mode:
        return
    try:
        supabase = get_supabase()
        supabase.table("failed_logins").delete().eq("email", email).execute()
        supabase.table("failed_logins").delete().eq("ip_address", ip_address).execute()
    except Exception as e:
        logger.error("Failed to clear failed login attempts: %s", e)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit(LIMIT_SIGNUP)
async def signup(request: Request, credentials: UserCredentials):
    """Sign up a new user via Supabase Auth."""
    settings = get_settings()
    if settings.mock_mode:
        return {
            "message": "Signup successful (Mock Mode)",
            "user": {
                "id": "11111111-1111-1111-1111-111111111111",
                "email": credentials.email,
            },
        }

    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        auth_resp = supabase.auth.sign_up(
            {
                "email": credentials.email,
                "password": credentials.password,
            }
        )

        if not auth_resp.user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Signup failed — no user returned from auth provider",
            )

        user_id = auth_resp.user.id

        # Insert user profile row
        try:
            supabase.table("profiles").insert(
                {
                    "id": user_id,
                    "is_pro": False,
                    "meetings_used": 0,
                }
            ).execute()
        except Exception as profile_exc:
            logger.error("Failed to auto-create profile for user %s: %s", user_id, profile_exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize user profile: {profile_exc}",
            ) from profile_exc

        return {
            "message": "Signup successful. Please verify your email to log in.",
            "user": {
                "id": user_id,
                "email": auth_resp.user.email,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Signup failed for email %s", credentials.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {exc}",
        ) from exc


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LIMIT_LOGIN)
async def login(request: Request, response: Response, credentials: UserCredentials):
    """Authenticate user. Fallback to mock login if configured. Sets httpOnly cookie."""
    ip_addr = request.client.host if request.client else "unknown"
    
    # Check failed login lockout before running auth checks
    check_failed_attempts(credentials.email, ip_addr)
    
    settings = get_settings()
    if settings.mock_mode:
        mock_token = "mock_token_demo_12345"
        mock_refresh = "mock_refresh_demo_12345"
        
        # Set access and refresh tokens as cookies
        response.set_cookie(
            key="access_token",
            value=mock_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=3600
        )
        response.set_cookie(
            key="refresh_token",
            value=mock_refresh,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=30*24*3600
        )
        
        return TokenResponse(
            access_token=mock_token,
            token_type="bearer",
            user=UserResponse(
                id="11111111-1111-1111-1111-111111111111",
                email=credentials.email,
            ),
        )

    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        auth_resp = supabase.auth.sign_in_with_password(
            {
                "email": credentials.email,
                "password": credentials.password,
            }
        )

        if not auth_resp.session:
            record_failed_attempt(credentials.email, ip_addr)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Login failed — no session returned",
            )

        # Clear failed login attempts on successful login
        clear_failed_attempts(credentials.email, ip_addr)

        # Set cookies for production-grade security
        response.set_cookie(
            key="access_token",
            value=auth_resp.session.access_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=3600
        )
        response.set_cookie(
            key="refresh_token",
            value=auth_resp.session.refresh_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=30*24*3600
        )

        return TokenResponse(
            access_token=auth_resp.session.access_token,
            token_type="bearer",
            user=UserResponse(
                id=auth_resp.user.id,
                email=auth_resp.user.email,
            ),
        )

    except Exception as exc:
        record_failed_attempt(credentials.email, ip_addr)
        logger.warning("Login failed for email %s: %s", credentials.email, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    """Refreshes the expired access token using the httpOnly refresh_token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    settings = get_settings()
    if settings.mock_mode or refresh_token.startswith("mock_refresh_"):
        new_token = "mock_token_demo_12345"
        response.set_cookie(
            key="access_token",
            value=new_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=3600
        )
        return {"status": "refreshed"}

    try:
        supabase = get_supabase()
        res = supabase.auth.refresh_session(refresh_token)
        if not res or not res.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        
        response.set_cookie(
            key="access_token",
            value=res.session.access_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=3600
        )
        response.set_cookie(
            key="refresh_token",
            value=res.session.refresh_token,
            httponly=True,
            samesite="none",
            secure=True,
            max_age=30*24*3600
        )
        return {"status": "refreshed"}
    except Exception as exc:
        logger.error("Session refresh failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to refresh authentication session",
        ) from exc


@router.post("/logout")
async def logout(response: Response):
    """Log out user by clearing the httpOnly authentication cookies."""
    response.delete_cookie("access_token", samesite="none", secure=True)
    response.delete_cookie("refresh_token", samesite="none", secure=True)
    return {"message": "Logout successful"}


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(current_user = Depends(get_current_user)):
    """Fetch the user's subscription profile details."""
    settings = get_settings()
    user_id_str = str(current_user.id)
    
    if settings.mock_mode or user_id_str == "11111111-1111-1111-1111-111111111111":
        if user_id_str not in MOCK_PROFILES:
            try:
                from routes.meetings import MOCK_MEETINGS
                meetings_count = len([m for m in MOCK_MEETINGS if str(m["user_id"]) == user_id_str])
            except Exception:
                meetings_count = 0
            
            MOCK_PROFILES[user_id_str] = {
                "id": user_id_str,
                "email": current_user.email,
                "is_pro": False,
                "pro_until": None,
                "meetings_used": meetings_count,
                "razorpay_subscription_id": None
            }
        return ProfileResponse(**MOCK_PROFILES[user_id_str])

    try:
        supabase = get_supabase()
    except SupabaseNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        # Wrap in timeout to prevent infinite hangs
        import asyncio
        async def fetch_profile():
            return supabase.table("profiles").select("*").eq("id", user_id_str).maybe_single().execute()
            
        result = await asyncio.wait_for(fetch_profile(), timeout=10.0)
        profile_data = result.data
        
        if not profile_data:
            profile_data = {
                "id": user_id_str,
                "is_pro": False,
                "pro_until": None,
                "meetings_used": 0,
                "razorpay_subscription_id": None
            }
            supabase.table("profiles").insert(profile_data).execute()
        
        profile_data["email"] = current_user.email
        return ProfileResponse(**profile_data)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Database request timed out.",
        ) from exc
    except Exception as exc:
        logger.exception("Failed to fetch profile for user %s", user_id_str)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile",
        ) from exc


async def check_limits(current_user = Depends(get_current_user)):
    """Dependency to check if user has exceeded their free tier usage limits."""
    settings = get_settings()
    user_id_str = str(current_user.id)
    
    if settings.mock_mode or user_id_str == "11111111-1111-1111-1111-111111111111":
        if user_id_str not in MOCK_PROFILES:
            try:
                from routes.meetings import MOCK_MEETINGS
                meetings_count = len([m for m in MOCK_MEETINGS if str(m["user_id"]) == user_id_str])
            except Exception:
                meetings_count = 0
            
            MOCK_PROFILES[user_id_str] = {
                "id": user_id_str,
                "email": current_user.email,
                "is_pro": False,
                "pro_until": None,
                "meetings_used": meetings_count,
                "razorpay_subscription_id": None
            }
        profile = MOCK_PROFILES[user_id_str]
    else:
        try:
            supabase = get_supabase()
            import asyncio
            async def fetch_limits():
                return supabase.table("profiles").select("*").eq("id", user_id_str).maybe_single().execute()
            result = await asyncio.wait_for(fetch_limits(), timeout=10.0)
            profile = result.data
            if not profile:
                profile = {
                    "id": user_id_str,
                    "is_pro": False,
                    "pro_until": None,
                    "meetings_used": 0,
                    "razorpay_subscription_id": None
                }
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Database request timed out.",
            ) from exc
        except Exception as exc:
            logger.error("Failed to query user profile for limits: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user profile for limit check",
            ) from exc

    if not profile.get("is_pro", False) and profile.get("meetings_used", 0) >= 3:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Upgrade to Pro",
        )
    return profile
