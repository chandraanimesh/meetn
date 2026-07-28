import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar, Pattern


class UserSentiment(str, Enum):
    NEUTRAL = "neutral"
    STRESSED = "stressed"
    HAPPY = "happy"
    EYE_STRAIN = "eye_strain"
    DARK_THEME = "dark_theme"
    LIGHT_THEME = "light_theme"
    SYSTEM_THEME = "system_theme"


@dataclass(frozen=True, slots=True)
class SafeSentimentAnalyzer:
    """Classify presentation signals without model-generated styling.

    The analyzer reads only the current user message and returns a closed enum.
    It is a presentation aid, not a medical or emotional diagnosis.
    """

    _NEGATED_THEME_REQUEST: ClassVar[Pattern[str]] = re.compile(
        r"\b(?:(?:do\s+not|don['\u2019]?t|dont|never)\s+"
        r"(?:turn|switch|change|set|use|enable|apply|follow|match|go)|"
        r"(?:turn|switch)\s+off|disable|avoid)\b.{0,32}"
        r"\b(?:dark|light|system)\s+"
        r"(?:mode|theme|setting|preference)\b",
        re.IGNORECASE,
    )
    _EXPLICIT_THEME_SIGNALS: ClassVar[
        tuple[tuple[UserSentiment, Pattern[str]], ...]
    ] = tuple(
        (
            signal,
            re.compile(
                rf"\b(?:turn|switch|change|set|use|enable|apply|follow|"
                rf"match|go)\b(?:\s+(?:the|my|this|website|site|interface))?"
                rf"(?:\s+(?:to|on))?\s+{theme}\s+"
                rf"(?:mode|theme|setting|preference)\b|"
                rf"\b(?:turn|switch|change|set|use|enable|apply)\b"
                rf"(?:\s+(?:the|my))?\s+(?:mode|theme)"
                rf"(?:\s+(?:to|on))?\s+{theme}\b",
                re.IGNORECASE,
            ),
        )
        for signal, theme in (
            (UserSentiment.DARK_THEME, "dark"),
            (UserSentiment.LIGHT_THEME, "light"),
            (UserSentiment.SYSTEM_THEME, "system"),
        )
    )
    _NEGATED_EYE_STRAIN: ClassVar[Pattern[str]] = re.compile(
        r"\b(?:my\s+)?eyes?\s+(?:are|is|feel|feels)\s+not\s+"
        r"(?:stressed|strained|tired|sore|hurting|aching)\b|"
        r"\bno\s+(?:eye|eyes)\s+(?:strain|fatigue)\b",
        re.IGNORECASE,
    )
    _EYE_STRAIN_SIGNALS: ClassVar[tuple[Pattern[str], ...]] = (
        re.compile(
            r"\bmy\s+eyes?\s+(?:are|is|feel|feels)\s+"
            r"(?:(?:really|very|so)\s+)?"
            r"(?:stressed|strained|tired|sore|hurting|aching)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:eye|eyes)\s+(?:strain|fatigue)\b|"
            r"\b(?:my\s+)?eyes?\s+(?:hurt|hurts|ache|aches)\b",
            re.IGNORECASE,
        ),
    )
    _NEGATED_STRESS: ClassVar[Pattern[str]] = re.compile(
        r"\b(?:not|no longer|do not feel|don['\u2019]?t feel)\s+"
        r"(?:stressed|anxious|overwhelmed)\b",
        re.IGNORECASE,
    )
    _STRESS_SIGNALS: ClassVar[tuple[Pattern[str], ...]] = (
        re.compile(
            r"\bi(?:\s+am|\s+m|['\u2019]m)\s+(?:feeling\s+)?"
            r"(?:(?:really|very)\s+)?(?:stressed|anxious|overwhelmed)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:feel|feeling)\s+(?:(?:really|very)\s+)?"
            r"(?:stressed|anxious|overwhelmed)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:under (?:a lot of|too much) stress|"
            r"too much stress|panicking)\b",
            re.IGNORECASE,
        ),
    )
    _NEGATED_HAPPINESS: ClassVar[Pattern[str]] = re.compile(
        r"\bi(?:\s+am|\s+m|['\u2019]m)\s+(?:not|no\s+longer)\s+"
        r"(?:feeling\s+)?(?:happy|joyful|cheerful|excited|positive)\b|"
        r"\bi\s+(?:do\s+not|don['\u2019]?t)\s+feel\s+"
        r"(?:happy|joyful|cheerful|excited|positive)\b",
        re.IGNORECASE,
    )
    _NON_MOOD_HAPPINESS: ClassVar[Pattern[str]] = re.compile(
        r"\bhappy\s+to\s+(?:help|assist|report|announce|say|confirm)\b",
        re.IGNORECASE,
    )
    _HAPPINESS_SIGNALS: ClassVar[tuple[Pattern[str], ...]] = (
        re.compile(
            r"\bi(?:\s+am|\s+m|['\u2019]m)\s+(?:feeling\s+)?"
            r"(?:(?:really|very|so)\s+)?"
            r"(?:happy|joyful|cheerful|excited|positive)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bi\s+feel\s+(?:(?:really|very|so)\s+)?"
            r"(?:happy|joyful|cheerful|excited|positive)\b|"
            r"\bi(?:['\u2019]m|\s+am)?\s+in\s+(?:a\s+)?"
            r"(?:good|great|happy)\s+mood\b",
            re.IGNORECASE,
        ),
    )

    def analyze(self, message: str) -> UserSentiment:
        normalized = message.strip()
        if not normalized:
            return UserSentiment.NEUTRAL

        if not self._NEGATED_THEME_REQUEST.search(normalized):
            for signal, pattern in self._EXPLICIT_THEME_SIGNALS:
                if pattern.search(normalized):
                    return signal

        if not self._NEGATED_EYE_STRAIN.search(normalized) and any(
            pattern.search(normalized) for pattern in self._EYE_STRAIN_SIGNALS
        ):
            return UserSentiment.EYE_STRAIN
        if not self._NEGATED_STRESS.search(normalized) and any(
            pattern.search(normalized) for pattern in self._STRESS_SIGNALS
        ):
            return UserSentiment.STRESSED
        if (
            not self._NEGATED_HAPPINESS.search(normalized)
            and not self._NON_MOOD_HAPPINESS.search(normalized)
            and any(pattern.search(normalized) for pattern in self._HAPPINESS_SIGNALS)
        ):
            return UserSentiment.HAPPY
        return UserSentiment.NEUTRAL
