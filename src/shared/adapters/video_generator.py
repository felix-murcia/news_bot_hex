"""Adaptador para generar videos a partir de audio e imagen usando el servicio ffmpeg.

Este adaptador implementa VideoGeneratorPort (arquitectura hexagonal) y
se encarga exclusivamente de la comunicación con el servicio externo ffmpeg.
La selección de imágenes está delegada en un proveedor de imágenes inyectado.
"""

import os
import random
from pathlib import Path
from typing import Optional

import requests

from config.logging_config import get_logger
from src.shared.domain.ports.video_generator_port import VideoGeneratorPort

logger = get_logger("shared.adapters.video_generator")


class ImageProvider:
    """Proveedor de imágenes. Responsabilidad separada (SRP)."""

    def __init__(self, images_dir: str):
        """
        Inicializa el proveedor de imágenes.

        Args:
            images_dir: Directorio donde se almacenan las imágenes.
        """
        self.images_dir = images_dir
        logger.info(f"[IMAGE PROVIDER] Directorio configurado: {self.images_dir}")

    def get_random_image(self) -> Optional[str]:
        """
        Selecciona una imagen aleatoria del directorio configurado.

        Returns:
            Ruta completa a una imagen aleatoria, o None si no hay imágenes.
        """
        if not os.path.exists(self.images_dir):
            logger.error(f"[IMAGE PROVIDER] Directorio no existe: {self.images_dir}")
            return None

        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

        try:
            images = [
                os.path.join(self.images_dir, f)
                for f in os.listdir(self.images_dir)
                if os.path.isfile(os.path.join(self.images_dir, f))
                and Path(f).suffix.lower() in image_extensions
            ]
        except OSError as e:
            logger.error(f"[IMAGE PROVIDER] Error al leer directorio: {e}")
            return None

        if not images:
            logger.warning(
                f"[IMAGE PROVIDER] No se encontraron imágenes en {self.images_dir}"
            )
            return None

        selected = random.choice(images)
        logger.info(
            f"[IMAGE PROVIDER] Imagen seleccionada: {os.path.basename(selected)}"
        )
        return selected


class VideoGeneratorAdapter(VideoGeneratorPort):
    """Adaptador que genera videos combinando audio e imagen.

    Responsabilidad: coordinar la generación de video a través del servicio ffmpeg.
    Delega la selección de imágenes a un ImageProvider inyectado (DIP - SOLID).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        image_provider: Optional[ImageProvider] = None,
    ):
        """
        Inicializa el generador de videos.

        Args:
            base_url: URL base del servicio ffmpeg (ej: http://localhost:8082).
                     Si es None, usa Settings.FFMPEG_API_URL.
            image_provider: Proveedor de imágenes. Si es None, se crea uno
                          con el directorio desde Settings.VIDEO_GENERATOR_IMAGES_DIR.
        """
        from config.settings import Settings

        self.base_url = base_url or Settings.FFMPEG_API_URL
        self.base_url = self.base_url.rstrip("/")
        self.create_from_audio_endpoint = f"{self.base_url}/create-from-audio"
        # Inyección de dependencia: el proveedor de imágenes es externo
        default_images_dir = Settings.VIDEO_GENERATOR_IMAGES_DIR
        self.image_provider = image_provider or ImageProvider(default_images_dir)

        logger.info(
            f"[VIDEO GENERATOR] Inicializado → endpoint: {self.create_from_audio_endpoint}"
        )

    def create_video_from_audio(
        self, audio_path: str, output_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Genera un video combinando un audio con una imagen aleatoria.

        Args:
            audio_path: Ruta al archivo de audio (MP3, WAV, etc.).
            output_path: Ruta de salida opcional para el video (ignorada,
                        el servicio genera nombre único).

        Returns:
            Ruta del video generado, o None si falla.
        """
        # Validar audio
        if not os.path.exists(audio_path):
            logger.error(f"[VIDEO GENERATOR] Audio no encontrado: {audio_path}")
            return None

        # Obtener imagen (delegado al proveedor inyectado)
        image_path = self.image_provider.get_random_image()
        if not image_path:
            logger.error("[VIDEO GENERATOR] No se pudo obtener una imagen, abortando")
            return None

        # Construir payload
        payload = {"audio_path": audio_path, "image_path": image_path}

        logger.info(
            f"[VIDEO GENERATOR] Creando video: audio={os.path.basename(audio_path)}, "
            f"image={os.path.basename(image_path)}"
        )

        try:
            resp = requests.post(
                self.create_from_audio_endpoint,
                json=payload,
                timeout=300,
            )

            if resp.status_code != 200:
                logger.error(
                    f"[VIDEO GENERATOR] Error HTTP {resp.status_code}: {resp.text[:200]}"
                )
                return None

            result = resp.json()
            output_video_path = result.get("output_path")

            if not output_video_path:
                logger.error(f"[VIDEO GENERATOR] Respuesta sin 'output_path': {result}")
                return None

            if not os.path.exists(output_video_path):
                logger.error(
                    f"[VIDEO GENERATOR] Video no generado: {output_video_path}"
                )
                return None

            file_size = os.path.getsize(output_video_path) / (1024 * 1024)
            logger.info(
                f"[VIDEO GENERATOR] ✅ Video creado: {output_video_path} "
                f"({file_size:.1f} MB) - imagen: {result.get('image_used', 'N/A')}"
            )

            return output_video_path

        except requests.exceptions.Timeout:
            logger.error("[VIDEO GENERATOR] Timeout después de 300s")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"[VIDEO GENERATOR] No se pudo conectar al servicio: {e}")
            return None
        except Exception as e:
            logger.error(f"[VIDEO GENERATOR] Error inesperado: {e}")
            return None

    def is_available(self) -> bool:
        """
        Verifica si el servicio ffmpeg está disponible.

        Returns:
            True si el servicio responde correctamente, False en caso contrario.
        """
        try:
            # El endpoint create-from-audio valida existencia de archivos,
            # usaremos un health check si existe, o un head request
            health_endpoint = f"{self.base_url}/health"
            resp = requests.get(health_endpoint, timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            # Si no hay health endpoint, probar conectividad al endpoint principal
            try:
                resp = requests.head(self.create_from_audio_endpoint, timeout=5)
                return resp.status_code in (
                    200,
                    405,
                )  # 405 = Method Not Allowed (pero endpoint existe)
            except requests.RequestException:
                return False


# Instancia global (singleton) del adaptador (para compatibilidad)
_video_generator: Optional[VideoGeneratorAdapter] = None


def get_video_generator() -> VideoGeneratorAdapter:
    """
    Obtiene la instancia global del generador de videos.
    Sigue el patrón de singleton con lazy initialization.

    Returns:
        Instancia de VideoGeneratorAdapter.
    """
    global _video_generator
    if _video_generator is None:
        _video_generator = VideoGeneratorAdapter()
    return _video_generator


def create_video_from_audio(
    audio_path: str, output_path: Optional[str] = None
) -> Optional[str]:
    """
    Función de conveniencia para generar un video a partir de un archivo de audio.

    Esta función actúa como fachada (facade pattern) y delega en la instancia
    global del adaptador (DIP - SOLID: dependencia de abstracción).

    Args:
        audio_path: Ruta al archivo de audio (MP3, WAV, etc.).
        output_path: Ruta de salida opcional para el video.

    Returns:
        Ruta del video generado, o None si falla.
    """
    return get_video_generator().create_video_from_audio(audio_path, output_path)
