"""Settings zrb no longer reads, and what took their place.

A release that renames or removes a setting without an alias leaves every
environment that still sets the old name silently running on the default.
Listing it here makes zrb say so when it starts (`Config.get_retired_env_keys`),
naming what to set instead. Keys and replacement settings are written without
the env prefix; a value that is not a setting name says why nothing replaces
it. Add an entry in the same diff that retires a setting; the
upgrading guide (docs/advanced-topics/upgrading-guide.md) says the same in
prose.
"""

RETIRED_SETTINGS: dict[str, str] = {
    # 3.10.0: voice became the dictation and camera features (ADR-0102).
    "LLM_VOICE_ENABLED": "/voice is always offered",
    "LLM_VOICE_MODE": "LLM_DICTATION_BACKEND",
    "LLM_VOICE_PUSH_TO_TALK_KEY": "/voice starts recording and a pause stops it",
    "LLM_VOICE_OPENAI_MODEL": "LLM_DICTATION_OPENAI_MODEL",
    "LLM_VOICE_GOOGLE_MODEL": "LLM_DICTATION_GOOGLE_MODEL",
    "LLM_VOICE_VOSK_MODEL_NAME": "LLM_DICTATION_VOSK_MODEL_NAME",
    "LLM_VOICE_VOSK_MODEL_URL": "LLM_DICTATION_VOSK_MODEL_URL",
    "LLM_UI_COMMAND_VOICE": "LLM_DICTATION_COMMANDS",
    "LLM_UI_COMMAND_PHOTO": "LLM_CAMERA_COMMANDS",
}
