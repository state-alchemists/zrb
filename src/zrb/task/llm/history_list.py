from typing import Any


def remove_system_prompt_and_instruction(
    history_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    for msg in history_list:
        if msg.get("instructions"):
            msg["instructions"] = ""
        msg["parts"] = [
            p for p in msg.get("parts", []) if p.get("part_kind") != "system-prompt"
        ]
    return history_list
