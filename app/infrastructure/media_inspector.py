from io import BytesIO
import wave

from app.application.ports.media_inspector import (
    MediaInspection,
    MediaInspectorPort,
)


class StandardLibraryMediaInspector(MediaInspectorPort):
    """Signature-based MIME inspection with WAV duration extraction."""

    def inspect(self, content: bytes) -> MediaInspection:
        detected_mime = self._detect_mime(content)
        duration_ms = (
            self._wav_duration_ms(content) if detected_mime == "audio/wav" else None
        )
        return MediaInspection(
            detected_mime=detected_mime,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _detect_mime(content: bytes) -> str | None:
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        ):
            return "image/webp"
        if (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WAVE"
        ):
            return "audio/wav"
        return None

    @staticmethod
    def _wav_duration_ms(content: bytes) -> int | None:
        try:
            with wave.open(BytesIO(content), "rb") as wav_file:
                frame_rate = wav_file.getframerate()
                if frame_rate <= 0:
                    return None
                return round(wav_file.getnframes() * 1000 / frame_rate)
        except (EOFError, wave.Error):
            return None
