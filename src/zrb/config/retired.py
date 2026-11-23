"""Settings zrb no longer reads and what took their place.

`Config.get_retired_env_keys` reports these settings at startup; keys and
replacement settings omit the environment prefix.
"""

RETIRED_SETTINGS: dict[str, str] = {
    # 4.0.0: the deprecated aliases are gone. Every row in this block was read
    # until this major, with one warning naming the new setting. A rename now
    # happens inside a major and the old name stops existing at the next one:
    # an alias left in the tree is an example, and the example says that
    # keeping an old name is how a rename is done here.
    "ENABLE_BUILTIN_TASKS": "BUILTIN_TASKS_ENABLED",
    "ENABLE_TIKTOKEN": "TIKTOKEN_ENABLED",
    "SHOW_UNRECOMMENDED_COMMAND_WARNING": "SHOW_UNRECOMMENDED_COMMAND_WARNING_ENABLED",
    "LLM_ENABLE_BUILTIN_AGENTS": "LLM_BUILTIN_AGENTS_ENABLED",
    "LLM_ENABLE_BUILTIN_SKILLS": "LLM_BUILTIN_SKILLS_ENABLED",
    "LLM_ENABLE_REWIND": "LLM_REWIND_ENABLED",
    "LLM_ENABLE_TOOL_SPILL": "LLM_TOOL_SPILL_ENABLED",
    "LLM_ENABLE_READ_IMAGE": "LLM_READ_IMAGE_ENABLED",
    "LLM_ENABLE_RATE_LIMIT": "LLM_RATE_LIMIT_ENABLED",
    "LLM_CAMERA_ENABLE_TOOL": "LLM_CAMERA_TOOL_ENABLED",
    "LLM_SCREENSHOT_ENABLE_TOOL": "LLM_SCREENSHOT_TOOL_ENABLED",
    "LLM_DICTATION_ENABLE_ECHO_CANCEL": "LLM_DICTATION_ECHO_CANCEL_ENABLED",
    "LLM_UI_ENABLE_MARKDOWN_MATH": "LLM_UI_MARKDOWN_MATH_ENABLED",
    "LLM_UI_ENABLE_MARKDOWN_MERMAID": "LLM_UI_MARKDOWN_MERMAID_ENABLED",
    "LLM_SEARCH_HOME": "LLM_SEARCH_HOME_ENABLED",
    "LLM_SEARCH_PROJECT": "LLM_SEARCH_PROJECT_ENABLED",
    "LLM_SHOW_OLLAMA_MODELS": "LLM_SHOW_OLLAMA_MODELS_ENABLED",
    "LLM_SHOW_PYDANTIC_AI_MODELS": "LLM_SHOW_PYDANTIC_AI_MODELS_ENABLED",
    "LLM_SHOW_TOOL_CALL_DETAIL": "LLM_SHOW_TOOL_CALL_DETAIL_ENABLED",
    "LLM_SHOW_TOOL_CALL_RESULT": "LLM_SHOW_TOOL_CALL_RESULT_ENABLED",
    "LLM_SANDBOX_ALLOW_ESCAPE": "LLM_SANDBOX_ALLOW_ESCAPE_ENABLED",
    "WEB_AUTH_SECURE_COOKIES": "WEB_AUTH_SECURE_COOKIES_ENABLED",
    "WEB_ENABLE_SECURE_COOKIES": "WEB_AUTH_SECURE_COOKIES_ENABLED",
    "LLM_UI_SHOW_RUNTIME_TIMERS": "LLM_UI_SHOW_RUNTIME_TIMERS_ENABLED",
    "LLM_DICTATION_DETECT_EMOTION": "LLM_DICTATION_DETECT_EMOTION_ENABLED",
    "LLM_DICTATION_EMOTION_OUT_OF_PROCESS": "LLM_DICTATION_EMOTION_OUT_OF_PROCESS_ENABLED",
    "LLM_VOICE_MOVES_SHELL": "LLM_VOICE_MOVES_SHELL_ENABLED",
    "LLM_BACKGROUND_WAKE": "LLM_BACKGROUND_WAKE_ENABLED",
    "LLM_INJECT_PROJECT_INSTRUCTIONS": "LLM_INJECT_PROJECT_INSTRUCTIONS_ENABLED",
    "LLM_SPEECH_MISSING_BLOCK_NOTICE_ENABLED": "LLM_SPEECH_BLOCK_NOTICE_ENABLED",
    # 4.0.0: the summarizer is gone. The `<spoken>` block is the one breath the
    # ear gets, and a reply that opened none is repaired at the end of the turn
    # (ADR-0145), so nothing asks a model for a shorter version of a reply.
    "LLM_SPEECH_SUMMARIZE_ABOVE_CHARS": "nothing: every reply is read whole",
    "LLM_SPEECH_SUMMARY_MODEL": "LLM_SPEECH_REPAIR_MODEL",
    "LLM_SPEECH_SUMMARY_TIMEOUT": "LLM_SPEECH_REPAIR_TIMEOUT",
    # 3.33.0: the journal was removed once the memory store replaced it
    # (ADR-0138). Every knob below only controlled its tools, its injection,
    # its judge or its writes.
    "LLM_JOURNAL_INDEX_FILE": "nothing: the journal was removed",
    "LLM_JOURNAL_INDEX_MAX_CHARS": "nothing: the journal was removed",
    "LLM_JOURNAL_HUD_MAX_ENTRIES_PER_SECTION": "nothing: the journal was removed",
    "LLM_JOURNAL_CATALOG_MAX_ENTRIES": "nothing: the journal was removed",
    "LLM_JOURNAL_CLAIMS_PER_TURN": "nothing: the journal was removed",
    "LLM_JOURNAL_CLAIMS_MAX_CHARS": "nothing: the journal was removed",
    "LLM_JOURNAL_AUTO_SEARCH_ENABLED": "nothing: the journal was removed",
    "LLM_JOURNAL_AUTO_SEARCH_MAX_HITS": "nothing: the journal was removed",
    "LLM_JOURNAL_GIT_ENABLED": "LLM_MEMORY_GIT_ENABLED",
    "LLM_JOURNAL_COMPLIANCE_ENABLED": "LLM_MEMORY_REVIEWER_ENABLED",
    "LLM_JOURNAL_COMPLIANCE_TURNS": "nothing: the memory reviewer runs every turn",
    "LLM_JOURNAL_LOCK_TIMEOUT": "LLM_MEMORY_LOCK_TIMEOUT",
    "LLM_JOURNAL_ENABLED": "nothing: the journal was removed",
    "LLM_JOURNAL_DIR": "LLM_NOTES_DIR",
    # 3.26.0: the RAG tool, its extra and the mixin that configured it were removed.
    "RAG_EMBEDDING_API_KEY": "nothing: the RAG tool was removed",
    "RAG_EMBEDDING_BASE_URL": "nothing: the RAG tool was removed",
    "RAG_EMBEDDING_MODEL": "nothing: the RAG tool was removed",
    "RAG_CHUNK_SIZE": "nothing: the RAG tool was removed",
    "RAG_OVERLAP": "nothing: the RAG tool was removed",
    "RAG_MAX_RESULT_COUNT": "nothing: the RAG tool was removed",
    # 3.26.0: the fixed cap became a share of the summarization threshold.
    "LLM_SUMMARY_MAX_TOKENS": "LLM_SUMMARY_MAX_TOKEN_RATIO",
    # 3.15.0: the stage-1 input tap and its unused Pipecat pipeline were removed.
    "LLM_DICTATION_PIPECAT_ENABLED": (
        "nothing: the Pipecat input tap is gone; the service a session listens "
        "and speaks through is named by LLM_DICTATION_BACKEND and "
        "LLM_SPEECH_BACKEND"
    ),
    # 3.14.0: stop handling moved to word lists and a small model.
    "LLM_DICTATION_BARGE_IN_ACTION": (
        "nothing: anything said over the assistant steers the turn, and a stop cancels it"
    ),
    "LLM_DICTATION_TURN_END_TIMEOUT": (
        "nothing: only barge_in_action=cancel waited for a cancelled turn"
    ),
    "LLM_DICTATION_ECHO_COOLDOWN": (
        "nothing: the microphone no longer goes deaf after the assistant stops speaking; "
        "what it hears then is held by loudness instead, against the barge-in "
        "margin"
    ),
    "LLM_DICTATION_SELF_ECHO_MATCH": (
        "nothing: barge-in holds the assistant's own voice by loudness instead"
    ),
    "LLM_DICTATION_SELF_ECHO_TAIL": (
        "nothing: barge-in holds the assistant's own voice by loudness instead"
    ),
    "LLM_DICTATION_TRAILING_WORDS": (
        "nothing: an utterance now ends after LLM_DICTATION_MIN_SILENCE "
        "once it has words"
    ),
    # 3.14.0: speech reads the whole reply.
    "LLM_SPEECH_MAX_CHARS": "nothing: the whole reply is read",
    "LLM_SPEECH_SUMMARIZE": "nothing: every reply is read whole",
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
