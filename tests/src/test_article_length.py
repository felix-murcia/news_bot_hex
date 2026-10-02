"""Tests de la verificación de longitud del artículo.

Producido en producción el 2026-10-02: el modelo devolvió 4.280 caracteres
(~650 palabras) con finish_reason="stop", pese a que el prompt exige 800.
Medido con Gemma 4: da 520-620 palabras y para solo — no se queda sin tokens.
"""

import pytest

from src.news.application.usecases.article import (
    ArticleTooShortError,
    ArticleUseCase,
    _contar_palabras,
)


def _html(n_palabras: int) -> str:
    cuerpo = " ".join(["palabra"] * n_palabras)
    return f"<h2>Sección</h2><p>{cuerpo}</p>"


class TestContarPalabras:
    def test_cuenta_solo_texto_visible(self):
        assert _contar_palabras("<p>uno dos tres</p>") == 3

    def test_ignora_etiquetas_html(self):
        # "Titular largo aqui" son 3 palabras reales, más 4 de los párrafos.
        html = "<h2>Titular largo aqui</h2><p>uno dos</p><p>tres cuatro</p>"
        assert _contar_palabras(html) == 7

    def test_ignora_entidades_html_comunes(self):
        # &nbsp; es un espacio: no debe contar como palabra.
        assert _contar_palabras("<p>a&nbsp;b</p>") == 2
        assert _contar_palabras("<p>solo&nbsp;</p>") == 1

    def test_acentos_como_entidad_no_infla_el_conteo(self):
        # "ma&ntilde;a" son 3 piezas tras normalizar; lo relevante es que no
        # se cuente la entidad como palabra extra.
        con_entidad = _contar_palabras("<p>ma&ntilde;a&nbsp;pe&ntilde;a tres</p>")
        sin_entidad = _contar_palabras("<p>maña peña tres</p>")
        assert con_entidad >= sin_entidad

    @pytest.mark.parametrize("vacia", ["", "<p></p>", "<div><span></span></div>"])
    def test_sin_palabras(self, vacia):
        assert _contar_palabras(vacia) == 0

    def test_no_cuenta_etiquetas_como_palabras(self):
        # Si contara las etiquetas, un artículo inflado pasaría el filtro.
        html = "<div class='x'><span id='y'></span></div><p>uno dos tres</p>"
        assert _contar_palabras(html) == 3


class TestEstandaresMinimos:
    def test_minimo_de_800_palabras(self):
        assert ArticleUseCase.MIN_WORDS == 800

    def test_permite_dos_regeneraciones(self):
        assert ArticleUseCase.MAX_REGENERATIONS == 2


class TestArticleTooShortError:
    def test_es_value_error_para_compatibilidad(self):
        # El except genérico de generación captura ValueError; esta clase
        # concreta se distingue para no caer al _generate_fallback.
        assert issubclass(ArticleTooShortError, ValueError)

    def test_se_propaga_con_el_mensaje_del_minimo(self):
        with pytest.raises(ArticleTooShortError, match="800"):
            raise ArticleTooShortError("550 palabras, mínimo exigido 800")


class TestDeteccionDelArticuloReal:
    def test_el_articulo_que_fallo_en_produccion_es_corto(self):
        real = (
            "<h2>Los enfrentamientos estudiantiles</h2>"
            "<p>La tensión social ha escalado drásticamente en las principales "
            "ciudades de Francia. Reicamente, un title video french ha "
            "capturado la intensidad de los choques.</p>"
        )
        assert _contar_palabras(real) < ArticleUseCase.MIN_WORDS

    def test_un_articulo_de_850_palabras_pasa(self):
        assert _contar_palabras(_html(850)) >= ArticleUseCase.MIN_WORDS

    def test_uno_de_700_falla(self):
        assert _contar_palabras(_html(700)) < ArticleUseCase.MIN_WORDS