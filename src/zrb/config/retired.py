"""Settings zrb no longer reads and what took their place.

`Config.get_retired_env_keys` reports these settings at startup; keys and
replacement settings omit the environment prefix.
"""

RETIRED_SETTINGS: dict[str, str] = {
    # 3.15.0: the stage-1 input tap and its unused Pipecat pipeline were removed.
    "LLM_DICTATION_PIPECAT_ENABLED": (
        "nothing: the Pipecat input tap is gone; the service a session listens "
        "and speaks through is named by LLM_DICTATION_BACKEND and "
        "LLM_SPEECH_BACKEND"
    ),
    # 3.14.0: stop handling moved to word lists and a small model.
    "LLM_DICTATION_BARGE_IN_ACTION": (
        "nothing: anything said over zrb steers the turn, and a stop cancels it"
    ),
    "LLM_DICTATION_TURN_END_TIMEOUT": (
        "nothing: only barge_in_action=cancel waited for a cancelled turn"
    ),
    "LLM_DICTATION_ECHO_COOLDOWN": (
        "nothing: the microphone no longer goes deaf after zrb stops speaking; "
        "what it hears then is held by loudness instead, against the barge-in "
        "margin"
    ),
    "LLM_DICTATION_SELF_ECHO_MATCH": (
        "nothing: barge-in holds zrb's own voice by loudness instead"
    ),
    "LLM_DICTATION_SELF_ECHO_TAIL": (
        "nothing: barge-in holds zrb's own voice by loudness instead"
    ),
    "LLM_DICTATION_TRAILING_WORDS": (
        "nothing: an utterance now ends after LLM_DICTATION_MIN_SILENCE "
        "once it has words"
    ),
    # 3.14.0: speech reads the whole reply.
    "LLM_SPEECH_MAX_CHARS": "nothing: the whole reply is read",
    "LLM_SPEECH_SUMMARIZE": "LLM_SPEECH_SUMMARIZE_ABOVE_CHARS",
    "LLM_SPEECH_ON_SCREEN_NOTE": "nothing: the whole reply is read",
    # 3.10.0: voice became the dictation and camera features.
    "LLM_VOICE_ENABLED": "/voice is always offered",
    "LLM_VOICE_MODE": "LLM_DICTATION_BACKEND",
    "LLM_VOICE_PUSH_TO_TALK_KEY": "/voice starts recording and a pause stops it",
    "LLM_VOICE_OPENAI_MODEL": "LLM_DICTATION_OPENAI_MODEL",
    "LLM_VOICE_GOOGLE_MODEL": "LLM_DICTATION_GOOGLE_MODEL",
    "LLM_VOICE_VOSK_MODEL_NAME": "LLM_DICTATION_VOSK_MODEL_NAME",
    "LLM_VOICE_VOSK_MODEL_URL": "LLM_DICTATION_VOSK_MODEL_URL",
    "LLM_UI_COMMAND_VOICE": "LLM_DICTATION_COMMANDS",
    "LLM_UI_COMMAND_PHOTO": "LLM_CAMERA_COMMANDS",
    # 2.54.0: the journal tools made the reminder and its Stop hook unnecessary.
    "LLM_INCLUDE_JOURNAL_REMINDER": "nothing: the journal tools replace the reminder",
}
