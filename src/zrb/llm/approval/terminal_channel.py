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
            wrap_type = None
            try:
                args = context.tool_args
                if isinstance(args, dict):
                    if "args_dict" in args:
                        args = args["args_dict"]
                        wrap_type = "args_dict"
                    elif "args_json" in args and isinstance(args["args_json"], str):
                        args = json.loads(args["args_json"])
                        wrap_type = "args_json"
                    elif "args" in args and isinstance(args["args"], str):
                        args = json.loads(args["args"])
                        wrap_type = "args"
                elif isinstance(args, str):
                    try:
                        args = json.loads(args)
                        wrap_type = "str_json"
                    except Exception:
                        pass
            except Exception:
                args = context.tool_args
            content_str = json.dumps(args, indent=2, ensure_ascii=False)

            with tempfile.NamedTemporaryFile(
                suffix=".json", mode="w+", delete=False
            ) as tf:
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

                final_args = edited_args
                if wrap_type == "args_dict":
                    final_args = {"args_dict": edited_args}
                elif wrap_type == "args_json":
                    final_args = {
                        "args_json": json.dumps(edited_args, ensure_ascii=False)
                    }
                elif wrap_type == "args":
                    final_args = {"args": json.dumps(edited_args, ensure_ascii=False)}
                elif wrap_type == "str_json":
                    final_args = json.dumps(edited_args, ensure_ascii=False)

                # Wrap with __local_edit__ so the LLM engine knows it was edited
                # locally, which helps properly format the override_args
                return ApprovalResult(
                    approved=True,
                    edited_args=(
                        {"__local_edit__": True, "args_dict": edited_args}
                        if not wrap_type
                        else final_args
                    ),
                )
            except json.JSONDecodeError as e:
                self._ui.append_to_output(f"❌ Invalid JSON: {e}\n")
                return ApprovalResult(approved=False, message=f"Invalid JSON: {e}")

        return ApprovalResult(approved=False, message=f"User denied with: {user_input}")

    async def notify(
        self, message: str, context: ApprovalContext | None = None
    ) -> None:
        self._ui.append_to_output(message)
