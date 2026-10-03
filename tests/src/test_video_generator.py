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

    def test_download_image_saves_to_images_dir(self):
        """Descarga una URL y guarda el archivo en el directorio compartido."""
        from src.shared.adapters.video_generator import ImageProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ImageProvider(images_dir=tmpdir)
            with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.headers = {"Content-Type": "image/jpeg"}
                mock_resp.content = b"fake jpeg bytes"
                mock_get.return_value = mock_resp
                result = provider.download_image("https://x.example/foto.jpg")

            assert result is not None
            assert os.path.exists(result)
            assert result.startswith(tmpdir)
            assert result.endswith(".jpg")

    def test_download_image_uses_cache_when_file_exists(self):
        """Si el archivo ya existe (mismo hash de URL), no vuelve a descargar."""
        from hashlib import md5
        from src.shared.adapters.video_generator import ImageProvider

        url = "https://x.example/foto.jpg"
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ImageProvider(images_dir=tmpdir)
            expected = os.path.join(tmpdir, md5(url.encode("utf-8")).hexdigest() + ".jpg")
            with open(expected, "wb") as f:
                f.write(b"cached bytes")

            with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
                result = provider.download_image(url)

            assert result == expected
            mock_get.assert_not_called()

    def test_download_image_defaults_extension_to_jpg(self):
        """URL sin extensión (o con query) usa .jpg."""
        from src.shared.adapters.video_generator import ImageProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ImageProvider(images_dir=tmpdir)
            with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.headers = {"Content-Type": "image/jpeg"}
                mock_resp.content = b"x"
                mock_get.return_value = mock_resp
                result = provider.download_image("https://x.example/foto?w=100")

            assert result is not None
            assert result.endswith(".jpg")

    def test_download_image_returns_none_on_http_error(self):
        """Un error HTTP (404) devuelve None sin crear archivo."""
        from src.shared.adapters.video_generator import ImageProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ImageProvider(images_dir=tmpdir)
            with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 404
                mock_get.return_value = mock_resp
                result = provider.download_image("https://x.example/missing.jpg")

            assert result is None

    def test_download_image_rejects_svg(self):
        """Un SVG (p. ej. el logo de fallback) no sirve para ffmpeg → None."""
        from src.shared.adapters.video_generator import ImageProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            provider = ImageProvider(images_dir=tmpdir)
            with patch("src.shared.adapters.video_generator.requests.get") as mock_get:
                mock_resp = Mock()
                mock_resp.status_code = 200
                mock_resp.headers = {"Content-Type": "image/svg+xml"}
                mock_resp.content = b"<?xml version='1.0'?><svg xmlns='...'></svg>"
                mock_get.return_value = mock_resp
                result = provider.download_image("https://x.example/logo.svg")

            assert result is None
            # No debe dejar archivo en el directorio
            assert list(Path(tmpdir).iterdir()) == []


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

    def test_create_video_from_audio_success(self, tmp_path):
        """Debe generar video correctamente cuando el servicio responde OK."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        # Mock del image provider
        mock_provider = Mock()
        mock_provider.get_random_image.return_value = str(tmp_path / "test.jpg")

        # El servicio genera el MP4 en disco; el adaptador lo valida con exists().
        output_path = tmp_path / "test_video.mp4"
        output_path.write_bytes(b"fake mp4")

        # El adaptador también valida que el audio de entrada exista.
        audio_path = tmp_path / "test.mp3"
        audio_path.write_bytes(b"fake mp3")

        # Mock de requests.post
        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "output_path": str(output_path),
                "image_used": "test.jpg",
            }
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            result = adapter.create_video_from_audio(str(tmp_path / "test.mp3"))

            assert result == str(output_path)
            mock_provider.get_random_image.assert_called_once()
            mock_post.assert_called_once_with(
                "http://ffmpeg-service:8082/create-from-audio",
                json={
                    "audio_path": str(tmp_path / "test.mp3"),
                    "image_path": str(tmp_path / "test.jpg"),
                },
                timeout=300,
            )

    def _make_audio_and_output(self, tmp_path):
        """Crea el audio de entrada y el MP4 de salida en disco."""
        output_path = tmp_path / "video.mp4"
        output_path.write_bytes(b"fake mp4")
        audio_path = tmp_path / "a.mp3"
        audio_path.write_bytes(b"fake mp3")
        return audio_path, output_path

    def test_create_video_uses_provided_image_url(self, tmp_path):
        """Con image=URL usa la imagen descargada, no la aleatoria."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        local_img = str(tmp_path / "news.jpg")
        (tmp_path / "news.jpg").write_bytes(b"fake img")
        mock_provider.download_image.return_value = local_img
        mock_provider.get_random_image.return_value = str(tmp_path / "random.jpg")

        audio_path, output_path = self._make_audio_and_output(tmp_path)
        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output_path": str(output_path)}
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )
            result = adapter.create_video_from_audio(
                str(audio_path), image="https://x.example/img.jpg"
            )

        assert result == str(output_path)
        mock_provider.download_image.assert_called_once_with("https://x.example/img.jpg")
        mock_provider.get_random_image.assert_not_called()
        mock_post.assert_called_once_with(
            "http://ffmpeg-service:8082/create-from-audio",
            json={"audio_path": str(audio_path), "image_path": local_img},
            timeout=300,
        )

    def test_create_video_falls_back_to_random_when_image_download_fails(self, tmp_path):
        """Si la imagen solicitada no se puede resolver, usa la aleatoria."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.download_image.return_value = None
        random_img = str(tmp_path / "random.jpg")
        (tmp_path / "random.jpg").write_bytes(b"fake")
        mock_provider.get_random_image.return_value = random_img

        audio_path, output_path = self._make_audio_and_output(tmp_path)
        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output_path": str(output_path)}
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )
            result = adapter.create_video_from_audio(
                str(audio_path), image="https://x.example/bad.jpg"
            )

        assert result == str(output_path)
        mock_provider.get_random_image.assert_called_once()
        mock_post.assert_called_once_with(
            "http://ffmpeg-service:8082/create-from-audio",
            json={"audio_path": str(audio_path), "image_path": random_img},
            timeout=300,
        )

    def test_create_video_uses_local_image_path(self, tmp_path):
        """Con image=ruta local existente la usa tal cual (sin descargar ni aleatoria)."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = str(tmp_path / "random.jpg")
        local_img = tmp_path / "local.png"
        local_img.write_bytes(b"fake png")

        audio_path, output_path = self._make_audio_and_output(tmp_path)
        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output_path": str(output_path)}
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )
            result = adapter.create_video_from_audio(
                str(audio_path), image=str(local_img)
            )

        assert result == str(output_path)
        mock_provider.download_image.assert_not_called()
        mock_provider.get_random_image.assert_not_called()
        mock_post.assert_called_once_with(
            "http://ffmpeg-service:8082/create-from-audio",
            json={"audio_path": str(audio_path), "image_path": str(local_img)},
            timeout=300,
        )

    def test_create_video_from_audio_rejects_missing_output(self, tmp_path):
        """Si el servicio responde 200 pero no dejó el MP4 en disco, debe fallar."""
        from src.shared.adapters.video_generator import VideoGeneratorAdapter

        mock_provider = Mock()
        mock_provider.get_random_image.return_value = str(tmp_path / "test.jpg")

        audio_path = tmp_path / "test.mp3"
        audio_path.write_bytes(b"fake mp3")

        with patch("src.shared.adapters.video_generator.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output_path": str(tmp_path / "ghost.mp4")}
            mock_post.return_value = mock_response

            adapter = VideoGeneratorAdapter(
                base_url="http://ffmpeg-service:8082",
                image_provider=mock_provider,
            )

            assert adapter.create_video_from_audio(str(audio_path)) is None

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
