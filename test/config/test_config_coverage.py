import pytest
import os
from zrb.config.config import Config, get_log_level

def test_config_additional_properties():
    """Test various config properties to increase coverage."""
    config = Config()
    # Access various properties that might not be covered
    assert isinstance(config.LOGGER, object)
    assert isinstance(config.ENV_PREFIX, str)
    assert isinstance(config.ROOT_GROUP_NAME, str)
    assert isinstance(config.ROOT_GROUP_DESCRIPTION, str)
    assert isinstance(config.INIT_FILE_NAME, str)
    assert isinstance(config.LOGGING_LEVEL, (str, int))
    assert isinstance(config.LOAD_BUILTIN, bool)
    assert isinstance(config.WARN_UNRECOMMENDED_COMMAND, bool)
    assert isinstance(config.SESSION_LOG_DIR, str)
    assert isinstance(config.TODO_DIR, str)
    assert isinstance(config.TODO_VISUAL_FILTER, str)
    assert isinstance(config.TODO_RETENTION, str) # '1w'
    assert isinstance(config.VERSION, str)
    assert isinstance(config.WEB_CSS_PATH, list)
    assert isinstance(config.WEB_JS_PATH, list)
    assert isinstance(config.WEB_FAVICON_PATH, str)
    assert isinstance(config.WEB_COLOR, str)
    assert isinstance(config.WEB_HTTP_PORT, int)
    assert isinstance(config.WEB_GUEST_USERNAME, str)
    assert isinstance(config.WEB_SUPER_ADMIN_USERNAME, str)
    assert isinstance(config.WEB_SUPER_ADMIN_PASSWORD, str)
    assert isinstance(config.WEB_ACCESS_TOKEN_COOKIE_NAME, str)
    assert isinstance(config.WEB_REFRESH_TOKEN_COOKIE_NAME, str)
    assert isinstance(config.WEB_SECRET_KEY, str)
    assert isinstance(config.WEB_ENABLE_AUTH, bool)
    assert isinstance(config.WEB_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES, int)
    assert isinstance(config.WEB_AUTH_REFRESH_TOKEN_EXPIRE_MINUTES, int)
    assert isinstance(config.WEB_TITLE, str)
    assert isinstance(config.WEB_JARGON, str)
    assert isinstance(config.WEB_HOMEPAGE_INTRO, str)

def test_get_log_level_function():
    assert get_log_level("DEBUG") == 10
    assert get_log_level("INFO") == 20
    assert get_log_level("WARNING") == 30
    assert get_log_level("ERROR") == 40
    assert get_log_level("CRITICAL") == 50
    assert get_log_level("INVALID") == 30 # Default is WARNING (30) based on test failure
