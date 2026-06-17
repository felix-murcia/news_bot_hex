"""Puerto/Interfaz para post-procesamiento de audio (Hexagonal Architecture - Port)."""

from abc import ABC, abstractmethod
from typing import Optional


class AudioPostProcessorPort(ABC):
    """Interfaz base para servicios de post-procesamiento de audio TTS."""

    @abstractmethod
    def process(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        normalize: bool = True,
        remove_breathing: bool = True,
        stabilize_plosives: bool = True,
        noise_gate_threshold: float = -40.0,
    ) -> Optional[str]:
        """Post-procesa audio para eliminar artefactos de TTS.

        Args:
            input_path: Ruta al archivo de entrada.
            output_path: Ruta de salida (si None, sobreescribe entrada).
            normalize: Aplicar normalización de volumen.
            remove_breathing: Reducir sonidos de respiración.
            stabilize_plosives: Estabilizar artefactos plosivos.
            noise_gate_threshold: Umbral en dB para noise gate.

        Returns:
            Ruta del audio procesado, o None si falla.
        """
        raise NotImplementedError()
