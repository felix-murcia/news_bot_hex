"""Configuración raíz de la suite de tests.

Decisiones RATIFICADAS por Felix (Fase 4):

  1. El marker `production` SE QUEDA como uno solo. Se evaluó partirlo en
     `production-readonly` / `production-write` y se descarta: con el clon de
     producción (decisión 2) la escritura es inofensiva, así que partir el
     marker sólo añadiría una dimensión de configuración sin ganancia. El
     marker sigue siendo opt-in por `NEWS_BOT_RUN_PRODUCTION_TESTS`.

  2. El modo producción afirma contra un CLÓN de `appdb`, nunca contra `appdb`.
     `appdb` es inmutable desde la suite: se clona al inicio de la sesión y el
     clon se dropea al terminar. Ver `_production_clone_provisioned`.

  3. `number_to_words` lee magnitudes (`number_to_words.py`), no dígitos.

  4. Las credenciales se inyectan aquí como placeholders INERTES. Los
     publicadores lanzan en el IMPORT si faltan (facebook_publisher.py:22,
     mastodon_publisher.py:26), así que sin esto la suite dependía de que el
     `.env` del desarrollador las tuviera puestas. `AI_PROVIDER` se fuerza a
     `mock`: los tests unitarios no salen a la red.

  5. CI ejecuta el modo producción en un job propio (`.github/workflows/ci.yml`).

Por qué la inyección va AQUÍ y no en una fixture:
    `Settings.MONGO_DB_NAME` se evalúa con `os.getenv` en el CUERPO de la clase
    (config/settings.py:267), es decir, AL IMPORTAR `config.settings`. Una
    fixture `monkeypatch` o incluso una fixture autouse se ejecutan DESPUÉS del
    import de los módulos de test, demasiado tarde. El conftest raíz se importa
    antes que cualquier módulo de test, por lo que es el único punto fiable.

    `load_dotenv()` se llama sin `override=True` en varios módulos, por lo que
    nunca reescribe un valor ya presente en `os.environ`: por eso esto gana
    siempre, incluso aunque el `.env` del desarrollador apunte a producción.

Modos de uso:
    Hermético (por defecto):
        .venv/bin/python -m pytest tests/
    Producción contra el CLON de appdb (opt-in):
        NEWS_BOT_RUN_PRODUCTION_TESTS=1 .venv/bin/python -m pytest tests/
"""

import os
import pathlib
import sys
import time

import pytest
from pymongo import IndexModel

ROOT = pathlib.Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# BD de producción. Inmutable desde la suite (decisión 2).
PRODUCTION_DB = "appdb"

# BD de pruebas del modo hermético.
TEST_DB = os.getenv("MONGO_DB_NAME_TEST", "appdb_test")

# BD donde se clona `appdb` para que el modo producción pueda escribir sin
# contaminar (decisión 2).
PRODUCTION_CLONE_DB = os.getenv("MONGO_DB_NAME_PROD_CLONE", "appdb_prod_clone")

# Activar con NEWS_BOT_RUN_PRODUCTION_TESTS=1 para ejecutar los tests que
# afirman datos reales (marca `production`).
RUN_PRODUCTION_ENV = "NEWS_BOT_RUN_PRODUCTION_TESTS"

# Credenciales inertes (decisión 4). Valores NO secretos: sólo evitan que el
# import de los publicadores reviente. Ningún test hace red con ellos.
INERT_PLACEHOLDERS = {
    "FACEBOOK_PAGE_ID": "test-page-id",
    "FACEBOOK_PAGE_ACCESS_TOKEN": "test-page-token",
    "MASTODON_INSTANCE_URL": "https://mastodon.test",
    "MASTODON_ACCESS_TOKEN": "test-access-token",
    "BLUESKY_HANDLE": "test.bsky.test",
    "BLUESKY_APP_PASSWORD": "test-app-password",
}


def production_mode_enabled() -> bool:
    """True si este run autoriza aserciones contra los datos reales de appdb."""
    return os.getenv(RUN_PRODUCTION_ENV, "").strip().lower() in {"1", "true", "yes"}


def production_data_db() -> str:
    """Nombre de la BD que los tests marcados `production` deben usar.

    Es SIEMPRE el clon: la suite nunca abre `appdb` para affirmedatos.
    Los tests de producción comparan contra este helper, no contra el literal
    'appdb', para que el contrato sea "afirmar contra los datos reales" y no
    "afirmar contra un nombre de base de datos".
    """
    return PRODUCTION_CLONE_DB


# --- Guardas de nombres de BD ------------------------------------------------

# Si alguien apunta la suite a appdb, abortamos en vez de contaminar producción.
if TEST_DB == PRODUCTION_DB:
    raise RuntimeError(
        f"MONGO_DB_NAME_TEST no puede ser '{PRODUCTION_DB}': la suite nunca debe "
        f"escribir en la base de datos de producción."
    )

