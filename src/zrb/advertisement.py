from zrb.helper.accessories.color import colored
from zrb.helper.advertisement import Advertisement
from zrb.helper.log import logger
from zrb.helper.typing import List

logger.debug(colored("Loading zrb.advertisement", attrs=["dark"]))

# flake8: noqa E501

advertisements: List[Advertisement] = [
    Advertisement(
        content="\n".join(
            [
                "Support zrb growth and development!",
                "☕ Donate at: https://stalchmst.com/donation",
                "🐙 Submit issues/PR at: https://github.com/state-alchemists/zrb",
                "🐤 Follow us at: https://twitter.com/zarubastalchmst",
            ]
        ),
        time_pattern=".*",
    ),
]
