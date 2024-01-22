from fastapi.security import OAuth2PasswordBearer

bearer_token_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login-oauth", auto_error=False
)
