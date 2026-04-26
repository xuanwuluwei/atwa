"""Parse cleaned terminal output into structured events.

This module contains:
- ``parse_output()``: a pure function that detects 6 stateless event types
- ``StuckDetector``: a stateful class that detects stuck agents
- ``RetryLoopDetector``: a stateful class that detects retry loops

The stateful detectors are owned and called by ``SessionTracker``,
not by ``parse_output()``.
"""

import re
from typing import TypedDict

import textdistance

from config.loader import load_config
from daemon.utils import now_ms


class ParsedEvent(TypedDict):
    """A structured event parsed from terminal output."""

    pane_id: str
    event_type: str    # one of the EVENT_* constants
    timestamp: int     # Unix ms
    data: dict         # event-type-specific payload
    confidence: float  # 0.0 - 1.0


# Event type constants
EVENT_WAITING_INPUT = "waiting_input"
EVENT_TOOL_START = "tool_start"
EVENT_TOOL_END = "tool_end"
EVENT_ERROR = "error"
EVENT_COMPLETED = "completed"
EVENT_TOKEN_USAGE = "token_usage"
EVENT_STUCK = "stuck"
EVENT_RETRY_LOOP = "retry_loop"

# --- Stateless pattern matchers ---

_WAITING_PATTERNS = [
    re.compile(r"\[y/n\]", re.IGNORECASE),
    re.compile(r"\(y/N\)|\(Y/n\)", re.IGNORECASE),
    re.compile(r"Continue\?", re.IGNORECASE),
    re.compile(r"Input required", re.IGNORECASE),
    re.compile(r"Enter your choice", re.IGNORECASE),
]

_TOOL_START_PATTERNS = [
    re.compile(r"Tool:\s*(\w+)", re.IGNORECASE),
    re.compile(r"Running\s+(\w+)", re.IGNORECASE),
    re.compile(r"Using\s+(\w+)", re.IGNORECASE),
]

_TOOL_END_PATTERNS = [
    re.compile(r"─{10,}"),
    re.compile(r"Output\b", re.IGNORECASE),
]

_ERROR_PATTERNS = [
    re.compile(r"Error:", re.IGNORECASE),
    re.compile(r"Exception:", re.IGNORECASE),
    re.compile(r"Traceback\s", re.IGNORECASE),
    re.compile(r"FAILED", re.IGNORECASE),
    re.compile(r"exit code\s+[1-9]\d*"),
]

_COMPLETED_PATTERNS = [
    re.compile(r"Task complete", re.IGNORECASE),
    re.compile(r"Done\.", re.IGNORECASE),
    re.compile(r"All tasks finished", re.IGNORECASE),
    re.compile(r"✓\s*Complete", re.IGNORECASE),
]

_TOKEN_PATTERNS = [
    re.compile(r"Tokens?:\s*(\d+)", re.IGNORECASE),
    re.compile(r"Usage:\s*in:(\d+)\s*out:(\d+)", re.IGNORECASE),
]


def _detect_waiting_input(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect prompts requiring user input."""
    events: list[ParsedEvent] = []
    for pattern in _WAITING_PATTERNS:
        if pattern.search(text):
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_WAITING_INPUT,
                timestamp=ts,
                data={},
                confidence=0.95,
            ))
            break  # one match is enough
    return events


def _detect_tool_start(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect tool invocation start."""
    events: list[ParsedEvent] = []
    for pattern in _TOOL_START_PATTERNS:
        match = pattern.search(text)
        if match:
            tool_name = match.group(1)
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_TOOL_START,
                timestamp=ts,
                data={"tool_name": tool_name},
                confidence=0.90,
            ))
            break
    return events


def _detect_tool_end(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect tool invocation end."""
    events: list[ParsedEvent] = []
    for pattern in _TOOL_END_PATTERNS:
        if pattern.search(text):
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_TOOL_END,
                timestamp=ts,
                data={},
                confidence=0.70,
            ))
            break
    return events


def _detect_error(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect error/exception patterns."""
    events: list[ParsedEvent] = []
    for pattern in _ERROR_PATTERNS:
        match = pattern.search(text)
        if match:
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_ERROR,
                timestamp=ts,
                data={"error_text": match.group(0)},
                confidence=0.95,
            ))
            break
    return events


