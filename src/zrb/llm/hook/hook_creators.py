import asyncio
import json
import logging
import os

from zrb.config.config import CFG
from zrb.llm.hook.interface import HookCallable, HookContext, HookResult
from zrb.llm.hook.schema import AgentHookConfig, CommandHookConfig, PromptHookConfig

logger = logging.getLogger(__name__)


def create_command_hook(config: CommandHookConfig) -> HookCallable:
    async def command_hook(context: HookContext) -> HookResult:
        import subprocess

        # Prepare environment with Claude Code context variables
        env = os.environ.copy()

        # Inject Claude Code context variables for hook scripts
        env["CLAUDE_HOOK_EVENT"] = str(context.event.value)
        env["CLAUDE_HOOK_EVENT_NAME"] = context.hook_event_name or str(
            context.event.value
        )
        env["CLAUDE_CWD"] = context.cwd or ""
        env["CLAUDE_TRANSCRIPT_PATH"] = context.transcript_path or ""
        env["CLAUDE_PERMISSION_MODE"] = context.permission_mode

        # Phase 7: Environment Variables
        env["CLAUDE_PROJECT_DIR"] = (
            context.cwd or os.getcwd()
        )  # Best guess for project root
        env["CLAUDE_PLUGIN_ROOT"] = (
            ""  # TODO: Need to pass this context if available
        )
        env["CLAUDE_CODE_REMOTE"] = "false"  # Zrb is typically local for now
        if context.metadata.get("remote"):
            env["CLAUDE_CODE_REMOTE"] = "true"

        # Inject event-specific data as JSON
        import json as json_module

        try:
            # Try to serialize event_data, fall back to string representation
            if context.event_data is not None:
                env["CLAUDE_EVENT_DATA"] = json_module.dumps(context.event_data)
            else:
                env["CLAUDE_EVENT_DATA"] = "null"
        except (TypeError, ValueError):
            # If not JSON serializable, use string representation
            env["CLAUDE_EVENT_DATA"] = str(context.event_data)

        # Add context fields to environment
        for field in [
            "tool_name",
            "tool_input",
            "prompt",
            "message",
            "title",
            "notification_type",
            "agent_id",
            "teammate_name",
            "task_id",
        ]:
            value = getattr(context, field, None)
            if value is not None:
                if isinstance(value, dict):
                    env[f"CLAUDE_{field.upper()}"] = json_module.dumps(value)
                else:
                    env[f"CLAUDE_{field.upper()}"] = str(value)

        try:
            # Run command with timeout
            process = await asyncio.create_subprocess_shell(
                config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=config.working_dir or context.cwd,
                env=env,
            )
            stdout, stderr = await process.communicate()

            output = stdout.decode().strip()
            stderr_output = stderr.decode().strip()

            # Claude Code compatibility: exit code 2 means block, 0 means success
            # Other non-zero exit codes are errors
            exit_code = process.returncode

            if exit_code == 2:
                # Blocking decision - parse output for reason
                modifications = {}
                reason = "Blocked by hook"

                try:
                    data = json_module.loads(output)
                    if isinstance(data, dict):
                        # Claude Code format: {"decision": "block", "reason": "...", ...}
                        modifications = data
                        if "reason" in data:
                            reason = data["reason"]
                except Exception:
                    # If not JSON, use output as reason
                    if output:
                        reason = output

                # Merge provided modifications with blocking modifications
                blocking_modifications = {
                    "decision": "block",
                    "reason": reason,
                    "exit_code": 2,
                }
                blocking_modifications.update(modifications)
                return HookResult(
                    success=False,
                    output=output,  # Include output for logging/debugging
                    should_stop=True,
                    modifications=blocking_modifications,
                )

            elif exit_code == 0:
                # Success - parse output for modifications
                modifications = {}
                try:
                    data = json_module.loads(output)
                    if isinstance(data, dict):
                        modifications = data
                except Exception:
                    # Not JSON, treat as plain output
                    pass

                return HookResult(
                    success=True, output=output, modifications=modifications
                )
            else:
                # Error case
                error_msg = f"Command failed with exit code {exit_code}"
                if stderr_output:
                    error_msg += f": {stderr_output}"
                elif output:
                    error_msg += f": {output}"

                logger.error(f"Command hook failed: {error_msg}")
                return HookResult(success=False, output=error_msg)

        except Exception as e:
            logger.error(f"Error executing command hook: {e}")
            return HookResult(success=False, output=str(e))

    return command_hook


