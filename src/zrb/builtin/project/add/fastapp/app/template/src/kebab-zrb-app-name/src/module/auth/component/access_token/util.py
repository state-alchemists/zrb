from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Mapping

import jsons
from component.error import HTTPAPIException
from jose import jwt
from module.auth.schema.token import AccessTokenData


class AccessTokenUtil(ABC):
    @abstractmethod
    def encode(self, token_data: AccessTokenData) -> str:
        pass

    @abstractmethod
    def decode(
        self, token_str: str, parse_expired_token: bool = False
    ) -> AccessTokenData:
        pass


class JWTAccessTokenUtil(AccessTokenUtil):
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def encode(self, data: AccessTokenData) -> str:
        expire_time = datetime.utcnow() + timedelta(seconds=data.expire_seconds)
        sub = jsons.dumps(data.model_dump())
        data_dict = {"sub": sub, "exp": expire_time}
        encoded_jwt = jwt.encode(data_dict, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode(self, token: str, parse_expired_token: bool = False) -> AccessTokenData:
        try:
            decoded_data = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options=self._get_decode_options(parse_expired_token),
            )
            sub = jsons.loads(decoded_data["sub"])
            token_data = AccessTokenData.model_validate(sub)
            if not parse_expired_token:
                expire_time = decoded_data["exp"]
                token_data.expire_seconds = (
                    datetime.fromtimestamp(expire_time) - datetime.utcnow()
                ).total_seconds()
                if token_data.expire_seconds < 0:
                    raise HTTPAPIException(422, "Expired token")
            return token_data
        except jwt.JWTError:
            raise HTTPAPIException(422, "Invalid token")

    def _get_decode_options(self, parse_expired_token: bool) -> Mapping[str, Any]:
        if parse_expired_token:
            return {"verify_exp": False}
        return {}
