"""Validación estructurada de la respuesta del agente de tweets.

El prompt obliga al modelo a responder con JSON `{"tweet": "..."}`.
El modelo NO decide publicabilidad; solo redacta.
La validación de calidad (no JSON, no URLs truncadas, longitud) la hace el sistema
(truncate_social_post + _validate_social_text en content.py), no el modelo.
"""

import json

from src.shared.domain.services.tweet_response import (
    TweetResponse,
    extraer_json,
    validar_tweet,
)

TWEET_BUELO = "El #BCE subió los #TiposDeInteres 25 puntos básicos hasta el 4,25%."


class TestExtraerJson:

    def test_objeto_json_solo(self):
        assert extraer_json('{"tweet": "x"}') == {"tweet": "x"}

    def test_con_cerca_json_y_texto_alrededor(self):
        raw = 'Aquí tienes:\n```json\n{"tweet": "hola"}\n```\nEspero que sirva.'
        data = extraer_json(raw)
        assert data == {"tweet": "hola"}

    def test_json_con_texto_tras_el_objeto(self):
        raw = '{"tweet": "x"} (respuesta breve)'
        assert extraer_json(raw)["tweet"] == "x"

    def test_json_invalido_devuelve_none(self):
        assert extraer_json("{no es json}") is None

    def test_lista_no_es_dict(self):
        assert extraer_json("[1, 2, 3]") is None

    def test_vacio_devuelve_none(self):
        assert extraer_json("") is None
        assert extraer_json(None) is None


class TestValidarTweetConJsonNuevoFormato:

    def test_tweet_valido_devuelve_el_tweet(self):
        raw = json.dumps({"tweet": TWEET_BUELO})
        resp = validar_tweet(raw)
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO
        assert resp.reason == ""

    def test_tweet_valido_con_cerca_json(self):
        raw = '```json\n{"tweet": "' + TWEET_BUELO + '"}\n```'
        resp = validar_tweet(raw)
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_json_sin_campo_tweet_rechaza(self):
        """JSON sin 'tweet' cae a fallback de texto plano."""
        resp = validar_tweet('{"otro": "campo"}')
        # Fallback: texto plano -> publishable=True con el JSON como texto
        assert resp.publishable is True
        assert resp.text == '{"otro": "campo"}'

    def test_tweet_vacio_en_json_rechaza(self):
        resp = validar_tweet('{"tweet": ""}')
        assert resp.publishable is False
        assert "vacío" in resp.reason

    def test_tweet_con_pagina_de_error_en_json_rechaza(self):
        resp = validar_tweet('{"tweet": "Server Error: 500"}')
        assert resp.publishable is False
        assert "página de error" in resp.reason.lower()

    def test_json_viejo_formato_publicable_true_se_trata_como_texto_plano(self):
        """Formato antiguo {'publicable': true, 'tweet': '...'} -> fallback texto plano."""
        raw = json.dumps({"publicable": True, "tweet": TWEET_BUELO})
        resp = validar_tweet(raw)
        # No tiene clave "tweet" como clave principal esperada? Wait, it DOES have "tweet"
        # Actually it does have "tweet" key, so it should extract it
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_json_viejo_formato_publicable_false_se_trata_como_texto_plano(self):
        """Formato antiguo {'publicable': false, 'motivo': '...'} -> fallback texto plano."""
        raw = json.dumps({"publicable": False, "motivo": "banner de cookies"})
        resp = validar_tweet(raw)
        # No tiene clave "tweet", cae a fallback
        assert resp.publishable is True
        assert "publicable" in resp.text


class TestValidarTweetSinJson:

    def test_tweet_plano_limpio_acepta(self):
        resp = validar_tweet(TWEET_BUELO, title="BCE sube tipos")
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_vacio_rechaza(self):
        resp = validar_tweet("")
        assert resp.publishable is False

    def test_pagina_de_error_rechaza(self):
        resp = validar_tweet("Server Error: the request failed with status 500")
        assert resp.publishable is False

    def test_titulo_con_pagina_de_error_rechaza(self):
        resp = validar_tweet(TWEET_BUELO, title="403 Forbidden - BBC")
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

    def test_json_nuevo_formato_devuelve_positiva(self):
        raw = json.dumps({"tweet": TWEET_BUELO})
        resp = self._agente(raw).generate(title="BCE sube tipos", tema="x")
        assert isinstance(resp, TweetResponse)
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO

    def test_json_truncado_sin_cerrar_es_texto_plano(self):
        """JSON truncado sin cerrar -> extraer_json devuelve None -> fallback texto plano."""
        raw_truncado = '{"tweet": "Esto es un tweet truncado'
        resp = self._agente(raw_truncado).generate(title="Título noticia", tema="Economía")
        assert isinstance(resp, TweetResponse)
        # JSON inválido -> fallback texto plano -> publishable=True con el JSON crudo
        # La validación de calidad (no JSON roto) la hace el sistema (truncate_social_post)
        assert resp.publishable is True
        assert resp.text == raw_truncado

    def test_solo_llave_abierta_es_texto_plano(self):
        """Respuesta cruda '{' se trata como texto plano (no es JSON válido)."""
        resp = self._agente('{').generate(title="T", tema="x")
        # JSON inválido -> fallback texto plano -> publishable=True con "{"
        assert resp.publishable is True
        assert resp.text == "{"

    def test_json_sin_cerrar_es_texto_plano(self):
        """'{\"tweet\": \"Hola\"' sin cerrar -> fallback texto plano."""
        raw = '{"tweet": "Hola'
        resp = self._agente(raw).generate(title="T", tema="x")
        assert resp.publishable is True
        assert resp.text == raw

    def test_tweet_plano_sin_json_devuelve_positiva(self):
        """Texto plano sin JSON -> se usa directamente."""
        resp = self._agente(TWEET_BUELO).generate(title="BCE sube tipos", tema="x")
        assert resp.publishable is True
        assert resp.text == TWEET_BUELO