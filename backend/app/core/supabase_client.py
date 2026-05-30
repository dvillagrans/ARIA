"""
Supabase async client factories.

Two clients are provided:
- Service-role client: for server-side operations that bypass RLS.
- Anon client: for user-scoped reads that respect RLS (Phase 2+).

ADR-01: create_async_client() called per-request via Depends (not singleton).
"""

from supabase._async.client import AsyncClient
from supabase import acreate_client

from app.core.config import Settings


async def get_supabase_client(settings: Settings) -> AsyncClient:
    """
    Build an async Supabase client authenticated with the service role key.

    Use this for backend-initiated writes or reads that must bypass RLS.
    Never expose this client or its key to the frontend.
    """
    return await acreate_client(
        settings.supabase_url, settings.supabase_service_role_key
    )


async def get_anon_client(settings: Settings) -> AsyncClient:
    """
    Build an async Supabase client authenticated with the anon key.

    Intended for user-scoped reads in Phase 2+ where the JWT is forwarded
    from the frontend.
    """
    return await acreate_client(
        settings.supabase_url, settings.supabase_anon_key
    )
