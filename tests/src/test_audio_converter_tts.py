"""Tests for refactored audio/video adapters using AudioConverter HTTP service."""

import pytest
from unittest.mock import Mock, patch
import requests


class TestAudioConverter:
    """Test AudioConverter HTTP client."""

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_mp3_success(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter
        import tempfile
        import os

        wav_path = tempfile.mktemp(suffix=".wav")
        mp3_path = wav_path.replace(".wav", ".mp3")

        with open(wav_path, "w") as f:
            f.write("fake wav")
        with open(mp3_path, "w") as f:
            f.write("fake mp3")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": mp3_path}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.convert_to_mp3(wav_path)

        assert result == mp3_path
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"path": wav_path, "format": "mp3"}

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_convert_to_wav16k_success(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter
        import tempfile
        import os

        input_path = tempfile.mktemp(suffix=".mp3")
        output_path = input_path.replace(".mp3", ".wav")

        with open(input_path, "w") as f:
            f.write("fake mp3")
        with open(output_path, "w") as f:
            f.write("fake wav")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": output_path}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.convert_to_wav16k(input_path)

        assert result == output_path
        call_args = mock_post.call_args
        assert call_args[1]["json"] == {"path": input_path}

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_has_audio_stream_true(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter
        import tempfile
        import os

        video_path = tempfile.mktemp(suffix=".mp4")
        with open(video_path, "w") as f:
            f.write("fake video")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"has_audio": True}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.has_audio_stream(video_path)
        assert result is True

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_has_audio_stream_false(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter
        import tempfile
        import os

        video_path = tempfile.mktemp(suffix=".mp4")
        with open(video_path, "w") as f:
            f.write("fake video silent")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"has_audio": False}
        mock_post.return_value = mock_response

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.has_audio_stream(video_path)
        assert result is False

    @patch("src.shared.adapters.audio_converter.requests.post")
    def test_has_audio_stream_file_not_found(self, mock_post):
        from src.shared.adapters.audio_converter import AudioConverter

        converter = AudioConverter(base_url="http://localhost:8082")
        result = converter.has_audio_stream("/nonexistent/file.mp4")
        assert result is False
        # No debería hacer POST si el archivo no existe
        mock_post.assert_not_called()

    def test_initialization_uses_settings(self):
        from config.settings import Settings
        from src.shared.adapters.audio_converter import AudioConverter

        with patch.object(Settings, "FFMPEG_API_URL", "http://test:8080"):
            converter = AudioConverter()
            assert converter.base_url == "http://test:8080"
            assert (
                converter.convert_endpoint == "http://test:8080/audio/convert-by-path"
            )
            assert (
                converter.convert_wav16k_endpoint
                == "http://test:8080/audio/convert-to-wav16k"
            )
            assert (
                converter.has_audio_endpoint
                == "http://test:8080/audio/has-audio-stream"
            )


class TestTTSFactory:
    """Test TTS Factory selection."""

    @patch("src.shared.adapters.tts_factory.TTSAdapter")
    def test_get_tts_adapter_speaches(self, mock_adapter):
        from src.shared.adapters.tts_factory import get_tts_adapter

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        with patch("config.settings.Settings.TTS_MODE", "speaches"):
            result = get_tts_adapter()
            assert result is mock_instance

    @patch("src.shared.adapters.tts_factory.CoquiTTSAdapter")
    def test_get_tts_adapter_coqui(self, mock_adapter):
        from src.shared.adapters.tts_factory import get_tts_adapter

        mock_instance = Mock()
        mock_adapter.return_value = mock_instance

        with patch("config.settings.Settings.TTS_MODE", "coqui"):
            result = get_tts_adapter()
            assert result is mock_instance

    def test_get_tts_adapter_invalid_mode_fallback(self):
        from src.shared.adapters.tts_factory import get_tts_adapter

        with patch("config.settings.Settings.TTS_MODE", "invalid"):
            result = get_tts_adapter()
            from src.shared.adapters.tts_adapter import TTSAdapter

            assert isinstance(result, TTSAdapter)


class TestCoquiTTSAdapter:
    """Test Coqui TTS Adapter con conversion a MP3."""

    @patch("src.shared.adapters.coqui_tts_adapter.requests.get")
    def test_text_to_speech_returns_mp3(self, mock_get):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter
        import tempfile
        import os

        # Crear archivos WAV y MP3 temporales para que existan
        wav_path = tempfile.mktemp(suffix=".wav")
        mp3_path = wav_path.replace(".wav", ".mp3")
        with open(wav_path, "w") as f:
            f.write("fake wav")
        with open(mp3_path, "w") as f:
            f.write("fake mp3")

        # Mock GET a Coqui TTS
        mock_get_response = Mock()
        mock_get_response.status_code = 200
        mock_get_response.iter_content = lambda chunk_size: [b"fake wav data"]
        mock_get.return_value = mock_get_response

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            # Parchar el método de la instancia
            with patch.object(
                adapter.converter, "convert_to_mp3", return_value=mp3_path
            ) as mock_conv:
                result = adapter.text_to_speech("Prueba texto")

        assert result == mp3_path
        assert mock_get.called
        mock_conv.assert_called_once()
        # Verificar que se llamó con el parámetro input_path
        call_kwargs = mock_conv.call_args[1]
        assert "input_path" in call_kwargs
        assert call_kwargs["input_path"].endswith(".wav")

    @patch("src.shared.adapters.coqui_tts_adapter.requests.get")
    def test_is_available_success(self, mock_get):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            assert adapter.is_available() is True

    @patch("src.shared.adapters.coqui_tts_adapter.requests.get")
    def test_is_available_connection_error(self, mock_get):
        from src.shared.adapters.coqui_tts_adapter import CoquiTTSAdapter

        mock_get.side_effect = requests.exceptions.ConnectionError()

        with patch("config.settings.Settings.COQUI_API_URL", "http://localhost:5002"):
            adapter = CoquiTTSAdapter()
            assert adapter.is_available() is False


class TestAudioFetcherUsesConverter:
    """Test AudioFetcher usa AudioConverter para validación."""

    @patch("src.audio.infrastructure.adapters.audio_fetcher._audio_converter")
    def test_cache_hit_uses_converter(self, mock_converter):
        from src.audio.infrastructure.adapters.audio_fetcher import download_audio
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_id = "test_cache"
            cached_file = os.path.join(tmpdir, f"{audio_id}.mp3")
            with open(cached_file, "w") as f:
                f.write("x" * 2000)  # tamaño > 1024

            mock_converter.has_audio_stream.return_value = True

            result = download_audio(
                url="https://example.com/audio.mp3",
                output_dir=tmpdir,
                audio_id=audio_id,
            )

            mock_converter.has_audio_stream.assert_called_once_with(cached_file)
            assert result == cached_file

    @patch("src.audio.infrastructure.adapters.audio_fetcher._audio_converter")
    @patch("src.audio.infrastructure.adapters.audio_fetcher._download_direct")
    def test_direct_download_validates_with_converter(
        self, mock_download, mock_converter
    ):
        from src.audio.infrastructure.adapters.audio_fetcher import download_audio
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_id = "test_direct"
            downloaded_path = os.path.join(tmpdir, f"{audio_id}.mp3")
            with open(downloaded_path, "w") as f:
                f.write("x" * 2000)

            mock_download.return_value = downloaded_path
            mock_converter.has_audio_stream.return_value = True

            # Evitar yt-dlp
            with patch(
                "src.audio.infrastructure.adapters.audio_fetcher._download_with_ytdlp",
                return_value=None,
            ):
                result = download_audio(
                    url="https://example.com/audio.mp3",
                    output_dir=tmpdir,
                    audio_id=audio_id,
                )

            mock_converter.has_audio_stream.assert_called_once_with(downloaded_path)
            assert result == downloaded_path


class TestAudioTranscriberUsesConverter:
    """Test AudioTranscriber usa AudioConverter para WAV conversion."""

    @patch("src.shared.adapters.audio_converter.AudioConverter.convert_to_wav16k")
    @patch("src.audio.infrastructure.adapters.audio_transcriber._send_to_groq")
    def test_transcribe_audio_uses_converter(self, mock_send_groq, mock_convert):
        from src.audio.infrastructure.adapters.audio_transcriber import transcribe_audio
        import tempfile

        mock_convert.return_value = "/tmp/test.wav"
        mock_send_groq.return_value = "Texto transcrito"

        audio_path = tempfile.mktemp(suffix=".mp3")
        with open(audio_path, "w") as f:
            f.write("fake audio")

        result = transcribe_audio(audio_path)

        mock_convert.assert_called_once_with(audio_path)
        mock_send_groq.assert_called_once_with("/tmp/test.wav")
        assert result == "Texto transcrito"


class TestVideoTranscriberUsesConverter:
    """Test VideoTranscriber usa AudioConverter para extracción de audio."""

    @patch("src.shared.adapters.audio_converter.AudioConverter.convert_to_wav16k")
    @patch("src.video.infrastructure.adapters.video_transcriber._send_to_groq")
    def test_transcribe_video_uses_converter(self, mock_send_groq, mock_convert):
        from src.video.infrastructure.adapters.video_transcriber import transcribe_video
        import tempfile

        mock_convert.return_value = "/tmp/test.wav"
        mock_send_groq.return_value = "Texto del video"

        video_path = tempfile.mktemp(suffix=".mp4")
        with open(video_path, "w") as f:
            f.write("fake video")

        result = transcribe_video(video_path)

        mock_convert.assert_called_once_with(video_path)
        mock_send_groq.assert_called_once_with("/tmp/test.wav")
        assert result == "Texto del video"
