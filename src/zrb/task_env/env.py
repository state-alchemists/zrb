from typing import Optional
from pydantic import BaseModel
import os


class Env(BaseModel):
    name: str
    os_name: Optional[str] = None
    default: str = ''

    def get(self, prefix: str = '') -> str:
        if self.os_name is not None:
            prefixed_sys_name = self.os_name
            if prefix != '':
                prefixed_sys_name = '_'.join([prefix, self.os_name])
            return os.getenv(prefixed_sys_name, self.default)
        return self.default
