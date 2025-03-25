import json
import html
import logging
from pathlib import Path
from typing import Any

from zrb.builtin.group import llm_group
from zrb.builtin.llm.tool.api import get_current_location, get_current_weather
from zrb.builtin.llm.tool.cli import run_shell_command
from zrb.builtin.llm.tool.file import (
    list_files,
    read_all_files,
    read_text_file,
    write_text_file,
)
from zrb.builtin.llm.tool.web import (
    create_search_internet_tool,
    open_web_page,
    search_arxiv,
    search_wikipedia,
)
from zrb.config import (
    LLM_ALLOW_ACCESS_INTERNET,
    LLM_ALLOW_ACCESS_LOCAL_FILE,
    LLM_ALLOW_ACCESS_SHELL,
    LLM_HISTORY_DIR,
    SERP_API_KEY,
)
from zrb.context.any_shared_context import AnySharedContext
from zrb.input.bool_input import BoolInput
from zrb.input.str_input import StrInput
from zrb.input.text_input import TextInput
from zrb.task.llm_task import LLMTask
from zrb.util.file import read_file, write_file
from zrb.util.string.conversion import to_pascal_case

# Set up logging
logger = logging.getLogger(__name__)


class PreviousSessionInput(StrInput):
    """
    Custom input type for handling previous conversation sessions.
    
    This input component renders an HTML input field with JavaScript support
    for selecting previous conversation sessions.
    """

    def to_html(self, ctx: AnySharedContext) -> str:
        """
        Generate HTML representation of the previous session input field.
        
        Args:
            ctx: The shared context containing input values and configuration
            
        Returns:
            str: HTML string representation of the input component
            
        Raises:
            FileNotFoundError: If the JavaScript template file is missing
        """
        try:
            name = html.escape(self.name)
            description = html.escape(self.description)
            default = html.escape(self.get_default_str(ctx))
            
            js_template_path = Path(__file__).parent / "previous-session.js"
            
            script = read_file(
                file_path=str(js_template_path),
                replace_map={
                    "CURRENT_INPUT_NAME": name,
                    "CurrentPascalInputName": to_pascal_case(name),
                },
            )
            
            return "\n".join(
                [
                    f'<input name="{name}" placeholder="{description}" value="{default}" />',
                    f"<script>{script}</script>",
                ]
            )
        except Exception as e:
            logger.error(f"Error generating HTML for PreviousSessionInput: {str(e)}")
            # Provide a basic fallback in case of error
            escaped_name = html.escape(self.name)
            escaped_desc = html.escape(self.description)
            return f'<input name="{escaped_name}" placeholder="{escaped_desc}" />'


def _read_chat_conversation(ctx: AnySharedContext) -> list[dict[str, Any]]:
    """
    Read conversation history from file for the current session.
    
    Args:
        ctx: The shared context containing input values and configuration
        
    Returns:
        List of conversation message dictionaries or empty list if no history exists
        
    Raises:
        None: Returns empty list on any error
    """
    try:
        # Return empty list for new sessions
        if ctx.input.start_new:
            logger.info("Starting new conversation session")
            return []
            
        # Get previous session name
        previous_session_name = ctx.input.previous_session
        if not previous_session_name:
            # Look for last session file
            history_dir = Path(LLM_HISTORY_DIR)
            last_session_path = history_dir / "last-session"
            
            if last_session_path.is_file():
                previous_session_name = read_file(str(last_session_path)).strip()
                logger.info(f"Using last session: {previous_session_name}")
                
        # Get conversation file path
        if not previous_session_name:
            logger.info("No previous session found")
            return []
            
        # Load conversation history
        conversation_path = Path(LLM_HISTORY_DIR) / f"{previous_session_name}.json"
        if not conversation_path.is_file():
            logger.warning(f"Conversation file not found: {conversation_path}")
            return []
            
        # Parse the conversation JSON
        conversation_data = json.loads(read_file(str(conversation_path)))
        logger.info(f"Loaded conversation history with {len(conversation_data)} messages")
        return conversation_data
        
    except Exception as e:
        logger.error(f"Error reading conversation history: {str(e)}")
        return []


def _write_chat_conversation(
    ctx: AnySharedContext, conversations: list[dict[str, Any]]
) -> None:
    """
    Write conversation history to file.
    
    Args:
        ctx: The shared context containing session information
        conversations: List of conversation message dictionaries to save
        
    Returns:
        None
        
    Raises:
        None: Logs errors but doesn't raise exceptions
    """
    try:
        # Create history directory if it doesn't exist
        history_dir = Path(LLM_HISTORY_DIR)
        history_dir.mkdir(parents=True, exist_ok=True)
        
        # Get current session name
        current_session_name = ctx.session.name
        if not current_session_name:
            logger.warning("No session name available, using 'default'")
            current_session_name = "default"
            
        # Save conversation to file
        conversation_path = history_dir / f"{current_session_name}.json"
        write_file(str(conversation_path), json.dumps(conversations, indent=2))
        msg_count = len(conversations)
        logger.info(f"Saved {msg_count} messages to {conversation_path}")
        
        # Update last session reference
        last_session_path = history_dir / "last-session"
        write_file(str(last_session_path), current_session_name)
        
    except Exception as e:
        logger.error(f"Error writing conversation history: {str(e)}")


