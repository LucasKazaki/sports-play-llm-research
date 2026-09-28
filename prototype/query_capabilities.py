"""Pure, bounded query capability checks with explicit, independent sport profiles.

These checks neither classify sports events nor execute requested constraints.
No sport engine, index, model, filesystem or transport is imported here.

KNOWN GAP: Participant filters (jersey number/kit colour) are lexically validated but
not enforced by the saved-report ranker. Unqualified participant words remain ranking preferences; explicit bounded only-by requests are rejected.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

_SOCCER_ACTIONS = (
    r"shots?|shoot(?:s|ing)?", r"cutbacks?|cut backs?", r"pass(?:es|ing)?",
    r"cross(?:es|ing)?", r"goals?", r"saves?", r"tackles?|tackling",
    r"interceptions?|intercept(?:s|ed|ing)?", r"turnovers?", r"dribbles?|dribbling",
    r"corners?", r"penalt(?:y|ies)", r"offsides?", r"free kicks?", r"throw ins?", r"fouls?",
)
_FOOTBALL_ACTIONS = (
    r"pass(?:es|ing)?", r"run(?:s|ning)?", r"kick(?:s|ing)?",
    r"turnovers?", r"penalt(?:y|ies)",
)
_ACTIONS = {"soccer": _SOCCER_ACTIONS, "football": _FOOTBALL_ACTIONS}

_JERSEY = re.compile(
    r"(?<!\w)(?:(?:(?:jersey|shirt)(?:\s+(?:number|no\.?))?|"
    r"player(?:\s+(?:number|no\.?))?|number|no\.?)\s*#?\s*|#\s*)"
    r"([0-9]{1,3})(?!\w|[.:][0-9])"
)
_COLOURS = r"red|blue|green|white|black|yellow|orange|purple|pink|maroon|navy|gr[ae]y|gold|silver"
_KIT = re.compile(
    rf"(?<!\w)(?:wearing\s+(?:(?:a|the)\s+)?({_COLOURS})(?!\w)|"
    rf"({_COLOURS})\s+(?:kits?|shirts?|jerseys?|uniforms?)(?!\w))"
)
_KIT_WORD = r"(?:kits?|shirts?|jerseys?|uniforms?)"
_ARTICLE = r"(?:(?:a|the)\s+)?"
_NUMBERED = (
    r"(?:(?:player\s+with\s+)?(?:jersey|shirt)(?:\s+(?:number|no\.?))?|"
    r"player(?:\s+(?:number|no\.?))?|number|no\.?)\s*#?\s*[0-9]{1,3}|#\s*[0-9]{1,3}"
)
_WEARING = rf"wearing\s+{_ARTICLE}(?:{_COLOURS})(?:\s+{_KIT_WORD})?"
_COLOUR_KIT = rf"(?:{_COLOURS})\s+{_KIT_WORD}"
_DESCRIPTION = (
    rf"{_ARTICLE}(?:(?:{_NUMBERED})"
    rf"(?:\s+(?:{_WEARING}|in\s+{_ARTICLE}{_COLOUR_KIT}))?|"
    rf"(?:players?\s+)?{_WEARING}|{_COLOUR_KIT})"
)
_POSITIVE_DESCRIPTION = re.compile(rf"{_DESCRIPTION}[.!?]?")
_POSITIVE_ACTIONS = {
    "soccer": (
        r"shots?(?:\s+on\s+(?:goal|target)|\s+off\s+target)?|pass(?:es)?|cutbacks?|"
        r"cross(?:es)?|corners?|goals?|saves?|tackles?|interceptions?|dribbles?|"
        r"free\s+kicks?|throw\s+ins?|long\s+balls?"
    ),
    "football": r"passes|pass plays|runs|run plays|kicks|kick plays",
}
_POSITIVE_REQUEST = {
    sport: re.compile(
        rf"(?:find|show)(?:\s+me)?\s+(?:the\s+)?(?:{actions})\s+by\s+"
        rf"(?P<participant>{_DESCRIPTION})[.!?]?"
    ) for sport, actions in _POSITIVE_ACTIONS.items()
}


_EXCLUSIVE_REQUEST = {
    sport: re.compile(
        rf"(?:only\s+)?(?:find|show)(?:\s+me)?\s+(?:only\s+)?(?:the\s+)?"
        rf"(?:{actions})\s+(?:only\s+)?by\s+(?:only\s+)?"
        rf"(?P<participant>{_DESCRIPTION})(?:\s+only)?[.!?]?"
    ) for sport, actions in _POSITIVE_ACTIONS.items()
}


class UnsupportedParticipantConstraint(ValueError):
    """Saved reports cannot enforce this explicit single-player restriction."""

    code = "unsupported_participant_constraint"


def _normalized(text: str) -> str:
    return re.sub(r"[_\s-]+", " ", text.casefold()).strip()


class UnsupportedTemporalOrderConstraint(ValueError):
    """The selected ranker cannot enforce the requested action order."""

    code = "unsupported_temporal_order_constraint"


class UnsupportedNegationConstraint(ValueError):
    """The selected saved-report ranker cannot execute this action exclusion."""

    code = "unsupported_negation_constraint"


def check_query(query: str, sport: str) -> None:
    """Reject bounded selected-sport action exclusion and temporal-order requests."""
    if sport not in _ACTIONS:
        raise ValueError("query capability sport must be soccer or football")
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1-500 characters")
    normalized = _normalized(query)
    if re.search(r"(?<!\w)only(?!\w)", normalized) and _EXCLUSIVE_REQUEST[sport].fullmatch(normalized):
        raise UnsupportedParticipantConstraint(
            "Explicit requests for plays only by one player or kit are not supported yet. "
            "Saved-report search cannot enforce player identity or kit restrictions."
        )
    actions = "|".join(f"(?:{pattern})" for pattern in _ACTIONS[sport])
    relation = r"(?:leading\s+to|followed\s+by|that\s+follow(?:s|ed)?|before|after)"
    if re.search(
        rf"(?<!\w)(?:{actions})\s+{relation}\s+(?:(?:a|an|the)\s+)?(?:{actions})(?!\w)",
        _normalized(query),
    ):
        raise UnsupportedTemporalOrderConstraint(
            "Queries that require one action before or after another are not supported yet. "
            "Saved-report search cannot enforce temporal event order."
        )

    if re.search(rf"(?<!\w)without\s+(?:(?:a|an|any|the)\s+)?(?:{actions})(?!\w)", _normalized(query)):
        raise UnsupportedNegationConstraint(
            "Queries that exclude a recognized action are not supported yet. "
            "Saved-report search cannot enforce that exclusion."
        )


def _attributes(text: str) -> set[str]:
    text = _normalized(text)
    result = {"jersey:" + str(int(match.group(1))) for match in _JERSEY.finditer(text)}
    result.update("kit:" + (match.group(1) or match.group(2)).replace("grey", "gray")
                  for match in _KIT.finditer(text))
    return result


def validate_participant_terms(query: str, terms: Iterable[str], sport: str) -> None:
    """Bind recognized proposed attributes to one whole positive actor request.

Names, roles, arbitrary language, omitted constraints and actual visual identity
are outside this lexical guarantee. Accepted terms remain ranking preferences.
"""
    if sport not in _POSITIVE_REQUEST:
        raise ValueError("query capability sport must be soccer or football")
    request = _POSITIVE_REQUEST[sport].fullmatch(_normalized(query))
    requested = _attributes(request.group("participant")) if request else None
    unsupported = set()
    for term in terms:
        proposed = _attributes(term)
        if proposed and (requested is None or not _POSITIVE_DESCRIPTION.fullmatch(_normalized(term))
                         or not proposed.issubset(requested)):
            unsupported.update(proposed)
    if unsupported:
        raise ValueError(
            "query plan has unsupported participant attributes without a bounded positive "
            "single-participant binding: " + ", ".join(sorted(unsupported))
            + ". Literal fallback does not enforce participant or exclusion constraints."
        )
