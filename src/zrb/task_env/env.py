from typing import Optional
from typeguard import typechecked
import os


@typechecked
class Env():
    '''
    Task Environment definition
    '''

    def __init__(
        self, name: str,
        os_name: Optional[str] = None,
        default: str = ''
    ):
        self.name: str = name
        self.os_name: str = os_name if os_name is not None else name
        self.default: str = default

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
        prefixed_name = self._get_prefixed_name(self.os_name, prefix)
        return os.getenv(prefixed_name, os.getenv(self.os_name, self.default))

    def _get_prefixed_name(self, name: str, prefix: str):
        if prefix is None or prefix == '':
            return name
        return '_'.join([prefix, name])
