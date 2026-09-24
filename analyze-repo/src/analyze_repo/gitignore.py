import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "IgnoreRule",
    "IgnoreScope",
    "is_ignored",
    "parse_gitignore",
]


@dataclass(frozen=True)
class IgnoreRule:
    """One .gitignore line, matched against a path relative to the file's directory."""

    pattern: re.Pattern[str]
    negated: bool
    directory_only: bool

    def matches(self, relative_path: str, *, is_directory: bool) -> bool:
        if self.directory_only and not is_directory:
            return False
        return self.pattern.fullmatch(relative_path) is not None


def parse_gitignore(lines: Iterable[str]) -> list[IgnoreRule]:
    rules: list[IgnoreRule] = []
    for raw in lines:
        line = strip_unescaped_trailing_spaces(raw.rstrip("\r\n"))
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        directory_only = line.endswith("/")
        if directory_only:
            line = line[:-1]
        anchored = "/" in line
        line = line.removeprefix("/")
        if not line:
            continue
        prefix = "" if anchored else "(?:.*/)?"
        rules.append(
            IgnoreRule(
                pattern=re.compile(prefix + glob_to_regex(line)),
                negated=negated,
                directory_only=directory_only,
            )
        )
    return rules


@dataclass(frozen=True)
class IgnoreScope:
    """The rules of one .gitignore, applying below the directory that holds it."""

    directory: Path
    rules: Sequence[IgnoreRule]


def is_ignored(
    scopes: Sequence[IgnoreScope], path: Path, *, is_directory: bool
) -> bool:
    """Scopes run shallow to deep and the last matching rule wins, as in git."""
    ignored = False
    for scope in scopes:
        relative_path = path.relative_to(scope.directory).as_posix()
        for rule in scope.rules:
            if rule.matches(relative_path, is_directory=is_directory):
                ignored = not rule.negated
    return ignored


def strip_unescaped_trailing_spaces(line: str) -> str:
    """A backslash protects the character after it, so `\\ ` keeps its space."""
    trailing_spaces_start: int | None = None
    position = 0
    while position < len(line):
        char = line[position]
        if char == " ":
            if trailing_spaces_start is None:
                trailing_spaces_start = position
        elif char == "\\":
            position += 1
            trailing_spaces_start = None
        else:
            trailing_spaces_start = None
        position += 1
    return line if trailing_spaces_start is None else line[:trailing_spaces_start]


def never_matching_regex() -> str:
    return "(?!)"


def glob_to_regex(pattern: str) -> str:
    """Follows git's wildmatch; a malformed pattern yields a regex that matches nothing."""
    parts: list[str] = []
    position = 0
    while position < len(pattern):
        char = pattern[position]
        if char == "\\":
            if position + 1 >= len(pattern):
                return never_matching_regex()
            parts.append(re.escape(pattern[position + 1]))
            position += 2
        elif char == "*":
            regex, position = stars_to_regex(pattern, position)
            parts.append(regex)
        elif char == "?":
            parts.append("[^/]")
            position += 1
        elif char == "[":
            bracket = bracket_to_regex(pattern, position)
            if bracket is None:
                return never_matching_regex()
            regex, position = bracket
            parts.append(regex)
        else:
            parts.append(re.escape(char))
            position += 1
    return "".join(parts)


def stars_to_regex(pattern: str, start: int) -> tuple[str, int]:
    """Two or more stars bordered by slashes or pattern ends cross directories."""
    position = start
    while position < len(pattern) and pattern[position] == "*":
        position += 1
    at_segment_start = start == 0 or pattern[start - 1] == "/"
    rest = pattern[position:]
    if position - start == 1 or not at_segment_start:
        return "[^/]*", position
    if rest.startswith("/"):
        return "(?:.*/)?", position + 1
    if not rest or rest.startswith("\\/"):
        return ".*", position
    return "[^/]*", position


def bracket_to_regex(pattern: str, start: int) -> tuple[str, int] | None:
    """None when git would abort the match: unterminated set or unknown class."""
    position = start + 1
    negate = position < len(pattern) and pattern[position] in "!^"
    if negate:
        position += 1
    members: list[str] = []
    previous: str | None = None
    first = True
    while position < len(pattern):
        char = pattern[position]
        if char == "]" and not first:
            return class_regex(members, negate=negate), position + 1
        first = False
        if char == "[" and pattern.startswith("[:", position):
            end = pattern.find("]", position + 2)
            if end == -1:
                return None
            if pattern[end - 1] == ":":
                class_members = posix_class_members(pattern[position + 2 : end - 1])
                if class_members is None:
                    return None
                members.append(class_members)
                position = end + 1
                previous = None
                continue
        if (
            char == "-"
            and previous is not None
            and pattern[position + 1 : position + 2] not in {"", "]"}
        ):
            high, position = escaped_or_literal(pattern, position + 1)
            if high is None:
                return None
            if previous <= high:
                members.append(f"{re.escape(previous)}-{re.escape(high)}")
            previous = None
            continue
        literal, position = escaped_or_literal(pattern, position)
        if literal is None:
            return None
        members.append(re.escape(literal))
        previous = literal
    return None


def escaped_or_literal(pattern: str, position: int) -> tuple[str | None, int]:
    """The character at position, or the one a backslash there protects; None at the end."""
    if pattern[position] == "\\":
        position += 1
        if position >= len(pattern):
            return None, position
    return pattern[position], position + 1


def class_regex(members: Sequence[str], *, negate: bool) -> str:
    """A bracket expression matches one character that is not a slash."""
    if not members:
        return "[^/]" if negate else never_matching_regex()
    body = "".join(members)
    return f"(?!/)[^{body}]" if negate else f"(?!/)[{body}]"


def posix_class_members(name: str) -> str | None:
    classes = {
        "alnum": "a-zA-Z0-9",
        "alpha": "a-zA-Z",
        "blank": " \\t",
        "cntrl": "\\x00-\\x1f\\x7f",
        "digit": "0-9",
        "graph": "\\x21-\\x7e",
        "lower": "a-z",
        "print": "\\x20-\\x7e",
        "punct": "!-/:-@\\[-`{-~",
        "space": " \\t\\n\\r\\f\\v",
        "upper": "A-Z",
        "xdigit": "0-9A-Fa-f",
    }
    return classes.get(name)
