import pytest

from app.agent.sentiment_analyzer import SafeSentimentAnalyzer, UserSentiment


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("i m feeling stressed", UserSentiment.STRESSED),
        ("I'm feeling anxious", UserSentiment.STRESSED),
        ("I’m overwhelmed", UserSentiment.STRESSED),
        ("i m feeling happy", UserSentiment.HAPPY),
        ("I am feeling joyful", UserSentiment.HAPPY),
        ("My eyes are stressed", UserSentiment.EYE_STRAIN),
        ("I have eye strain", UserSentiment.EYE_STRAIN),
        ("Turn to dark mode", UserSentiment.DARK_THEME),
        ("Switch the theme to light", UserSentiment.LIGHT_THEME),
        ("Follow my system theme", UserSentiment.SYSTEM_THEME),
    ],
)
def test_detects_supported_presentation_signals(
    message: str,
    expected: UserSentiment,
) -> None:
    assert SafeSentimentAnalyzer().analyze(message) is expected


@pytest.mark.parametrize(
    "message",
    [
        "I am not stressed",
        "I am not happy",
        "My eyes are not stressed",
        "Don't use dark mode",
        "Turn off dark mode",
        "Avoid the light theme",
    ],
)
def test_negated_signals_do_not_change_presentation(message: str) -> None:
    assert SafeSentimentAnalyzer().analyze(message) is UserSentiment.NEUTRAL


@pytest.mark.parametrize(
    "message",
    [
        "",
        "Dark chocolate sounds good",
        "The lighting system is online",
        "I am happy to help",
        "Open my meeting history",
    ],
)
def test_unrelated_words_remain_neutral(message: str) -> None:
    assert SafeSentimentAnalyzer().analyze(message) is UserSentiment.NEUTRAL


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("I am happy, but turn to dark mode", UserSentiment.DARK_THEME),
        ("I am stressed, but use light theme", UserSentiment.LIGHT_THEME),
        ("My eyes are tired; follow my system theme", UserSentiment.SYSTEM_THEME),
    ],
)
def test_explicit_theme_commands_take_priority_over_mood(
    message: str,
    expected: UserSentiment,
) -> None:
    assert SafeSentimentAnalyzer().analyze(message) is expected
