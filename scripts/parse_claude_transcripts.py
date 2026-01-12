#!/usr/bin/env python3
"""Parse Claude JSONL transcripts from PyCharm projects into readable text files."""

import json
from pathlib import Path


def parse_jsonl_to_text(jsonl_path: Path, output_path: Path) -> None:
    """Parse a JSONL file and extract user/assistant messages to text."""
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    messages = []
    for line in lines:
        if not line.strip():
            continue
            
        try:
            data = json.loads(line)
            
            # Skip if not a message type or if it's a meta message
            if data.get('type') != 'user' and data.get('type') != 'assistant':
                continue
            if data.get('isMeta', False):
                continue
                
            message = data.get('message', {})
            role = message.get('role')
            content = message.get('content', '')
            
            # Handle content that might be a list (Claude's format)
            if isinstance(content, list):
                # Extract text from list of content objects
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                content = '\n'.join(text_parts)
            
            # Skip empty content or tool-related messages
            if not content:
                continue
            if 'antml:function_calls' in content:
                continue
            if '<invoke' in content:
                continue
            if 'function_results' in content:
                continue
            if content.startswith('<command-name>'):
                continue
            if content.startswith('<local-command-stdout>'):
                continue
                
            # Clean up system reminders and other noise
            if '<system-reminder>' in content:
                continue
                
            if role in ['user', 'assistant']:
                messages.append(f"{role}: {content.strip()}\n")
                
        except json.JSONDecodeError:
            continue
    
    # Only write to output file if we have messages
    if messages:
        with open(output_path, 'w', encoding='utf-8') as f:
            for message in messages:
                f.write(message)
                f.write('\n')


def main():
    """Main function to process all PyCharm project JSONL files."""
    
    claude_projects = Path(r"C:\Users\estasney\.claude\projects")
    output_dir = Path(r"C:\Users\estasney\Downloads\transcripts")
    
    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)
    
    # Process all PyCharm project directories
    for project_dir in claude_projects.iterdir():
        if not project_dir.is_dir():
            continue
            
        # Check if directory name contains "PycharmProjects"
        if "PycharmProjects" not in project_dir.name:
            continue
            
        print(f"Processing project: {project_dir.name}")
        
        # Process each JSONL file in the project (output directly to transcripts folder)
        for jsonl_file in project_dir.glob("*.jsonl"):
            output_file = output_dir / f"{jsonl_file.stem}.txt"
            
            try:
                parse_jsonl_to_text(jsonl_file, output_file)
                print(f"  Converted: {jsonl_file.name} -> {output_file.name}")
            except Exception as e:
                print(f"  Error processing {jsonl_file.name}: {e}")


if __name__ == "__main__":
    main()