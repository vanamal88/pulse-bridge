import pytest
from app.models import TelegramConnection, Direction
from app.services.users import get_or_create_user
from app.services.sync import upsert_connection,get_or_create_chat,store_inbound,edit_inbound,delete_inbound
@pytest.mark.asyncio
async def test_inbound_dedup_edit_delete(db_session):
    user=await get_or_create_user(db_session,1001,"A",None)
    conn=await upsert_connection(db_session,user,"business-1",True,True)
    chat=await get_or_create_chat(db_session,user,conn,2002,"Peer")
    one=await store_inbound(db_session,chat,11,"hello",None)
    two=await store_inbound(db_session,chat,11,"duplicate",None)
    assert one is not None and two is None
    edited=await edit_inbound(db_session,chat,11,"edited",None,None,None,None)
    assert edited.text=="edited" and edited.direction==Direction.inbound
    assert await delete_inbound(db_session,chat,[11]) == [11]
