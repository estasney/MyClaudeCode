# Python Typing

- Use PEP 585 built-in generics (list, dict) not typing imports (List, Dict). [python, typing, pep585]

- **Match statement as type narrowing** — when a method receives a union/generic type and needs to access subclass-specific attributes, `match` with a class pattern destructures AND narrows in one expression. Works with any class (keyword patterns like `case Foo(x=x)` need no special support; positional patterns need `__match_args__`, which dataclasses provide automatically). Initial instincts for the narrowing problem were all heavyweight: signature narrowing (Liskov violation), `isinstance` (defensive against impossible state), `TypeGuard` helpers (whole function to narrow one field). Match does it in one line with zero helpers. [python, typing, pattern-matching, type-narrowing]
