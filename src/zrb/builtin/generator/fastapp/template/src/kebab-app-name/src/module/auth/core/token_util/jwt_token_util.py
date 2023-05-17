from core.error import HTTPAPIException
from module.auth.schema.token import AccessTokenData, RefreshTokenData
from module.auth.core.token_util.token_util import (
    AccessTokenUtil, RefreshTokenUtil
)
from datetime import datetime, timedelta
from jose import jwt
import jsons


class JWTAccessTokenUtil(AccessTokenUtil):

    def __init__(self, secret_key: str, algorithm: str = 'HS256'):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def encode(self, data: AccessTokenData) -> str:
        expire_time = datetime.utcnow() + timedelta(
            seconds=data.expire_seconds
        )
        sub = jsons.dumps(data.dict())
        data_dict = {'sub': sub, 'exp': expire_time}
        encoded_jwt = jwt.encode(
            data_dict, self.secret_key, algorithm=self.algorithm
        )
        return encoded_jwt

    def decode(self, token: str) -> AccessTokenData:
        try:
            decoded_data = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            sub = jsons.loads(decoded_data['sub'])
            token_data = AccessTokenData.parse_obj(sub)
            expire_time = decoded_data['exp']
            token_data.expire_seconds = ((
                datetime.fromtimestamp(expire_time) - datetime.utcnow()
            ).total_seconds())
            if token_data.expire_seconds < 0:
                raise HTTPAPIException(422, 'Expired token')
            return token_data
        except jwt.JWTError:
            raise HTTPAPIException(422, 'Invalid token')


class JWTRefreshTokenUtil(RefreshTokenUtil):

    def __init__(self, secret_key: str, algorithm: str = 'HS256'):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def encode(self, data: RefreshTokenData) -> str:
        expire_time = datetime.utcnow() + timedelta(
            seconds=data.expire_seconds
        )
        sub = jsons.dumps(data.dict())
        data_dict = {'sub': sub, 'exp': expire_time}
        encoded_jwt = jwt.encode(
            data_dict, self.secret_key, algorithm=self.algorithm
        )
        return encoded_jwt

    def decode(self, token: str) -> RefreshTokenData:
        try:
            decoded_data = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
            sub = jsons.loads(decoded_data['sub'])
            token_data = RefreshTokenData.parse_obj(sub)
            expire_time = decoded_data['exp']
            token_data.expire_seconds = ((
                datetime.fromtimestamp(expire_time) - datetime.utcnow()
            ).total_seconds())
            if token_data.expire_seconds < 0:
                raise HTTPAPIException(422, 'Expired token')
            return token_data
        except jwt.JWTError:
            raise HTTPAPIException(422, 'Invalid token')
