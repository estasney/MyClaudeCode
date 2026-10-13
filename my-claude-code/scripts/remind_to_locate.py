# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2"]
# ///
"""PreToolUse hook on searches in the main session that points Claude at the locate skill as often as the locate_reminder option says."""

import json
import os
import sys
from typing import Literal, assert_never

from pydantic import BaseModel, DirectoryPath, Field


class SearchHookInput(BaseModel):
    """Claude Code sets agent_id only when a subagent makes the call."""

    session_id: str
    agent_id: str | None = None


class PluginEnvironment(BaseModel):
    plugin_data: DirectoryPath = Field(alias="CLAUDE_PLUGIN_DATA")
    locate_reminder: Literal["once per session", "every search"] = Field(
        default="every search", alias="CLAUDE_PLUGIN_OPTION_LOCATE_REMINDER"
    )
    locate_reminder_action: Literal["warn", "stop"] = Field(
        default="warn", alias="CLAUDE_PLUGIN_OPTION_LOCATE_REMINDER_ACTION"
    )


def main() -> None:
    """Parallel searches race to create the session's marker file, and only the one that creates it reminds."""
    hook_input = SearchHookInput.model_validate_json(sys.stdin.read())
    if hook_input.agent_id is not None:
        return
    environment = PluginEnvironment.model_validate(os.environ)
    match environment.locate_reminder:
        case "once per session":
            reminded_sessions = environment.plugin_data / "locate-reminded-sessions"
            reminded_sessions.mkdir(exist_ok=True)
            try:
                (reminded_sessions / hook_input.session_id).touch(exist_ok=False)
            except FileExistsError:
                return
        case "every search":
            pass
        case unexpected:
            assert_never(unexpected)
    reminder = "To find where code is defined or used, invoke the my-claude-code:locate skill instead of Grep, Glob, or grep."
    match environment.locate_reminder_action:
        case "warn":
            output = {
                "systemMessage": "Reminded Claude to use the locate skill for searches",
                "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": reminder},
            }
        case "stop":
            output = {
                "systemMessage": "Stopped a search and told Claude to use the locate skill",
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reminder,
                },
            }
        case unexpected:
            assert_never(unexpected)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
