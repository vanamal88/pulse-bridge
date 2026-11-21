import hashlib, secrets

def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def new_api_key() -> str:
    return "pulse_" + secrets.token_urlsafe(36)
