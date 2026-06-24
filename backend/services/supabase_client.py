"""Supabase client singleton."""

from functools import lru_cache

from supabase import Client, create_client

from config import get_settings


class SupabaseNotConfiguredError(Exception):
    """Raised when required Supabase environment variables are missing."""


@lru_cache
def get_supabase() -> Client:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise SupabaseNotConfiguredError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
        )
    return create_client(settings.supabase_url, settings.supabase_service_key)
