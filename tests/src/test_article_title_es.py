"""El LLM genera el título en español como <h1> del artículo y el pipeline lo
extrae como title_es: ya no se llama a translate_text (Google) ni para el
título ni para el contenido. El LLM lee el contenido original y traduce por
cuenta (la regla 1 de prompts/article.md ya lo exige).
"""

from unittest.mock import MagicMock, Mock

from src.news.application.usecases.article import (
    ArticleUseCase,
    _extract_title_es,
)

LONG_BODY = "<h2>Sección uno</h2><p>" + " ".join(["palabra"] * 850) + "</p>"


def _use_case(ai_model):
    posts_repo = Mock()
    arts_repo = Mock()
    verified = Mock()
    verified.get_all_news.return_value = []
    verified.get_news_by_url.return_value = None
    uc = ArticleUseCase(
        verified_repo=verified,
        generated_posts_repo=posts_repo,
        generated_articles_repo=arts_repo,
        use_ai=True,
        ai_model=ai_model,
    )
    return uc, posts_repo, arts_repo, verified


class TestExtractTitleEs:
    def test_extrae_h1(self):
        html = "<h1>El banco sube los tipos de interés</h1>" + LONG_BODY
        assert _extract_title_es(html) == "El banco sube los tipos de interés"

    def test_extrae_h1_con_etiquetas_externas(self):
        html = '<h1 class="titulo">El banco sube los tipos</h1>' + LONG_BODY
        assert _extract_title_es(html) == "El banco sube los tipos"

    def test_quita_etiquetas_incrustadas(self):
        html = "<h1><strong>El banco sube los tipos</strong></h1>"
        assert _extract_title_es(html) == "El banco sube los tipos"

    def test_quita_prefijo_titulo(self):
        html = "<h1>Título: El banco sube los tipos</h1>"
        assert _extract_title_es(html) == "El banco sube los tipos"

    def test_sin_h1_devuelve_vacio(self):
        assert _extract_title_es(LONG_BODY) == ""

    def test_h1_vacio_devuelve_vacio(self):
        assert _extract_title_es("<h1></h1>" + LONG_BODY) == ""

    def test_h1_corto_devuelve_vacio(self):
        assert _extract_title_es("<h1>Banco</h1>" + LONG_BODY) == ""

    def test_h1_basura_devuelve_vacio(self):
        assert _extract_title_es("<h1>Un momento por favor</h1>" + LONG_BODY) == ""

    def test_varios_h1_toma_el_primero(self):
        html = "<h1>Primer título válido</h1><h2>S</h2><p>x</p><h1>Segundo</h1>"
        assert _extract_title_es(html) == "Primer título válido"


class TestGenerateWithAiTitle:
    def test_devuelve_tupla_con_titulo_y_cuerpo_sin_h1(self):
        model = Mock()
        model.generate.return_value = (
            "<h1>El banco sube los tipos de interés</h1>" + LONG_BODY
        )
        uc, _, _, _ = _use_case(model)
        html, title_es = uc._generate_with_ai({"title": "Bank hiked rates"}, "news")
        assert title_es == "El banco sube los tipos de interés"
        assert "<h1>" not in html

    def test_sin_h1_en_salida_devuelve_titulo_vacio(self):
        model = Mock()
        model.generate.return_value = LONG_BODY
        uc, _, _, _ = _use_case(model)
        html, title_es = uc._generate_with_ai({"title": "Bank hiked rates"}, "news")
        assert title_es == ""
        assert "<h2>" in html

    def test_no_depende_del_traductor_de_google(self):
        import src.news.application.usecases.article as art_mod

        # article.py no debe ni importar translate_text: ni el título ni el
        # contenido pasan por la API de Google.
        assert not hasattr(art_mod, "translate_text")