# El clon existe precisamente para NO ser appdb. Si alguien lo renombra,
# la protección se evaporaría y el teardown borraría producción.
if PRODUCTION_CLONE_DB in (PRODUCTION_DB, TEST_DB):
    raise RuntimeError(
        f"MONGO_DB_NAME_PROD_CLONE ('{PRODUCTION_CLONE_DB}') colisiona con "
        f"'{PRODUCTION_DB}' o '{TEST_DB}'. El clon debe ser una BD propia."
    )


# --- Inyección de entorno (DEBE ocurrir antes de importar config.settings) ----

injected_inert_credentials = []
for _name, _placeholder in INERT_PLACEHOLDERS.items():
    # Se rellena sólo lo que esté AUSENTE o VACÍO: exportar la variable real
    # antes de pytest sigue teniendo prioridad (decisión 4).
    if not os.getenv(_name, "").strip():
        os.environ[_name] = _placeholder
        injected_inert_credentials.append(_name)

# La suite no sale a la red: sin proveedor de IA, ni cuota, ni llamadas reales.
# `.env.test` ya usaba `mock`; aquí se fuerza para que el `.env` del
# desarrollador no pueda colar un proveedor vivo.
os.environ["AI_PROVIDER"] = "mock"

# Inyección de la BD. DEBE ejecutarse antes del primer import de
# config.settings (ver docstring del módulo).
if production_mode_enabled():
    # Modo producción: los tests afirmarán contra el CLON (decisión 2).
    os.environ["MONGO_DB_NAME"] = PRODUCTION_CLONE_DB
else:
    os.environ["MONGO_DB_NAME"] = TEST_DB


def drop_database_safely(client, db_name: str) -> bool:
    """Borra una BD, negándose SIEMPRE a borrar producción.

    Returns:
        True si se borró, False si se rechazó por ser producción o falló.
    """
    if db_name == PRODUCTION_DB:
        # Nunca destruir datos reales, pase lo que pase.
        return False
    try:
        client.drop_database(db_name)
        return True
    except Exception:
        return False


def _mongo_client():
    """Cliente Mongo usando la configuración de Settings ya resuelta."""
    from pymongo import MongoClient

    from config.settings import Settings

    kwargs = {
        "host": Settings.MONGO_HOST,
        "port": Settings.MONGO_PORT,
        "serverSelectionTimeoutMS": 5000,
    }
    if Settings.MONGO_USER and Settings.MONGO_PASSWORD:
        kwargs["username"] = Settings.MONGO_USER
        kwargs["password"] = Settings.MONGO_PASSWORD
        kwargs["authSource"] = "admin"
    return MongoClient(**kwargs)


def ensure_database_exists(client, db_name: str) -> None:
    """Crea la BD si no existe (MongoDB no tiene 'crear BD vacía')."""
    if db_name == PRODUCTION_DB:
        raise RuntimeError("No se crea ni se toca la BD de producción desde tests.")
    # Sentinel: la escritura materializa la BD.
    client[db_name]["_hermetic_bootstrap"].insert_one({"_": 1})


# --- Clonado de appdb para el modo producción (decisión 2, Fase 4) ------------

# Tamaño de lote de `insert_many`. 2000 documents equilibra memoria y nº de viajes.
CLONE_BATCH_SIZE = 2000


def _copy_collection(source, target) -> int:
    """Copia documentos e índices de una colección. Devuelve el nº de documentos."""
    total = 0
    batch = []
    for doc in source.find({}).batch_size(CLONE_BATCH_SIZE):
        batch.append(dict(doc))
        if len(batch) >= CLONE_BATCH_SIZE:
            target.insert_many(batch, ordered=False)
            total += len(batch)
            batch = []
    if batch:
        target.insert_many(batch, ordered=False)
        total += len(batch)

    # Índices: sin ellos, las queries del repositorio no usarían el índice y un
    # unique podría fallar al insertar. Se excluyen los índices internos de
    # MongoDB (`_fts`/`_ftsx` de los text indexes), que no son recreables.
    specs = []
    for index_name, info in source.index_information().items():
        if index_name == "_id_":
            continue
        fields = [field for field, _ in info["key"]]
        if index_name.startswith("_") or any(f.startswith("_fts") for f in fields):
            continue
        options = {
            option: info[option]
            for option in (
                "unique",
                "sparse",
                "expireAfterSeconds",
                "partialFilterExpression",
            )
            if option in info
        }
        specs.append(IndexModel(keys=info["key"], name=index_name, **options))
    if specs:
        target.create_indexes(specs)

    return total


