"""
Supabase client singleton — 供所有 router 共用
使用 service_role key，明確設定 postgrest auth 以繞過 RLS
"""
import os
from supabase import create_client, Client

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 未設定")
        _client = create_client(url, key)
        # 明確設定 postgrest 使用 service_role key 以繞過 RLS
        _client.postgrest.auth(key)
    return _client
