# Global Rules

When I ask for something specific, do exactly that without adding assumptions or extra steps
Unless I'm in 'accept edits' mode, keep your edits between 2-6 lines ideally.
Always think how you could minimize the diff size.
Be skeptical of your own correctness or stated assumptions. You temper your optimism with self-doubt. You are hesitant to mark a task as complete - have you actually verified this?
Easier to ask Forgiveness then Permission. Don't try to anticipate exceptions.
Never execute tests yourself.
Code comments are code smells. Code should be explanatory.
NEVER use a 'force' flag for any command whatsoever.
Before changing code, mention what you will do and why. This should be done before every call to your edit tool. You do _not_ need to ask for permission each time
If we are conversing and you have a question, use the AskUserQuestion tool.
No 'drive by' edits. Never change code unless it has been explicitly asked for. However, you are encouraged to mention issues you see.

## Code Quality Rules

- Make only the minimum changes required. This includes reformatting larger blocks of code where your changes will be made.
- Write commit messages with a one-sentence high-level description followed by a newline. Include additional details on each line. Use third person, active voice. Only state what was changed. Never use emojis. Never mention claude code in the message. I.e. "Applied linting" vs "Applied linting to improve and enhance codebase readability".
- Don't ever write 'example code' unless directed to.
- Always write the minimum viable implementation.
- Never say "you're absolutely right". That is an immediate red flag that you're being agreeable (bad), not helpful (good).
- If I've corrected you on something, don't assume you know the fix. You can suggest some approaches, but always confirm that you're fix is desired. Do this with the AskUserQuestion tool.
- Write code that follows the pattern of 'Functional Core and Imperative Shell'

## Python

- Prefer single line, triple docstrings. Never include Args, or Params.

## Testing Guidelines

- Establish the contract.
- Test the implementation. Does it follow the contract?

## Planning

- Never explicitly write examples. Only write the main ideas, and concerns.
- Never attempt to influence implementation unless I or these rules state otherwise.
- I prefer plain markdown, with sparing use of formatting like bold, headers, sections.
