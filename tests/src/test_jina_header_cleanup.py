"""Tests de limpieza de la cabecera que Jina antepone al contenido.

Sin esta limpieza el prefijo "Title:" acaba en el título del artículo, en el
slug (title-video-...), en las keywords SEO y en el texto que ve el modelo de IA.
Producido en producción el 2026-10-02: https://news.sagarebel.com/title-video-french-
students-clash-with-police-as-school-protests-spread-nationwide
"""

from src.shared.adapters.jina_extractor import limpiar_cabecera_jina


class TestLimpiarCabeceraJina:
    def test_quita_title_y_url_source(self):
        crudo = (
            "Title: Video. French students clash with police as school protests spread\n"
            "\n"
            "URL Source: https://www.euronews.com/video/2026/10/02/french-students\n"
            "\n"
            "El cuerpo del articulo empieza aqui."
        )
        limpio = limpiar_cabecera_jina(crudo)

        assert limpio.startswith("El cuerpo del articulo")
        assert "Title:" not in limpio
        assert "URL Source:" not in limpio
        assert "euronews" not in limpio

    def test_acepta_cabecera_sin_linea_en_blanco(self):
        crudo = "Title: Noticia importante\nURL Source: https://x.com/a\n\nCuerpo real."
        limpio = limpiar_cabecera_jina(crudo)

        assert limpio == "Cuerpo real."
        assert not limpio.lstrip().startswith(("Title:", "URL Source:"))

    def test_acepta_published_time_antes_de_title(self):
        crudo = "Published Time: 2026-10-02\n\nTitle: Mi titular\n\nCuerpo."
        limpio = limpiar_cabecera_jina(crudo)

        assert limpio == "Cuerpo."

    def test_no_toca_contenido_sin_cabecera(self):
        crudo = "Cuerpo sin cabecera ninguna. Sigue igual."
        assert limpiar_cabecera_jina(crudo) == crudo

    def test_no_trunca_contenido_largo_sin_cabecera(self):
        crudo = "Primer parrafo largo. " * 50
        limpio = limpiar_cabecera_jina(crudo)

        assert limpio == crudo
        assert len(limpio) > 200

    def test_preserva_el_cuerpo_completo(self):
        cuerpo = "Parrafo uno.\n\nParrafo dos.\n\nParrafo tres con detalle."
        crudo = f"Title: Noticia de prueba\n\nURL Source: https://ejemplo.com/x\n\n{cuerpo}"
        limpio = limpiar_cabecera_jina(crudo)

        assert limpio == cuerpo

    def test_entrada_vacia_o_nula(self):
        assert limpiar_cabecera_jina("") == ""
        assert limpiar_cabecera_jina(None) is None

    def test_no_fuga_published_time_cuando_hay_marcador_markdown(self):
        # Formato real de Jina: campos separados por lineas en blanco y cuerpo
        # tras "Markdown Content:". El bug dejaba "Published Time:" como 1ª
        # linea no vacia, que acababa en el titulo del articulo.
        crudo = (
            "Title: Protestas en España\n"
            "\n"
            "URL Source: https://www.bbc.co.uk/news/videos/x\n"
            "\n"
            "Published Time: Fri, 04 Sep 2026 09:35:49 GMT\n"
            "\n"
            "Markdown Content:\n"
            "Protesters gather in Madrid to demand legal protections.\n"
            "More body text here."
        )
        limpio = limpiar_cabecera_jina(crudo)
        primera = next((l for l in limpio.splitlines() if l.strip()), "")
        assert not primera.startswith(
            ("Published Time:", "URL Source:", "Title:", "Markdown Content:")
        )
        assert "Protesters gather" in limpio
        assert "Published Time:" not in limpio
        assert "Markdown Content:" not in limpio
        assert "www.bbc.co.uk" not in limpio

    def test_fallback_sin_marcador_tolera_lineas_en_blanco(self):
        crudo = (
            "URL Source: https://x.com/a\n"
            "\n"
            "Published Time: 2026-10-02\n"
            "\n"
            "Cuerpo real del articulo."
        )
        limpio = limpiar_cabecera_jina(crudo)
        primera = next((l for l in limpio.splitlines() if l.strip()), "")
        assert primera.startswith("Cuerpo real del articulo")
        assert "Published Time:" not in limpio