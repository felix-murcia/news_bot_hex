"""Extractor de Jina: campo 'Title:' y recorte del ruido de página inicial.

En páginas con banner de cookies (p. ej. euronews.com) el cuerpo que devuelve
Jina empieza con ~700 líneas de banner + navegación ANTES del H1 del artículo.
El bot debe:
  - usar la metadata 'Title:' de Jina como título (antes se descartaba y el
    título salía como la primera línea del cuerpo, i.e. el banner de cookies);
  - recortar el ruido inicial para que desc/resumen/contenido empiecen por el
    artículo y no por el banner.
"""

from unittest.mock import Mock, patch

JINA_RAW = (
    "Title: Azerbaijan, Turkey and Uzbekistan join forces in major military exercise\n"
    "\n"
    "URL Source: https://www.euronews.com/2026/10/03/azerbaijan-turkey\n"
    "\n"
    "Published Time: 2026-10-03T21:26:46+02:00\n"
    "\n"
    "Markdown Content:\n"
    "Continue without agreeing →\n"
    "\n"
    "**We value your privacy**\n"
    "With your agreement, we and our partners use cookies to store data.\n"
    "\n"
    "*   [Go to navigation](https://www.euronews.com/...#enw-navigation-bar)\n"
    "*   [Go to main content](https://www.euronews.com/...#enw-main-content)\n"
    "\n"
    "# Azerbaijan, Turkey and Uzbekistan join forces in major military exercise\n"
    "\n"
    "Thousands of military personnel from Azerbaijan, Turkey and Uzbekistan\n"
    "joined forces in the “Power of Unity, 2026” military exercise.\n"
)

TITLE_ESPERADO = "Azerbaijan, Turkey and Uzbekistan join forces in major military exercise"
H1 = "# " + TITLE_ESPERADO


class TestExtraerTituloJina:

    def test_extrae_el_campo_title_de_la_cabecera(self):
        from src.shared.adapters.jina_extractor import extraer_titulo_jina

        assert extraer_titulo_jina(JINA_RAW) == TITLE_ESPERADO

    def test_devuelve_vacio_si_no_hay_campo_title(self):
        from src.shared.adapters.jina_extractor import extraer_titulo_jina

        assert extraer_titulo_jina("Markdown Content:\n# Otro titular\n\nTexto.") == ""

    def test_ignora_titles_dentro_del_cuerpo(self):
        from src.shared.adapters.jina_extractor import extraer_titulo_jina

        raw = (
            "Title: Titular real\n"
            "Markdown Content:\n"
            "# Titular real\n"
            "Title: otro texto que parece cabecera\n"
            "Cuerpo del artículo.\n"
        )
        assert extraer_titulo_jina(raw) == "Titular real"

    def test_devuelve_vacio_para_entrada_vacia(self):
        from src.shared.adapters.jina_extractor import extraer_titulo_jina

        assert extraer_titulo_jina("") == ""
        assert extraer_titulo_jina(None) == ""


class TestQuitarRuidoInicial:

    def test_recorta_el_banner_y_la_navegacion_hasta_el_h1(self):
        from src.shared.adapters.jina_extractor import quitar_ruido_inicial

        cuerpo = (
            "Continue without agreeing →\n"
            "\n"
            "**We value your privacy**\n"
            "*   [Go to navigation](https://x.example/#nav)\n"
            "\n"
            + H1 + "\n"
            "Cuerpo del artículo.\n"
        )
        limpio = quitar_ruido_inicial(cuerpo)
        assert limpio.startswith(H1)
        assert "We value your privacy" not in limpio
        assert "Cuerpo del artículo." in limpio

    def test_no_toca_el_cuerpo_si_el_h1_va_primero(self):
        from src.shared.adapters.jina_extractor import quitar_ruido_inicial

        cuerpo = H1 + "\n\nCuerpo del artículo.\n"
        assert quitar_ruido_inicial(cuerpo) == cuerpo

    def test_no_toca_si_no_hay_h1_cerca(self):
        from src.shared.adapters.jina_extractor import quitar_ruido_inicial

        ruido = "\n".join(f"Línea de navegación {i}" for i in range(400))
        cuerpo = ruido + "\n\n# H1 tardío\nCuerpo.\n"
        assert quitar_ruido_inicial(cuerpo) == cuerpo

    def test_devuelve_la_entrada_si_es_vacia(self):
        from src.shared.adapters.jina_extractor import quitar_ruido_inicial

        assert quitar_ruido_inicial("") == ""
        assert quitar_ruido_inicial(None) is None


class TestJinaExtractorDevuelveTitulo:

    def test_extract_devuelve_titulo_y_cuerpo_recortado(self):
        from src.shared.adapters.jina_extractor import JinaExtractor

        extractor = JinaExtractor()
        respuesta = Mock(status_code=200, text=JINA_RAW)
        with patch("src.shared.adapters.jina_extractor.requests.get",
                   return_value=respuesta):
            contenido, metodo, titulo = extractor.extract(
                "https://www.euronews.com/2026/10/03/azerbaijan-turkey"
            )

        assert metodo == "jina_success"
        assert titulo == TITLE_ESPERADO
        assert contenido.startswith(H1)
        assert "We value your privacy" not in contenido
        assert "Power of Unity, 2026" in contenido

    def test_extract_devuelve_titulo_vacio_si_no_hay_cabecera(self):
        from src.shared.adapters.jina_extractor import JinaExtractor

        extractor = JinaExtractor()
        respuesta = Mock(status_code=200, text=H1 + "\n\nCuerpo suficiente " * 10)
        with patch("src.shared.adapters.jina_extractor.requests.get",
                   return_value=respuesta):
            contenido, metodo, titulo = extractor.extract("https://x.example/a")

        assert metodo == "jina_success"
        assert titulo == ""
        assert contenido.startswith(H1)
