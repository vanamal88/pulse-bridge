from app.api.deps import issue_ws_token,consume_ws_token
def test_ws_token_is_single_use_and_bound_to_user():
    token=issue_ws_token("user-a",60)
    assert consume_ws_token(token)=="user-a"
    assert consume_ws_token(token) is None
