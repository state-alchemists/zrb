from zrb.helper.typing import Any, List, Mapping
from abc import ABC, abstractmethod


class AnyInput(ABC):
    '''
    Any Input Specification
    '''

    @abstractmethod
    def get_name(self) -> str:
        '''
        Getting input name
        '''
        pass

    @abstractmethod
    def get_default(self) -> Any:
        '''
        Getting input default value
        '''
        pass

    @abstractmethod
    def get_param_decl(self) -> List[str]:
        '''
        Getting param declaration
        '''
        pass

    @abstractmethod
    def get_options(self) -> Mapping[str, Any]:
        '''
        Getting options
        '''
        pass

    @abstractmethod
    def should_render(self) -> bool:
        '''
        Whether should render the value or not
        '''
        pass

    @abstractmethod
    def is_hidden(self) -> bool:
        '''
        Whether input value is hidden or not
        '''
        pass
