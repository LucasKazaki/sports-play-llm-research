"""SoccerNet-v2 label mapping for the scaled soccer-only experiment."""

from __future__ import annotations


SOCCERNET_TO_CLASS: dict[str, str] = {
    "Ball out of play": "ball_out_of_play",
    "Clearance": "clearance",
    "Corner": "corner_kick",
    "Direct free-kick": "free_kick",
    "Foul": "foul",
    "Goal": "goal",
    "Indirect free-kick": "free_kick",
    "Kick-off": "kick_off",
    "Offside": "offside",
    "Penalty": "penalty_kick",
    "Red card": "card",
    "Shots off target": "shot",
    "Shots on target": "shot",
    "Substitution": "substitution",
    "Throw-in": "throw_in",
    "Yellow card": "card",
    "Yellow->red card": "card",
}

# Background is generated only from windows separated from every labeled event.
CLASS_NAMES: tuple[str, ...] = (
    "background",
    "ball_out_of_play",
    "card",
    "clearance",
    "corner_kick",
    "foul",
    "free_kick",
    "goal",
    "kick_off",
    "offside",
    "penalty_kick",
    "shot",
    "substitution",
    "throw_in",
)

UNSUPPORTED_COACH_QUERIES: tuple[str, ...] = (
    "player identity",
    "long ball",
    "formation",
    "pressing trigger",
    "run type",
    "tactical intent",
)

EVENT_DESCRIPTIONS: dict[str, str] = {
    "background": "No supported SoccerNet-v2 event is predicted in this candidate window.",
    "ball_out_of_play": "The ball appears to leave active play.",
    "card": "A disciplinary card event is predicted; card color and recipient are not learned here.",
    "clearance": "A defensive clearance is predicted.",
    "corner_kick": "A corner-kick restart is predicted.",
    "foul": "A foul stoppage is predicted.",
    "free_kick": "A direct or indirect free-kick restart is predicted.",
    "goal": "A goal event is predicted; scorer and buildup are not learned here.",
    "kick_off": "A kick-off restart is predicted.",
    "offside": "An offside event is predicted; the offending player is not learned here.",
    "penalty_kick": "A penalty-kick event is predicted.",
    "shot": "A shot event is predicted; on-target status is collapsed in this pilot.",
    "substitution": "A substitution event is predicted.",
    "throw_in": "A throw-in restart is predicted.",
}


def mapped_class(label: str) -> str:
    try:
        return SOCCERNET_TO_CLASS[label]
    except KeyError as exc:
        raise ValueError(f"unsupported SoccerNet-v2 label: {label}") from exc

