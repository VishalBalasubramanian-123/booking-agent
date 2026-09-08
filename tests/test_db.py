# Tests that shared.db exposes a working Supabase client.
from shared import db


def test_supabase_client_is_not_none():
    assert db.supabase is not None


def test_session_table_query_returns_list_data():
    response = db.supabase.table("session").select("*").execute()
    assert isinstance(response.data, list)
