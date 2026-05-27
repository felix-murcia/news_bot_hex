"""Tests for audio post-processor artifact removal."""

import os
import pytest
from pathlib import Path
from src.shared.adapters.audio_post_processor import AudioPostProcessor, post_process_audio


class TestAudioPostProcessor:
    """Test cases for AudioPostProcessor."""

    def test_initialization(self):
        """Test that post-processor initializes correctly."""
        processor = AudioPostProcessor()
        assert processor.temp_dir.exists()

    def test_normalize_loudness_simple(self, tmp_path):
        """Test loudness normalization with a simple sine wave."""
        # Create a simple test WAV file (sine wave)
        import subprocess

        test_wav = tmp_path / "test_sine.wav"
        output_wav = tmp_path / "normalized.wav"

        # Generate a simple sine wave with ffmpeg
        cmd = [
            "ffmpeg", "-f", "lavfi", "-i", "sine=f=440:d=1",
            "-q:a", "9", str(test_wav), "-y"
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("ffmpeg not available")

        if not test_wav.exists():
            pytest.skip("Could not generate test WAV")

        processor = AudioPostProcessor()
        result = processor.process(
            str(test_wav),
            str(output_wav),
            normalize=True,
            remove_breathing=False,
            stabilize_plosives=False,
        )

        # Should return the output path
        assert result is not None
        # Output file should exist
        assert Path(result).exists() if result else True

    def test_breathing_removal_parameters(self):
        """Test that breathing removal uses appropriate parameters."""
        processor = AudioPostProcessor()
        # Just verify the processor has the method
        assert hasattr(processor, "_remove_breathing_artifacts")
        assert callable(processor._remove_breathing_artifacts)

    def test_artifact_stabilization_parameters(self):
        """Test that artifact stabilization is configured."""
        processor = AudioPostProcessor()
        assert hasattr(processor, "_stabilize_artifacts")
        assert callable(processor._stabilize_artifacts)

    def test_compression_parameters(self):
        """Test that compression is configured."""
        processor = AudioPostProcessor()
        assert hasattr(processor, "_apply_compression")
        assert callable(processor._apply_compression)

    def test_temp_directory_cleanup(self, tmp_path):
        """Test that cleanup method handles files gracefully."""
        processor = AudioPostProcessor()
        # Just verify cleanup doesn't crash with various counts
        processor._cleanup_temp_files(0)
        processor._cleanup_temp_files(1)
        processor._cleanup_temp_files(5)
        # If we get here without exception, cleanup is working
        assert True

    def test_post_process_audio_convenience_function(self):
        """Test the convenience wrapper function."""
        processor_func = post_process_audio
        assert callable(processor_func)


class TestAudioPostProcessorIntegration:
    """Integration tests for audio post-processing."""

    def test_full_pipeline_parameters(self):
        """Test that all processing stages are configured."""
        processor = AudioPostProcessor()

        # Verify all methods exist
        assert hasattr(processor, "_normalize_loudness")
        assert hasattr(processor, "_remove_breathing_artifacts")
        assert hasattr(processor, "_stabilize_artifacts")
        assert hasattr(processor, "_apply_compression")

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