def create_prompt_hook(config: PromptHookConfig) -> HookCallable:
    async def prompt_hook(context: HookContext) -> HookResult:
        """
        Execute a prompt hook using the LLM system.
        This runs an LLM with the given prompt template and returns the result.
        """
        try:
            # Import here to avoid circular imports
            from pydantic_ai import Agent
            from pydantic_ai.models.openai import OpenAIModel

            # Get LLM configuration
            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for prompt hook")
                return HookResult(success=False, output="No LLM model configured")

            # Parse model name (format: provider:model)
            if ":" in model_name:
                provider, model = model_name.split(":", 1)
            else:
                provider = "openai"
                model = model_name

            # Create model based on provider
            if provider == "openai":
                llm_model = OpenAIModel(model)
            else:
                # For other providers, we'd need to handle them
                # For now, use OpenAI as default
                logger.warning(
                    f"Provider {provider} not fully supported, using OpenAI"
                )
                llm_model = OpenAIModel(model)

            # Create agent with the prompt
            agent = Agent(
                model=llm_model,
                system_prompt=config.system_prompt or "",
                deps_type=dict,
            )

            # Format user prompt template with context
            # Simple template substitution using context fields
            user_prompt = config.user_prompt_template
            for field_name in dir(context):
                if not field_name.startswith("_"):
                    field_value = getattr(context, field_name)
                    if isinstance(field_value, (str, int, float, bool)):
                        placeholder = f"{{{{{field_name}}}}}"
                        if placeholder in user_prompt:
                            user_prompt = user_prompt.replace(
                                placeholder, str(field_value)
                            )

            # Run the agent
            result = await agent.run(user_prompt, deps={})

            # Parse the result for modifications
            modifications = {}
            try:
                # Try to parse as JSON if it looks like JSON
                import json

                output_text = str(result.output)
                if output_text.strip().startswith(
                    "{"
                ) and output_text.strip().endswith("}"):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except Exception:
                # Not JSON, use as plain output
                pass

            return HookResult(
                success=True, output=str(result.output), modifications=modifications
            )

        except Exception as e:
            logger.error(f"Error executing prompt hook: {e}", exc_info=True)
            return HookResult(success=False, output=str(e))

    return prompt_hook


def create_agent_hook(config: AgentHookConfig) -> HookCallable:
    async def agent_hook(context: HookContext) -> HookResult:
        """
        Execute an agent hook with tools.
        This creates an agent with the given system prompt and tools.
        """
        try:
            # Import here to avoid circular imports
            from pydantic_ai import Agent
            from pydantic_ai.models.openai import OpenAIModel

            # Get LLM configuration
            model_name = config.model or CFG.LLM_MODEL
            if not model_name:
                logger.error("No LLM model configured for agent hook")
                return HookResult(success=False, output="No LLM model configured")

            # Parse model name (format: provider:model)
            if ":" in model_name:
                provider, model = model_name.split(":", 1)
            else:
                provider = "openai"
                model = model_name

            # Create model based on provider
            if provider == "openai":
                llm_model = OpenAIModel(model)
            else:
                # For other providers, we'd need to handle them
                # For now, use OpenAI as default
                logger.warning(
                    f"Provider {provider} not fully supported, using OpenAI"
                )
                llm_model = OpenAIModel(model)

            # Create agent with system prompt
            agent = Agent(
                model=llm_model,
                system_prompt=config.system_prompt,
                deps_type=dict,
            )

            # TODO: Add tools from config.tools
            # For now, run without tools

            # Create a prompt from context
            # Use event_data or other context fields as input
            user_input = ""
            if context.event_data:
                if isinstance(context.event_data, dict):
                    user_input = str(context.event_data)
                else:
                    user_input = str(context.event_data)
            elif hasattr(context, "prompt") and context.prompt:
                user_input = context.prompt
            else:
                user_input = f"Hook event: {context.event.value}"

            # Run the agent
            result = await agent.run(user_input, deps={})

            # Parse the result for modifications
            modifications = {}
            try:
                # Try to parse as JSON if it looks like JSON
                import json

                output_text = str(result.output)
                if output_text.strip().startswith(
                    "{"
                ) and output_text.strip().endswith("}"):
                    parsed = json.loads(output_text)
                    if isinstance(parsed, dict):
                        modifications = parsed
            except Exception:
                # Not JSON, use as plain output
                pass

            return HookResult(
                success=True, output=str(result.output), modifications=modifications
            )

        except Exception as e:
            logger.error(f"Error executing agent hook: {e}", exc_info=True)
            return HookResult(success=False, output=str(e))

    return agent_hook
