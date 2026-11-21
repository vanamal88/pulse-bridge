import pytest
from app.services.users import get_or_create_user, issue_key_if_missing, user_for_key, rotate_key
@pytest.mark.asyncio
async def test_api_keys_are_per_user_and_revocable(db_session):
    u1=await get_or_create_user(db_session,101,"A",None)
    u2=await get_or_create_user(db_session,202,"B",None)
    k1=await issue_key_if_missing(db_session,u1)
    k2=await issue_key_if_missing(db_session,u2)
    assert k1 and k2 and k1 != k2
    assert (await user_for_key(db_session,k1)).id == u1.id
    assert (await user_for_key(db_session,k2)).id == u2.id
    k1b=await rotate_key(db_session,u1)
    assert await user_for_key(db_session,k1) is None
    assert (await user_for_key(db_session,k1b)).id == u1.id
