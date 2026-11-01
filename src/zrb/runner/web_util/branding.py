"""The title and tagline the web pages show, with the root group as fallback."""

from zrb.config.config import CFG
from zrb.group.any_group import AnyGroup


def get_web_title(root_group: AnyGroup) -> str:
    """`CFG.WEB_TITLE`, or the root group's name when the title is blank."""
    return CFG.WEB_TITLE if CFG.WEB_TITLE.strip() != "" else root_group.name


def get_web_jargon(root_group: AnyGroup) -> str:
    """`CFG.WEB_JARGON`, or the root group's description when the tagline is blank."""
    return CFG.WEB_JARGON if CFG.WEB_JARGON.strip() != "" else root_group.description