# Create the LLM chat task
logger.info("Initializing LLM chat task")


# Define helper functions for model configuration
def get_model_param(value_str: str):
    """Helper to convert empty strings to None for model parameters"""
    return None if not value_str or value_str.strip() == "" else value_str.strip()


# Create LLM chat task
llm_chat: LLMTask = llm_group.add_task(
    LLMTask(
        name="llm-chat",
        description="Chat with LLM using various tools and capabilities",
        input=[
            # Model configuration inputs
            StrInput(
                "model",
                description="LLM Model name (e.g., gpt-4, claude-3)",
                prompt="LLM Model",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            StrInput(
                "base-url",
                description="LLM API Base URL (for custom endpoints)",
                prompt="LLM API Base URL",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            StrInput(
                "api-key",
                description="LLM API Key for authentication",
                prompt="LLM API Key",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
                allow_empty=True,
            ),
            TextInput(
                "system-prompt",
                description="System prompt to guide LLM behavior",
                prompt="System prompt",
                default="",
                allow_positional_parsing=False,
                always_prompt=False,
            ),
            
            # Conversation management inputs
            BoolInput(
                "start-new",
                description="Start new conversation (LLM will forget everything)",
                prompt="Start new conversation (LLM will forget everything)",
                default=False,
                allow_positional_parsing=False,
                always_prompt=False,
            ),
            PreviousSessionInput(
                "previous-session",
                description="Previous conversation session",
                prompt="Previous conversation session (can be empty)",
                allow_positional_parsing=False,
                allow_empty=True,
                always_prompt=False,
            ),
            
            # Message input (must be last for best UX)
            TextInput(
                "message",
                description="User message",
                prompt="Your message"
            ),
        ],
        # Model configuration
        model=lambda ctx: get_model_param(ctx.input.model),
        model_base_url=lambda ctx: get_model_param(ctx.input.base_url),
        model_api_key=lambda ctx: get_model_param(ctx.input.api_key),
        system_prompt=lambda ctx: get_model_param(ctx.input.system_prompt),
        
        # Conversation history handling
        conversation_history_reader=_read_chat_conversation,
        conversation_history_writer=_write_chat_conversation,
        
        # Message template
        message="{ctx.input.message}",
        
        # No retries by default - let the user retry manually
        retries=0,
    ),
    alias="chat",
)

logger.info("LLM chat task initialized")


# Register tools based on access permissions in configuration
logger.info("Registering tools for LLM chat based on permissions")


# Local file system tools
if LLM_ALLOW_ACCESS_LOCAL_FILE:
    logger.info("Enabling local file access tools")
    try:
        # Reading tools
        llm_chat.add_tool(list_files)
        llm_chat.add_tool(read_text_file)
        llm_chat.add_tool(read_all_files)
        
        # Writing tools
        llm_chat.add_tool(write_text_file)
        
        logger.info("Local file access tools registered successfully")
    except Exception as e:
        logger.error(f"Failed to register local file tools: {str(e)}")


# Shell command execution tools
if LLM_ALLOW_ACCESS_SHELL:
    logger.info("Enabling shell command execution tool")
    try:
        llm_chat.add_tool(run_shell_command)
        logger.info("Shell command execution tool registered successfully")
    except Exception as e:
        logger.error(f"Failed to register shell command tool: {str(e)}")


# Internet access tools
if LLM_ALLOW_ACCESS_INTERNET:
    logger.info("Enabling internet access tools")
    try:
        # Web page tools
        llm_chat.add_tool(open_web_page)
        
        # Information search tools
        llm_chat.add_tool(search_wikipedia)
        llm_chat.add_tool(search_arxiv)
        
        # Internet search (if API key available)
        if SERP_API_KEY:
            logger.info("Enabling internet search with SerpAPI")
            search_tool = create_search_internet_tool(SERP_API_KEY)
            llm_chat.add_tool(search_tool)
        else:
            logger.warning("SerpAPI key not provided, internet search disabled")
        
        # Location and weather tools
        llm_chat.add_tool(get_current_location)
        llm_chat.add_tool(get_current_weather)
        
        logger.info("Internet access tools registered successfully")
    except Exception as e:
        logger.error(f"Failed to register internet tools: {str(e)}")


logger.info("LLM chat tool registration complete")
