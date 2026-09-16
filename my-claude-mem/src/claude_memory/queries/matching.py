import re


def match_expression(phrase: str) -> str | None:
    """Quotes every alphanumeric term and joins them with OR; None when the phrase has no terms."""
    terms = re.findall(r"[^\W_]+", phrase)
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in terms)