def _detect_completed(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect task completion markers."""
    events: list[ParsedEvent] = []
    for pattern in _COMPLETED_PATTERNS:
        if pattern.search(text):
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_COMPLETED,
                timestamp=ts,
                data={},
                confidence=0.90,
            ))
            break
    return events


def _detect_token_usage(pane_id: str, text: str, ts: int) -> list[ParsedEvent]:
    """Detect token usage reporting."""
    events: list[ParsedEvent] = []
    for pattern in _TOKEN_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) == 1:
                data: dict = {"tokens": int(groups[0])}
            else:
                data = {"input_tokens": int(groups[0]), "output_tokens": int(groups[1])}
            events.append(ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_TOKEN_USAGE,
                timestamp=ts,
                data=data,
                confidence=0.95,
            ))
            break
    return events


def parse_output(pane_id: str, text: str | None) -> list[ParsedEvent]:
    """Parse cleaned text into a list of ParsedEvent.

    Pure function: same input always produces same output.
    Empty/whitespace/None input returns empty list.
    Does NOT include stuck or retry_loop detection (those are stateful).
    """
    if not text or not text.strip():
        return []

    ts = now_ms()
    events: list[ParsedEvent] = []
    events.extend(_detect_waiting_input(pane_id, text, ts))
    events.extend(_detect_tool_start(pane_id, text, ts))
    events.extend(_detect_tool_end(pane_id, text, ts))
    events.extend(_detect_error(pane_id, text, ts))
    events.extend(_detect_completed(pane_id, text, ts))
    events.extend(_detect_token_usage(pane_id, text, ts))
    return events


class StuckDetector:
    """Detect stuck agents via output similarity.

    Uses textdistance.ratcliff_obershelp on a sliding window of
    recent outputs. Fires when average pairwise similarity exceeds
    the configured threshold for a full window.
    """

    def __init__(
        self,
        threshold: float | None = None,
        window_size: int | None = None,
    ) -> None:
        cfg = load_config()
        self.threshold = threshold or cfg["thresholds"]["stuck_similarity"]
        self.window_size = window_size or cfg["thresholds"]["stuck_window"]
        self._history: dict[str, list[str]] = {}

    def update(self, pane_id: str, text: str) -> ParsedEvent | None:
        """Feed new output, return stuck event if detected."""
        history = self._history.setdefault(pane_id, [])
        history.append(text)
        if len(history) > self.window_size:
            history.pop(0)
        if len(history) < self.window_size:
            return None

        similarities = [
            textdistance.ratcliff_obershelp(history[i], history[i + 1])
            for i in range(len(history) - 1)
        ]
        avg_sim = sum(similarities) / len(similarities)

        if avg_sim >= self.threshold:
            return ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_STUCK,
                timestamp=now_ms(),
                data={"avg_similarity": avg_sim},
                confidence=min(avg_sim, 0.99),
            )
        return None

    def reset(self, pane_id: str) -> None:
        """Clear history for a pane (e.g., on status change)."""
        self._history.pop(pane_id, None)


class RetryLoopDetector:
    """Detect retry loops via repeated tool invocations.

    Fires when the same tool_name appears ``min_occurrences`` times
    within ``window_seconds`` seconds for the same pane.
    """

    def __init__(self, window_seconds: int = 60, min_occurrences: int = 3) -> None:
        self.window_seconds = window_seconds
        self.min_occurrences = min_occurrences
        self._tool_history: dict[str, list[tuple[str, int]]] = {}

    def check(self, pane_id: str, tool_name: str) -> ParsedEvent | None:
        """Record a tool_start event, return retry_loop if detected."""
        now = now_ms()
        history = self._tool_history.setdefault(pane_id, [])
        history.append((tool_name, now))

        # Prune entries outside the time window
        cutoff = now - self.window_seconds * 1000
        self._tool_history[pane_id] = [
            (name, ts) for name, ts in history if ts >= cutoff
        ]
        history = self._tool_history[pane_id]

        # Count occurrences of the same tool
        count = sum(1 for name, _ in history if name == tool_name)
        if count >= self.min_occurrences:
            return ParsedEvent(
                pane_id=pane_id,
                event_type=EVENT_RETRY_LOOP,
                timestamp=now,
                data={"tool_name": tool_name, "count": count},
                confidence=0.90,
            )
        return None

    def reset(self, pane_id: str) -> None:
        """Clear tool history for a pane."""
        self._tool_history.pop(pane_id, None)
