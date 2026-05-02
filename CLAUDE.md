# Global Rules

- When I ask for something specific, do exactly that without adding assumptions, abstractions, or extra steps.
- NEVER use a 'force' flag for any command whatsoever. 
- Before changing code, mention what you will do and why. This should be done before every call to your edit tool. You do *not* need to ask for permission each time
- Don't assume you have a perfect re-collection of a file you read 3-5 turns ago. Always re-read.
- Always use the CLAUDE.md file at <repo_root>/.claude/CLAUDE.md. Never <repo_root>/CLAUDE.md

## Code Quality Rules

- Leave the formatting and linting fixes to tools. 
- Good code runs today. Great code is easily understandable by other developers.
- Never take any action to silence linter's warnings. This includes ignore comments, changing the linter config, etc
- If, during your work you notice an area of the codebase that you could improve, suggest a fix. If approved, you'll the codebase in a better place. 

## Python

- Write code that follows the pattern of 'Functional Core and Imperative Shell'
- Prefer single line, triple docstrings. Never include Args, or Params.
- Assume I'm using `uv`, not `pip`
- No assert statements in production code
- (Pydantic OR Dataclass) prefer over (Namedtuple) prefer over (TypedDict OR dict[str, object]) prever over (dict).

## Planning

- Never explicitly write examples. Only write the main ideas, and concerns.
- Avoid concrete references, such as file names, line numbers, derived statistics. This quickly go stale.
- Never attempt to influence implementation unless I or these rules state otherwise.
