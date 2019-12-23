import adal
from requests.auth import AuthBase

class AzureOIDCAuth(AuthBase):
    """Attaches OpenID Connect Authentication to the given Request object."""

    def __init__(self, tenant_url):
        self._auth_context = adal.AuthenticationContext(
            tenant_url, timeout=3.0)

    def client_credentials_auth(self, resource_id, client_id, client_secret):
        auth_context = self._auth_context

        class cca(AuthBase):
            def __call__(self, r):
                token = auth_context.acquire_token_with_client_credentials(
                    resource_id,
                    client_id,
                    client_secret)

                r.headers['Authorization'] = f"Bearer {token['accessToken']}"
                return r

        return cca()
