from typing import List
from .helper.advertisement import Advertisement

# flake8: noqa E501

advertisements: List[Advertisement] = [
    Advertisement(
        content='\n'.join([
            'Support zrb growth and development!',
            '☕ Donate at: https://stalchmst.com/donation',
            '🐙 Submit issues/pull requests at: https://github.com/state-alchemists/zaruba',
            '🐤 Follow us at: https://twitter.com/zarubastalchmst'
        ]),
        time_pattern='.*'
    ),
]
