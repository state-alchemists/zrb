from zrb.helper.typing import Optional
from zrb.helper.typecheck import typechecked
from zrb.task_env.constant import RESERVED_ENV_NAMES
import os


@typechecked
class Env():
    '''
    Task Environment definition
    '''

    def __init__(
        self,
        name: str,
        os_name: Optional[str] = None,
        default: str = '',
        should_render: bool = True,
    ):
        if name in RESERVED_ENV_NAMES:
            raise ValueError(f'Forbidden input name: {name}')
        self.__name: str = name
        self.__os_name: str = os_name if os_name is not None else name
        self.__default: str = default
        self.__should_render: bool = should_render

    def get_name(self) -> str:
        return self.__name

    def get_os_name(self) -> str:
        return self.__os_name

    def get_default(self) -> str:
        return self.__default

    def should_render(self) -> bool:
        return self.__should_render

    def get(self, prefix: str = '') -> str:
        '''
        Return environment value.
        You can use prefix to distinguish 'DEV', 'PROD'

        Example:
        ```python
        os.environ['DEV_SERVER'] = 'localhost'
        os.environ['PROD_SERVER'] = 'example.com'

        env = Env(name='HOST', os_name='SERVER', default='0.0.0.0')

        print(env.get('DEV'))   # will show 'localhost'
        print(env.get('PROD'))  # will show 'example.com'
        print(env.get('STAG'))  # will show '0.0.0.0'
        ```
        '''
        if self.__os_name == '':
            return self.__default
        prefixed_name = self.__get_prefixed_name(self.__os_name, prefix)
        if prefixed_name in os.environ and os.environ[prefixed_name] != '':
            return os.environ[prefixed_name]
        if self.__os_name in os.environ and os.environ[self.__os_name] != '':
            return os.environ[self.__os_name]
        return self.__default

    def __get_prefixed_name(self, name: str, prefix: str):
        if prefix is None or prefix == '':
            return name
        return prefix + '_' + name

    def __repr__(self) -> str:
        name = self.__name
        os_name = self.__os_name
        default = self.__default
        return f'<Env name={name} os_name={os_name} default={default}>'
