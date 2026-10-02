"""Tests for audio post-processor artifact removal.

These tests cover the CURRENT contract of AudioPostProcessor, which since the
ffmpeg migration (commit a6b7d37) delegates every DSP stage to the ffmpeg-api
microservice via a single HTTP POST to /audio/post-process. The former
subprocess implementation (temp_dir, _normalize_loudness, _remove_breathing_artifacts,
_stabilize_artifacts, _apply_compression, _cleanup_temp_files) no longer exists in
the adapter: that logic now lives in the ffmpeg-api service.
"""

import pytest
import requests
from unittest.mock import Mock, patch

from src.shared.adapters.audio_post_processor import AudioPostProcessor, post_process_audio

FAKE_WAV = b"RIFF$\x00\x00\x00WAVEfmt "


def _mock_response(status_code: int = 200, content: bytes = FAKE_WAV) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.content = content
    response.text = "error"
    return response


class TestAudioPostProcessor:
    """Test cases for AudioPostProcessor."""

    def test_initialization(self):
        """Post-processor must build the ffmpeg-api /audio/post-process endpoint."""
        processor = AudioPostProcessor(base_url="http://ffmpeg.test:8082/")
        assert processor.base_url == "http://ffmpeg.test:8082"
        assert processor.post_process_endpoint == "http://ffmpeg.test:8082/audio/post-process"

    def test_initialization_default_url_comes_from_settings(self):
        """Without an explicit base_url the adapter uses the configured ffmpeg-api URL."""
        with patch(
            "src.shared.adapters.audio_post_processor.get_audio_converter_url",
            return_value="http://default.test:9999",
        ):
            processor = AudioPostProcessor()
        assert processor.base_url == "http://default.test:9999"
        assert processor.post_process_endpoint == "http://default.test:9999/audio/post-process"

    def test_process_sends_every_artifact_flag(self, tmp_path):
        """All artifact-reduction stages must be forwarded to ffmpeg-api as flags."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response()
            AudioPostProcessor(base_url="http://ffmpeg.test").process(
                str(source),
                str(tmp_path / "out.wav"),
                normalize=True,
                remove_breathing=True,
                stabilize_plosives=True,
                noise_gate_threshold=-35.0,
            )

        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        payload = mock_post.call_args[1]["json"]
        assert url == "http://ffmpeg.test/audio/post-process"
        assert payload == {
            "path": str(source),
            "normalize": True,
            "remove_breathing": True,
            "stabilize_plosives": True,
            "noise_gate_threshold": -35.0,
        }

    def test_process_writes_binary_response_to_output(self, tmp_path):
        """The binary WAV body returned by ffmpeg-api must land on disk."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)
        target = tmp_path / "nested" / "out.wav"

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response(content=b"PROCESSED-AUDIO")
            result = AudioPostProcessor(base_url="http://ffmpeg.test").process(
                str(source), str(target)
            )

        assert result == str(target)
        assert target.read_bytes() == b"PROCESSED-AUDIO"

    def test_process_overwrites_input_when_no_output_path(self, tmp_path):
        """Omitting output_path must post-process the input file in place."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response(content=b"IN-PLACE")
            result = AudioPostProcessor(base_url="http://ffmpeg.test").process(str(source))

        assert result == str(source)
        assert source.read_bytes() == b"IN-PLACE"

    def test_process_returns_none_when_input_missing(self, tmp_path):
        """A missing input must short-circuit before any HTTP call."""
        missing = tmp_path / "nope.wav"

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            result = AudioPostProcessor(base_url="http://ffmpeg.test").process(str(missing))

        assert result is None
        mock_post.assert_not_called()

    @pytest.mark.parametrize("status_code", [400, 404, 500, 503])
    def test_process_returns_none_on_http_error(self, tmp_path, status_code):
        """Any non-200 from ffmpeg-api must degrade to None, never raise."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response(status_code=status_code)
            result = AudioPostProcessor(base_url="http://ffmpeg.test").process(str(source))

        assert result is None

    @pytest.mark.parametrize(
        "error",
        [
            requests.exceptions.Timeout("boom"),
            requests.exceptions.ConnectionError("boom"),
            RuntimeError("boom"),
        ],
    )
    def test_process_returns_none_on_transport_error(self, tmp_path, error):
        """Network/transport failures must degrade to None, never raise."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.side_effect = error
            result = AudioPostProcessor(base_url="http://ffmpeg.test").process(str(source))

        assert result is None

    def test_post_process_audio_convenience_function(self):
        """Test the convenience wrapper function."""
        processor_func = post_process_audio
        assert callable(processor_func)


class TestAudioPostProcessorAggressiveness:
    """The convenience wrapper maps `aggressive` onto the noise-gate threshold."""

    @pytest.mark.parametrize(
        "aggressive,expected_threshold", [(True, -35.0), (False, -40.0)]
    )
    def test_noise_gate_threshold_per_aggressiveness(
        self, tmp_path, aggressive, expected_threshold
    ):
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response()
            post_process_audio(
                input_path=str(source),
                output_path=str(tmp_path / "out.wav"),
                aggressive=aggressive,
            )

        payload = mock_post.call_args[1]["json"]
        assert payload["noise_gate_threshold"] == expected_threshold
        assert payload["normalize"] is True
        assert payload["remove_breathing"] is True
        assert payload["stabilize_plosives"] is True


class TestAudioPostProcessorIntegration:
    """Integration tests for audio post-processing."""

    def test_full_pipeline_parameters(self, tmp_path):
        """Every processing stage the adapter still owns must be enabled by default."""
        source = tmp_path / "in.wav"
        source.write_bytes(FAKE_WAV)

        with patch("src.shared.adapters.audio_post_processor.requests.post") as mock_post:
            mock_post.return_value = _mock_response()
            AudioPostProcessor(base_url="http://ffmpeg.test").process(str(source))

        payload = mock_post.call_args[1]["json"]
        assert payload["normalize"] is True
        assert payload["remove_breathing"] is True
        assert payload["stabilize_plosives"] is True
        assert payload["noise_gate_threshold"] == -40.0

    def test_aggressive_mode(self):
        """Test aggressive post-processing mode."""
        aggressive_result = post_process_audio(
            input_path="/nonexistent/file.wav",
            aggressive=True,
        )
        # Should return None for nonexistent file
        assert aggressive_result is None

    def test_non_aggressive_mode(self):
        """Test normal post-processing mode."""
        normal_result = post_process_audio(
            input_path="/nonexistent/file.wav",
            aggressive=False,
        )
        # Should return None for nonexistent file
        assert normal_result is None


class TestAudioPostProcessorDocumentation:
    """Test that post-processor is properly documented."""

    def test_module_docstring(self):
        """Test that module has appropriate docstring."""
        from src.shared.adapters import audio_post_processor

        assert audio_post_processor.__doc__ is not None
        assert "artifact" in audio_post_processor.__doc__.lower()

    def test_class_docstring(self):
        """Test that class has appropriate docstring."""
        assert AudioPostProcessor.__doc__ is not None
        assert "post-process" in AudioPostProcessor.__doc__.lower()

    def test_process_method_docstring(self):
        """Test that process method has appropriate docstring."""
        assert AudioPostProcessor.process.__doc__ is not None
        assert "normalize" in AudioPostProcessor.process.__doc__.lower()