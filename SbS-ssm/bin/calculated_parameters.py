import secrets

def random_api_secret_key():
    return secrets.token_urlsafe(16)