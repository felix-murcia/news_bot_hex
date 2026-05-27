"""Audio post-processor for cleaning and stabilizing TTS synthesis artifacts.

Addresses Coqui TTS issues like spectral artifacts, plosives, and breathing sounds
through normalization, filtering, and audio restoration techniques.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from config.logging_config import get_logger

logger = get_logger("news_bot.adapters.audio_post_processor")


class AudioPostProcessor:
    """Post-process TTS audio to remove synthesis artifacts and improve quality."""

    def __init__(self):
        """Initialize the post-processor."""
        self.temp_dir = Path("/tmp/audio_processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        normalize: bool = True,
        remove_breathing: bool = True,
        stabilize_plosives: bool = True,
        noise_gate_threshold: float = -40.0,
    ) -> Optional[str]:
        """
        Post-process audio to remove TTS artifacts.

        Args:
            input_path: Path to input audio file
            output_path: Path for output file (if None, overwrites input)
            normalize: Apply loudness normalization
            remove_breathing: Apply breathing sound reduction
            stabilize_plosives: Apply plosive/artifact stabilization
            noise_gate_threshold: Threshold in dB for noise gate

        Returns:
            Path to processed audio or None if processing failed
        """
        if not os.path.exists(input_path):
            logger.error(f"[AUDIO POST] Input file not found: {input_path}")
            return None

        output_path = output_path or input_path
        current_path = input_path
        temp_counter = 0

        try:
            # Step 1: Normalize loudness (LUFS-based normalization)
            if normalize:
                logger.info("[AUDIO POST] Applying loudness normalization...")
                current_path = self._normalize_loudness(current_path, temp_counter)
                temp_counter += 1
                if not current_path:
                    logger.error("[AUDIO POST] Normalization failed")
                    return None

            # Step 2: Remove breathing sounds and low-frequency rumble
            if remove_breathing:
                logger.info("[AUDIO POST] Removing breathing artifacts...")
                current_path = self._remove_breathing_artifacts(
                    current_path, temp_counter, noise_gate_threshold
                )
                temp_counter += 1
                if not current_path:
                    logger.error("[AUDIO POST] Breathing removal failed")
                    return None

            # Step 3: Stabilize plosives and spectral artifacts
            if stabilize_plosives:
                logger.info("[AUDIO POST] Stabilizing plosives and artifacts...")
                current_path = self._stabilize_artifacts(current_path, temp_counter)
                temp_counter += 1
                if not current_path:
                    logger.error("[AUDIO POST] Artifact stabilization failed")
                    return None

            # Step 4: Final compression and limiting
            logger.info("[AUDIO POST] Applying compression and limiting...")
            current_path = self._apply_compression(current_path, temp_counter)
            temp_counter += 1
            if not current_path:
                logger.error("[AUDIO POST] Compression failed")
                return None

            # Copy final result to output path
            if current_path != output_path:
                cmd = ["cp", current_path, output_path]
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info(f"[AUDIO POST] ✅ Audio saved: {output_path}")

            # Cleanup temp files
            self._cleanup_temp_files(temp_counter)

            return output_path

        except Exception as e:
            logger.error(f"[AUDIO POST] Processing failed: {e}")
            self._cleanup_temp_files(temp_counter)
            return None

    def _normalize_loudness(self, input_path: str, step: int) -> Optional[str]:
        """
        Normalize audio loudness to -23 LUFS (podcast standard).

        Uses ffmpeg-normalize for integrated loudness normalization.
        """
        output_path = self._get_temp_path(f"step{step}_normalized")

        try:
            # Use ffmpeg for EBU R128 loudness normalization
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-af", "loudnorm=I=-23:TP=-1.5:LRA=11",
                "-q:a", "9",
                output_path,
                "-y"
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"[AUDIO POST] Normalization stdout: {result.stdout[:100]}")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"[AUDIO POST] Normalization error: {e.stderr}")
            return None

    def _remove_breathing_artifacts(
        self, input_path: str, step: int, noise_gate_threshold: float
    ) -> Optional[str]:
        """
        Remove breathing sounds and low-frequency rumble.

        Uses high-pass filter (>80Hz) to remove rumble. Attempts to use noise gate
        if available, otherwise falls back to high-pass filter only.
        """
        output_path = self._get_temp_path(f"step{step}_debreathe")

        try:
            # Try with gate filter first (best quality)
            filters_with_gate = (
                f"highpass=f=80,"
                f"gate=threshold={noise_gate_threshold}dB:ratio=10:attack=0.005:release=0.1"
            )

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-af", filters_with_gate,
                "-q:a", "9",
                output_path,
                "-y"
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"[AUDIO POST] Breathing removal applied (with gate)")
            return output_path

        except subprocess.CalledProcessError as e:
            # If gate filter fails (not available), fall back to high-pass only
            if "No such filter: 'gate'" in e.stderr or "Filter not found" in e.stderr:
                logger.warning(f"[AUDIO POST] Gate filter unavailable, using high-pass only")
                try:
                    filters_fallback = "highpass=f=80"
                    cmd = [
                        "ffmpeg",
                        "-i", input_path,
                        "-af", filters_fallback,
                        "-q:a", "9",
                        output_path,
                        "-y"
                    ]
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    logger.debug(f"[AUDIO POST] Breathing removal applied (high-pass only)")
                    return output_path
                except subprocess.CalledProcessError as e2:
                    logger.error(f"[AUDIO POST] Fallback breathing removal error: {e2.stderr}")
                    return None
            else:
                logger.error(f"[AUDIO POST] Breathing removal error: {e.stderr}")
                return None

    def _stabilize_artifacts(self, input_path: str, step: int) -> Optional[str]:
        """
        Stabilize plosives, spectral artifacts, and glitches.

        Uses spectral subtraction-like approach via bass/treble boost and
        gentle EQ to smooth harsh frequencies that cause the spectral artifacts.
        """
        output_path = self._get_temp_path(f"step{step}_stabilized")

        try:
            # Subtle EQ to smooth harsh artifacts:
            # - Reduce 3-4kHz (harshness/plosives area)
            # - Slight presence boost in midrange (2-3kHz) to maintain clarity
            # - De-esser effect for sibilants
            filters = (
                "equalizer=f=3500:t=q:w=2:g=-2,"  # Reduce harshness peak
                "equalizer=f=2500:t=q:w=1.5:g=1.5,"  # Presence boost
                "equalizer=f=100:t=q:w=0.7:g=-1"  # Reduce very low rumble
            )

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-af", filters,
                "-q:a", "9",
                output_path,
                "-y"
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"[AUDIO POST] Artifact stabilization applied")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"[AUDIO POST] Stabilization error: {e.stderr}")
            return None

    def _apply_compression(self, input_path: str, step: int) -> Optional[str]:
        """
        Apply dynamic range compression and limiting.

        Gentle multiband compression to tame dynamic range and prevent clipping
        while maintaining naturalness.
        """
        output_path = self._get_temp_path(f"step{step}_compressed")

        try:
            # Gentle compression:
            # - Ratio 3:1 (moderate)
            # - Threshold -20dB (only compress loud peaks)
            # - Attack/release for smooth response
            # - Makeup gain to restore loudness
            filters = (
                "compand=attacks=0.005:decays=0.1:points=-80/-80|-20/-15|0/-10:soft-knee=6:gain=2"
            )

            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-af", filters,
                "-q:a", "9",
                output_path,
                "-y"
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.debug(f"[AUDIO POST] Compression applied")
            return output_path

        except subprocess.CalledProcessError as e:
            logger.error(f"[AUDIO POST] Compression error: {e.stderr}")
            return None

    def _get_temp_path(self, name: str) -> str:
        """Generate a temporary file path."""
        return str(self.temp_dir / f"{name}.wav")

    def _cleanup_temp_files(self, count: int) -> None:
        """Clean up temporary processing files."""
        try:
            for i in range(count):
                for suffix in ["normalized", "debreathe", "stabilized", "compressed"]:
                    temp_file = self._get_temp_path(f"step{i}_{suffix}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"[AUDIO POST] Cleaned up: {temp_file}")
        except Exception as e:
            logger.warning(f"[AUDIO POST] Cleanup error (non-critical): {e}")


def post_process_audio(
    input_path: str,
    output_path: Optional[str] = None,
    aggressive: bool = False,
) -> Optional[str]:
    """
    Convenience function to post-process audio.

    Args:
        input_path: Path to input audio file
        output_path: Path for output file
        aggressive: Use aggressive settings for heavily distorted audio

    Returns:
        Path to processed audio or None if failed
    """
    processor = AudioPostProcessor()

    # Adjust parameters based on aggressiveness
    noise_gate = -35.0 if aggressive else -40.0

    return processor.process(
        input_path=input_path,
        output_path=output_path,
        normalize=True,
        remove_breathing=True,
        stabilize_plosives=True,
        noise_gate_threshold=noise_gate,
    )