def clone_production_database(client, source_name: str, target_name: str) -> int:
    """Copia `source_name` en `target_name`. Sólo lee del origen, nunca escribe.

    Lanza RuntimeError si el origen no existe o está vacío: un clon sin datos
    haría que los tests de producción affirmen contra fixtures inventados, que es
    justo el defecto que el audit de tests señalaba.
    """
    if source_name == PRODUCTION_DB and target_name == PRODUCTION_DB:
        raise RuntimeError("El clonado no puede tener appdb como origen y destino.")
    if target_name == PRODUCTION_DB:
        raise RuntimeError(
            "El clonado sólo puede escribir en el CLON: appdb es el origen de "
            "lectura y jamás debe ser destino de una escritura."
        )

    source = client[source_name]
    collections = sorted(source.list_collection_names())
    if not collections:
        raise RuntimeError(
            f"'{source_name}' no existe o no tiene colecciones: no hay datos "
            f"reales que clonar. El modo producción requiere appdb poblada."
        )

    # Un clon de una run anterior ensuciaría las aserciones.
    drop_database_safely(client, target_name)

    total = 0
    for name in collections:
        # MongoDB no materializa una colección vacía: sin este create_collection
        # explícito, `verified_news` (0 documentos en appdb) desaparecería del
        # clon y los tests de colecciones obligatorias fallarían. El clon debe
        # reflejar la ESTRUCTURA de appdb, no sólo sus documentos.
        if name not in client[target_name].list_collection_names():
            client[target_name].create_collection(name)
        total += _copy_collection(source[name], client[target_name][name])
    return total


def production_clone_snapshot(client, db_name: str = PRODUCTION_DB) -> dict:
    """Huella `{colección: (nº_docs, md5 del primero y del último _id)}`.

    Usada por los tests para dejar constancia de que `appdb` no cambia. El hash
    es deliberadamente barato: una copia completa de 58k documentos en cada
    test costaría más que el propio test.
    """
    db = client[db_name]
    fingerprint = {}
    for name in sorted(db.list_collection_names()):
        collection = db[name]
        count = collection.count_documents({})
        first = collection.find_one(sort=[("_id", 1)], projection={"_id": 1})
        last = collection.find_one(sort=[("_id", -1)], projection={"_id": 1})
        fingerprint[name] = (
            count,
            str(first["_id"]) if first else None,
            str(last["_id"]) if last else None,
        )
    return fingerprint


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "production: afirma datos reales de appdb (a través de su clon). "
        "Opt-in con NEWS_BOT_RUN_PRODUCTION_TESTS=1",
    )


def pytest_collection_modifyitems(config, items):
    """Salta los tests de producción salvo que se pidan explícitamente."""
    if production_mode_enabled():
        return
    marker = pytest.mark.skip(
        reason="test de datos reales de appdb: requiere "
        "NEWS_BOT_RUN_PRODUCTION_TESTS=1"
    )
    for item in items:
        if "production" in item.keywords:
            item.add_marker(marker)


@pytest.fixture(scope="session", autouse=True)
def _test_database_provisioned():
    """Crea la BD de test si no existe, o clona appdb en modo producción."""
    if production_mode_enabled():
        # El clon lo crea `_production_clone_provisioned` (más abajo), que además
        # necesita comprobar el snapshot de appdb antes y después.
        yield
        return
    try:
        client = _mongo_client()
        ensure_database_exists(client, TEST_DB)
    except Exception:
        # Mongo inaccesible: los tests de integración fallarán solos con su
        # propio mensaje. No debe impedir que corra el resto de la suite.
        pass
    yield


@pytest.fixture(scope="session", autouse=True)
def _production_clone_provisioned():
    """Modo producción: clona `appdb` y verifica que queda intacta (decisión 2).

    Es la garantía central de la Fase 4: los tests marcados `production` afirman
    contra `appdb_prod_clone`, así que pueden escribir (el pipeline mete artículos
    RSS reales) sin que `appdb` reciba una sola escritura.
    """
    if not production_mode_enabled():
        yield
        return

    client = _mongo_client()
    before = production_clone_snapshot(client, PRODUCTION_DB)

    started = time.monotonic()
    documents = clone_production_database(client, PRODUCTION_DB, PRODUCTION_CLONE_DB)
    elapsed = time.monotonic() - started

    print(
        f"\n[conftest] Clon de '{PRODUCTION_DB}' → '{PRODUCTION_CLONE_DB}': "
        f"{documents:,} documentos en {elapsed:.1f}s"
    )

    yield

    after = production_clone_snapshot(client, PRODUCTION_DB)
    if before != after:
        raise RuntimeError(
            f"CONTAMINACIÓN: '{PRODUCTION_DB}' cambió durante la sesión de tests "
            f"en modo producción. Antes={before} Después={after}. "
            f"Esto es un fallo grave: revisa qué test escribe fuera del clon."
        )
    drop_database_safely(client, PRODUCTION_CLONE_DB)
    print(
        f"[conftest] '{PRODUCTION_CLONE_DB}' dropeada; '{PRODUCTION_DB}' intacta."
    )


def pytest_sessionfinish(session, exitstatus):
    """Red de seguridad: si el fixture de sesión no corrió, limpia igual.

    Garantiza el requisito "la suite limpia lo que escribe" incluso si la
    sesión se aborta antes de llegar al teardown del fixture.
    """
    try:
        client = _mongo_client()
    except Exception:
        return
    if production_mode_enabled():
        # El clon también se limpia aquí: una sesión abortada no debe dejar 58k
        # documentos huérfanos en el servidor.
        drop_database_safely(client, PRODUCTION_CLONE_DB)
        return
    drop_database_safely(client, TEST_DB)