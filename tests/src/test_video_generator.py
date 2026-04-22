"""Tests unitarios para VideoGeneratorAdapter.

Verifica:
- Selección aleatoria de imágenes
- Manejo de errores cuando no hay imágenes
- Comprobación de disponibilidad del servicio
- Construcción correcta del payload
Separación de responsabilidades (SRP) y dependencia de abstracciones (DIP).
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

import sys
import os

# Añadir raíz del proyecto al path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
sys.path.insert(0, project_root)


class TestImageProvider:
    """Tests del ImageProvider (responsabilidad separada)."""

    def test_get_random_image_returns_valid_path(self):
        """Debe devolver una ruta de imagen válida del directorio."""
        from src.shared.adapters.video_generator import ImageProvider

        # Crear directorio temporal con imágenes
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear imágenes de prueba
            img1 = Path(tmpdir) / "img1.jpg"
            img2 = Path(tmpdir) / "img2.png"
            img3 = Path(tmpdir) / "not_image.txt"
            img1.touch()
            img2.touch()
            img3.touch()  # Este no es imagen

            provider = ImageProvider(images_dir=tmpdir)
            result = provider.get_random_image()

            assert result is not None
            assert os.path.exists(result)
            assert result.endswith((".jpg", ".png"))
            # El .txt no debe ser seleccionado

    def test_get_random_image_no_images(self):
        """Debe devolver None si no hay imágenes."""
        from src.shared.adapters.video_generator import ImageProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            # Solo creamos archivos no-imagen
            (Path(tmpdir) / "file.txt").touch()
            (Path(tmpdir) / "doc.pdf").touch()

            provider = ImageProvider(images_dir=tmpdir)
            result = provider.get_random_image()

            assert result is None

    def test_get_random_image_directory_not_exists(self):
        """Debe devolver None si el directorio no existe."""
        from src.shared.adapters.video_generator import ImageProvider

        provider = ImageProvider(images_dir="/tmp/nonexistent_dir_12345")
        result = provider.get_random_image()

        assert result is None


class TestVideoGeneratorAdapter:
    """Tests del adaptador principal."""

    def test_init_uses_settings_url_by_default(self):
        """Debe usar FFMPEG_API_URL de Settings si no se proporciona base_url."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter
        from config.settings import Settings

        with patch("src.shared.adapters.video_generator.Settings") as mock_settings:
            mock_settings.FFMPEG_API_URL = "http://mock-ffmpeg:8082"
            mock_settings.VIDEO_GENERATOR_IMAGES_DIR = "/tmp/mock_images"
            adapter = VideoGeneratorAdapter()

            assert adapter.base_url == "http://mock-ffmpeg:8082"
            assert (
                adapter.create_from_audio_endpoint
                == "http://mock-ffmpeg:8082/create-from-audio"
            )

    def test_create_video_from_audio_success(self):
        """Debe generar video correctamente cuando el servicio responde OK."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        # Mock del image provider
        mock_provider = Mock()
        mock_provider.get_random_image.return_value = "/tmp/images/test.jpg"

        # Mock de requests.post
        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "output_path": "/tmp/videos/test_video.mp4",
                "image_used": "test.jpg",
            }
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )
            # Asegurar que el directorio del video existe
            os.makedirs("/tmp/videos", exist_ok=True)
            Path("/tmp/videos/test_video.mp4").touch()

            result = adapter.create_video_from_audio("/tmp/audio/test.mp3")

            assert result == "/tmp/videos/test_video.mp4"
            mock_provider.get_random_image.assert_called_once()
            mock_post.assert_called_once_with(
                "http://ffmpeg-service:8082/create-from-audio",
                json={
                    "audio_path": "/tmp/audio/test.mp3",
                    "image_path": "/tmp/images/test.jpg",
                },
                timeout=300,
            )

    def test_create_video_from_audio_audio_not_found(self):
        """Debe devolver None si el archivo de audio no existe."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = "/tmp/images/test.jpg"

        adapter = VideoGeneratorAdapter(
            base_url="http://ffmpeg-service:8082",
            image_provider=mock_provider,
        )

        result = adapter.create_video_from_audio("/tmp/audio/nonexistent.mp3")

        assert result is None

    def test_create_video_from_audio_no_image_available(self):
        """Debe devolver None si no hay imágenes disponibles."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = None

        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            result = adapter.create_video_from_audio("/tmp/audio/test.mp3")

            assert result is None
            mock_post.assert_not_called()

    def test_create_video_from_audio_ffmpeg_error(self):
        """Debe devolver None si el servicio ffmpeg responde con error."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = "/tmp/images/test.jpg"

        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            result = adapter.create_video_from_audio("/tmp/audio/test.mp3")

            assert result is None

    def test_create_video_from_audio_timeout(self):
        """Debe manejar timeout correctamente."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter
        import requests

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = "/tmp/images/test.jpg"

        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout()

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            result = adapter.create_video_from_audio("/tmp/audio/test.mp3")

            assert result is None

    def test_is_available_health_check_success(self):
        """Debe retornar True si el endpoint /health responde 200."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            adapter = VideoGeneratorAdapter(base_url="http://ffmpeg-service:8082")
            assert adapter.is_available() is True
            mock_get.assert_called_once_with(
                "http://ffmpeg-service:8082/health", timeout=5
            )

    def test_is_available_health_check_failure(self):
        """Debe retornar False si el health check falla."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter
        import requests

        with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()
            adapter = VideoGeneratorAdapter(base_url="http://ffmpeg-service:8082")
            assert adapter.is_available() is False

    def test_create_video_from_audio_invalid_json_response(self):
        """Debe manejar respuesta sin JSON correctamente."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter
        import requests

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = "/tmp/images/test.jpg"

        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("No es JSON")
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            result = adapter.create_video_from_audio("/tmp/audio/test.mp3")

            assert result is None


class TestVideoGeneratorModule:
    """Tests del módulovideo_generator (función de conveniencia)."""

    def test_create_video_from_audio_function_exists(self):
        """La función de conveniencia debe existir y ser importable."""
        from src.shared.adapters.video_generator import create_video_from_audio

        assert callable(create_video_from_audio)

    def test_get_video_generator_singleton(self):
        """get_video_generator debe retornar la misma instancia."""
        from src.shared.adapters.video_generator import get_video_generator

        gen1 = get_video_generator()
        gen2 = get_video_generator()
        assert gen1 is gen2
