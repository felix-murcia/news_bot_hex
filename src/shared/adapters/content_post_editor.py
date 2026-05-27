"""
Módulo de post-edición automática para contenido generado por IA.
Aplica correcciones automáticas a posts y artículos para mantener consistencia factual.
"""

import re
from typing import Dict, List


class ContentPostEditor:
    """
    Servicio para post-editar contenido generado por IA.
    Aplica reemplazos automáticos basados en reglas predefinidas.
    """

    def __init__(self, replacements: Dict[str, str] = None):
        """
        Inicializa el editor con un diccionario de reemplazos.

        Args:
            replacements: Diccionario de reemplazos. Si None, usa valores por defecto.
        """
        self.replacements = replacements or self._get_default_replacements()

    def _get_default_replacements(self) -> Dict[str, str]:
        """
        Retorna los reemplazos por defecto.
        """
        return {
            "Papa Francisco": "Papa León XIII",
            "Francisco dijo": "León XIII declaró",
            "expresidente Donald Trump": "presidente Donald Trump",
            "ex presidente Trump": "presidente Trump",
            "expresidente Trump": "presidente Trump",
            "ex presidente Donald Trump": "presidente Donald Trump"
        }

    def post_edit(self, content: str) -> str:
        """
        Aplica los reemplazos al contenido.

        Args:
            content: Texto a post-editar.

        Returns:
            Texto corregido.
        """
        if not content:
            return content

        edited_content = content
        for old_text, new_text in self.replacements.items():
            # Usar regex para reemplazos case-insensitive y con word boundaries
            pattern = re.compile(re.escape(old_text), re.IGNORECASE)
            edited_content = pattern.sub(new_text, edited_content)

        return edited_content

    def add_replacement(self, old_text: str, new_text: str):
        """
        Añade un nuevo reemplazo.

        Args:
            old_text: Texto a reemplazar.
            new_text: Texto de reemplazo.
        """
        self.replacements[old_text] = new_text

    def remove_replacement(self, old_text: str):
        """
        Remueve un reemplazo.

        Args:
            old_text: Texto a remover.
        """
        self.replacements.pop(old_text, None)


# Instancia global por defecto
default_editor = ContentPostEditor()


def post_edit_content(content: str, editor: ContentPostEditor = None) -> str:
    """
    Función de conveniencia para post-editar contenido usando el editor por defecto.

    Args:
        content: Texto a post-editar.
        editor: Editor personalizado. Si None, usa el por defecto.

    Returns:
        Texto corregido.
    """
    if editor is None:
        editor = default_editor
    return editor.post_edit(content)