class TestMakePayloadTitle:
    def test_prioriza_el_titulo_del_llm(self):
        uc, _, _, _ = _use_case(Mock())
        payload = uc.make_payload(
            {"title": "Bank hiked rates", "url": "http://x/a", "tema": "Noticias"},
            LONG_BODY,
            title_es_llm="El banco sube los tipos de interés",
        )
        assert payload["title"] == "El banco sube los tipos de interés"
        assert payload["title_es"] == "El banco sube los tipos de interés"

    def test_caee_al_title_es_del_post_si_no_hay_del_llm(self):
        uc, _, _, _ = _use_case(Mock())
        payload = uc.make_payload(
            {"title": "Bank hiked rates", "title_es": "Título traducido antes",
             "url": "http://x/a"},
            LONG_BODY,
        )
        assert payload["title"] == "Título traducido antes"

    def test_caee_al_titulo_original_si_no_hay_nada(self):
        uc, _, _, _ = _use_case(Mock())
        payload = uc.make_payload(
            {"title": "Bank hiked rates", "url": "http://x/a"}, LONG_BODY
        )
        assert payload["title"] == "Bank hiked rates"

    def test_no_depende_del_traductor_de_google(self):
        # make_payload no traduce por API: usa el título del LLM, el del post
        # o el original, en ese orden.
        uc, _, _, _ = _use_case(Mock())
        payload = uc.make_payload(
            {"title": "Bank hiked rates", "url": "http://x/a"}, LONG_BODY
        )
        assert payload["title"] == "Bank hiked rates"


class TestExecuteUpdatesPostTitle:
    def test_escribe_title_es_en_el_post_coincidente(self):
        model = Mock()
        model.generate.return_value = (
            "<h1>El banco sube los tipos de interés</h1>" + LONG_BODY
        )
        uc, posts_repo, arts_repo, verified = _use_case(model)
        verified.get_all_news.return_value = [Mock(url="http://x/a")]
        posts_repo.load_all.return_value = [
            {
                "tweet": "t",
                "title": "Bank hiked rates",
                "url": "http://x/a",
                "source": "s",
                "source_type": "news_man",
                "tema": "Noticias",
                "image_url": "",
            }
        ]

        result = uc.execute(limit=1)

        assert result, "debe generarse un artículo"
        assert result[0]["title_es"] == "El banco sube los tipos de interés"
        posts_repo.update_post.assert_called_once_with(
            "http://x/a", {"title_es": "El banco sube los tipos de interés"}
        )

    def test_no_actualiza_post_si_el_llm_no_devuelve_titulo(self):
        model = Mock()
        model.generate.return_value = LONG_BODY
        uc, posts_repo, arts_repo, verified = _use_case(model)
        verified.get_all_news.return_value = [Mock(url="http://x/a")]
        posts_repo.load_all.return_value = [
            {
                "tweet": "t",
                "title": "Bank hiked rates",
                "url": "http://x/a",
                "source": "s",
                "source_type": "news_man",
                "tema": "Noticias",
                "image_url": "",
            }
        ]

        uc.execute(limit=1)

        posts_repo.update_post.assert_not_called()


class TestMongoUpdatePost:
    def test_update_post_hace_update_one_por_url(self):
        from src.news.infrastructure.adapters.mongo_repositories import (
            MongoGeneratedPostsRepository,
        )

        db = MagicMock()
        coll = db.__getitem__.return_value
        repo = MongoGeneratedPostsRepository(db=db)
        assert repo.update_post("http://x/a", {"title_es": "T"}) is True
        coll.update_one.assert_called_once_with(
            {"url": "http://x/a"}, {"$set": {"title_es": "T"}}
        )

    def test_update_post_devuelve_false_si_falla(self):
        from src.news.infrastructure.adapters.mongo_repositories import (
            MongoGeneratedPostsRepository,
        )

        db = MagicMock()
        db.__getitem__.return_value.update_one.side_effect = RuntimeError("boom")
        repo = MongoGeneratedPostsRepository(db=db)
        assert repo.update_post("http://x/a", {"title_es": "T"}) is False
