from zrb.helper.typing import Any, List, Mapping
from abc import ABC, abstractmethod


class AnyInput(ABC):
    '''
    Task Input specification
    '''
    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_default(self) -> Any:
        pass

    @abstractmethod
    def get_param_decl(self) -> List[str]:
        pass

    @abstractmethod
    def get_options(self) -> Mapping[str, Any]:
        pass

    @abstractmethod
    def should_render(self) -> bool:
        pass

    @abstractmethod
    def is_hidden(self) -> bool:
        pass
