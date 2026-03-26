from __future__ import annotations

from zrb.llm.approval.channel import ApprovalChannel, ApprovalContext, ApprovalResult


class TerminalApprovalChannel:
    def __init__(self, ui):
        self._ui = ui

    async def request_approval(self, context: ApprovalContext) -> ApprovalResult:
        from pydantic_ai import ToolCallPart

        from zrb.llm.tool_call.handler import ToolCallHandler

        call = ToolCallPart(
            tool_name=context.tool_name,
            args=context.tool_args,
            tool_call_id=context.tool_call_id,
        )
        handler = ToolCallHandler()
        message = await handler._get_confirm_user_message(self._ui, call)
        self._ui.append_to_output(f"\n\n{message}", end="")
        user_input = await self._ui.ask_user("")
        r = user_input.strip().lower()
        if r in ("y", "yes", "ok", "accept", "✅", ""):
            return ApprovalResult(approved=True)
        if r in ("n", "no", "deny", "cancel", "🛑"):
            return ApprovalResult(approved=False, message="User denied")
        if r == "e":
            import json
            import os
            import tempfile

            from zrb.config.config import CFG
            from zrb.util.yaml import yaml_dump

            self._ui.append_to_output("\n✏️ Edit mode - opening editor...\n")
            
            # Format args for editing
            args = context.tool_args
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    pass
            content_str = json.dumps(args, indent=2, ensure_ascii=False)

            with tempfile.NamedTemporaryFile(suffix=".json", mode="w+", delete=False) as tf:
                tf.write(content_str)
                tf_path = tf.name

            # Run interactive command (opens editor like vim)
            await self._ui.run_interactive_command([CFG.EDITOR, tf_path], shell=False)

            with open(tf_path, "r", encoding="utf-8") as tf:
                new_content = tf.read()
            os.remove(tf_path)

            if new_content.strip() == content_str.strip():
                self._ui.append_to_output("ℹ️ No changes made. Edit cancelled.\n")
                return ApprovalResult(approved=False, message="Edit cancelled")

            try:
                edited_args = json.loads(new_content)
                self._ui.append_to_output("✅ Approved with edited arguments.\n")
                # Wrap with __local_edit__ so the LLM engine knows it was edited
                # locally, which helps properly format the override_args
                return ApprovalResult(
                    approved=True, 
                    edited_args={"__local_edit__": True, "args_dict": edited_args}
                )
            except json.JSONDecodeError as e:
                self._ui.append_to_output(f"❌ Invalid JSON: {e}\n")
                return ApprovalResult(approved=False, message=f"Invalid JSON: {e}")

        return ApprovalResult(approved=False, message=f"User denied with: {user_input}")

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        self._ui.append_to_output(message)
