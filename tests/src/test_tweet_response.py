"""Validación estructurada de la respuesta del agente de tweets.

La comprobación primaria es DETERMINISTA: el prompt obliga al modelo a
responder con JSON `{"publicable": bool, "tweet"/"motivo"}` y `validar_tweet`
decide por ese campo. Los patrones solo actúan como segunda capa cuando la
respuesta no trae JSON.
"""

import json

from src.shared.domain.services.tweet_response import (
    TweetResponse,
    extraer_json,
    validar_tweet,
)

TWEET_BUELO = "El #BCE subió los #TiposDeInteres 25 puntos básicos hasta el 4,25%."
META_OBSERVADA = (
    "Por favor, proporcione el contenido de la noticia. El texto suministrado "
    "solo contiene enlaces y etiquetas de navegación, por lo que no hay "
    "información disponible para redactar el tweet."
)


class TestExtraerJson:

    def test_objeto_json_solo(self):
        assert extraer_json('{"publicable": true, "tweet": "x"}') == {
            "publicable": True,
            "tweet": "x",
        }

    def test_con_cerca_json_y_texto_alrededor(self):
        raw = 'Aquí tienes:\n```json\n{"publicable": false, "motivo": "banner"}\n```\nEspero que sirva.'
        data = extraer_json(raw)
        assert data == {"publicable": False, "motivo": "banner"}

    def test_json_con_texto_tras_el_objeto(self):
        raw = '{"publicable": true, "tweet": "x"} (respuesta breve)'
        assert extraer_json(raw)["publicable"] is True

    def test_json_invalido_devuelve_none(self):
        assert extraer_json("{no es json}") is None

    def test_lista_no_es_dict(self):
        assert extraer_json("[1, 2, 3]") is None

    def test_vacio_devuelve_none(self):
        assert extraer_json("") is None
        assert extraer_json(None) is None


class TestValidarTweetConJson:

    def test_publicable_true_devuelve_el_tweet(self):
        raw = json.dumps({"publicable": True, "tweet": TWEET_BUELO})
        resp = validar_tweet(raw)
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO
        assert resp.reason == ""

    def test_publicable_false_devuelve_el_motivo(self):
        raw = json.dumps(
            {"publicable": False, "motivo": "El contenido solo contiene enlaces de navegación"}
        )
        resp = validar_tweet(raw)
        assert resp.publishable is False
        assert resp.text == ""
        assert "enlaces de navegación" in resp.reason

    def test_publicable_true_con_cerca_json(self):
        raw = '```json\n{"publicable": true, "tweet": "' + TWEET_BUELO + '"}\n```'
        resp = validar_tweet(raw)
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_publicable_true_sin_tweet_rechaza(self):
        resp = validar_tweet('{"publicable": true}')
        assert resp.publishable is False
        assert resp.text == ""

    def test_tweet_del_json_con_negacion_rechaza(self):
        raw = json.dumps({"publicable": True, "tweet": META_OBSERVADA})
        resp = validar_tweet(raw)
        assert resp.publishable is False

    def test_publicable_str_tipo_false_rechaza(self):
        resp = validar_tweet('{"publicable": "false", "motivo": "sin hecho concreto"}')
        assert resp.publishable is False
        assert "hecho concreto" in resp.reason

    def test_campo_publicable_omitido_caen_a_segunda_capa(self):
        # Sin campo `publicable` el objeto JSON no vale: se trata como texto plano.
        resp = validar_tweet('{"otro": "campo"} El ' + TWEET_BUELO)
        assert resp.publishable is True


class TestValidarTweetSinJson:

    def test_meta_observada_en_produccion_rechaza(self):
        """El tweet publicado por error en Mastodon (BBC 2026-10-05) no puede
        volver a publicarse."""
        resp = validar_tweet(META_OBSERVADA)
        assert resp.publishable is False
        assert resp.text == ""

    def test_negacion_clasica_rechaza(self):
        resp = validar_tweet(
            "El contenido proporcionado no contiene información suficiente "
            "para generar un reporte."
        )
        assert resp.publishable is False

    def test_apologia_rechaza(self):
        resp = validar_tweet("Lo siento, no es posible generar un tweet sobre ese contenido.")
        assert resp.publishable is False

    def test_pagina_de_error_rechaza(self):
        resp = validar_tweet("Server Error: the request failed with status 500")
        assert resp.publishable is False

    def test_titulo_con_pagina_de_error_rechaza(self):
        resp = validar_tweet(TWEET_BUELO, title="403 Forbidden - BBC")
        assert resp.publishable is False

    def test_tweet_plano_limpio_acepta(self):
        resp = validar_tweet(TWEET_BUELO, title="BCE sube tipos")
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_vacio_rechaza(self):
        resp = validar_tweet("")
        assert resp.publishable is False


class TestAgenteDevuelveTweetResponse:
    """El agente parsea la respuesta cruda del LLM y devuelve TweetResponse:
    el llamador nunca manipula el texto crudo."""

    def _agente(self, raw_llm):
        from unittest.mock import Mock
        from src.shared.adapters.ai.agents.tweet_geopolitics_agent import TweetGeopoliticsAgent

        model = Mock()
        model.generate.return_value = raw_llm
        return TweetGeopoliticsAgent(model)

    def test_json_false_devuelve_negativa(self):
        resp = self._agente('{"publicable": false, "motivo": "banner de cookies"}').generate(
            title="T", tema="x", context="y"
        )
        assert isinstance(resp, TweetResponse)
        assert resp.publishable is False
        assert "banner" in resp.reason

    def test_respuesta_meta_en_texto_devuelve_negativa(self):
        resp = self._agente(META_OBSERVADA).generate(title="T", tema="x", context="y")
        assert resp.publishable is False

    def test_tweet_limpio_devuelve_positiva(self):
        resp = self._agente(TWEET_BUELO).generate(title="BCE sube tipos", tema="x")
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO
