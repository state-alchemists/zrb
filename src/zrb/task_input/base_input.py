from typing import Any, List, Mapping
from pydantic import BaseModel


class BaseInput(BaseModel):
    name: str
    shortcut: str
    default: str = ''
    help: str = ''
    prompt: str = ''

    def get_name(self) -> str:
        return self.name

    def get_param_decl(self) -> List[str]:
        return [f'--{self.name}', f'-{self.shortcut}']

    def get_options(self) -> Mapping[str, Any]:
        return {
            'default': self.default,
            'help': self.help,
            'prompt': self.prompt,
        }
