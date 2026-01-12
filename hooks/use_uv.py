#!/usr/bin/env python3
"""
Claude Code hook for enforcing uv run usage instead of direct python commands.
"""
import json
import sys


def main():
    try:
        # Read the tool input from stdin
        data = json.load(sys.stdin)
        
        # Extract command from bash tool input
        command = data.get('tool_input', {}).get('command', '')
        
        if not command:
            sys.exit(0)
        
        # Check if command starts with 'python'
        if command.strip().startswith('python'):
            print("Use 'uv run' instead of 'python' for running Python commands", file=sys.stderr)
            sys.exit(2)  # Blocking error
        
        # Check if command starts with 'pip install'
        if command.strip().startswith('pip install'):
            print("Use 'uv add' instead of 'pip install' for installing packages", file=sys.stderr)
            sys.exit(2)  # Blocking error
        
        # Exit with success for all other commands
        sys.exit(0)
        
    except Exception:
        # If anything goes wrong, don't block
        sys.exit(0)


if __name__ == "__main__":
    main()