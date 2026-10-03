"""Guard: el código muerto eliminado no debe reaparecer.

Complementa a `test_dead_code_removed.py` (que protege módulos ya borrados).
Cubre tres categorías que un refactor posterior reintroduciría sin avisar:

1. **Imports sin usar.** Lista explícita de los que se borraron, más un
   barrido general con pyflakes (si está disponible) sobre todo el código
   enviado. Los `__init__.py` quedan fuera del barrido: sus imports son
   re-exports intencionales que constituyen la API pública del paquete y
   pyflakes los marca como unused por diseño.

2. **Código inalcanzable.** Un `try` cuyos caminos terminan todos en
   `return`/`raise` vuelve inalcanzable todo lo que le siga en la misma función.
   Es el fallo que dejó 53 líneas muertas en `AudioConverter.convert_to_wav16k`
   tras migrar el endpoint de multipart/form-data a JSON por ruta.

3. **Cableado muerto**: módulos reemplazados por adaptadores que sí construye
   `ai_factory`, y providers de DI sin ningún consumidor por `Depends`.

Este test verifica que algo **no** está, no que algo funciona.
"""

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCANNED_ROOTS = ("src", "config", "scripts")
EXTRA_FILES = ("server.py",)

# (fichero, línea 1-indexada, fragmento esperado) — el import no debe volver.
#
# Solo se listan imports a NIVEL DE MÓDULO. Los re-exports de `__init__.py`
# y los símbolos que además se importan dentro de una función quedan fuera:
# en ambos casos borrarlos es correcto, pero el símbolo sigue *"usándose"* y
# el barrido por nombre daría un falso positivo.
DELETED_IMPORTS = [
    ("src/audio/application/usecases/audio_pipeline.py", "asyncio"),
    ("src/audio/application/usecases/audio_pipeline.py", "random"),
    ("src/video/application/usecases/video_pipeline.py", "asyncio"),
    ("src/video/application/usecases/video_pipeline.py", "random"),
    ("src/news/application/usecases/pipeline_job.py", "Protocol"),
    ("src/news/entrypoints/api/dependencies.py", "lru_cache"),
    ("src/news/entrypoints/api/news_router.py", "subprocess"),
    ("src/news/entrypoints/api/news_router.py", "ContentExtractor"),
    ("src/news/entrypoints/api/news_router.py", "get_content_extractor"),
    ("src/news/entrypoints/api/news_router.py", "get_content_usecase"),
    ("src/news/application/usecases/article.py", "os"),
    ("src/news/application/usecases/article.py", "json"),
    ("src/news/application/usecases/content.py", "json"),
    ("src/news/application/usecases/content.py", "re"),
    ("src/video/application/usecases/video_to_news.py", "os"),
    ("src/video/infrastructure/adapters/video_transcriber.py", "Optional"),
    ("src/shared/adapters/facebook_publisher.py", "re"),
    ("src/shared/adapters/facebook_publisher.py", "datetime"),
    ("src/shared/adapters/mongo_db.py", "os"),
    ("src/shared/adapters/bluesky_publisher.py", "os"),
    ("src/shared/adapters/web_search.py", "os"),
    ("src/shared/adapters/ai/gemini_adapter.py", "os"),
    ("src/shared/adapters/ai/openrouter_adapter.py", "os"),
    ("src/shared/adapters/ai/prompt_loader.py", "os"),
    ("src/shared/adapters/audio_post_processor.py", "Path"),
    ("src/shared/adapters/audio_post_processor.py", "Settings"),
    ("src/shared/adapters/image_enricher.py", "Path"),
    ("src/shared/infrastructure/startup_validator.py", "Tuple"),
    ("src/news/domain/services/validation_rules.py", "Counter"),
    ("src/news/infrastructure/adapters/mongo_repositories.py", "Path"),
]


def _iter_source_files():
    for root in SCANNED_ROOTS:
        for path in sorted((PROJECT_ROOT / root).rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path
    for name in EXTRA_FILES:
        path = PROJECT_ROOT / name
        if path.exists():
            yield path


def _imported_names(path: Path) -> dict[str, int]:
    """Mapa nombre-importado -> línea, para un fichero dado."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return {}

    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[alias.asname or alias.name.split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                imported[alias.asname or alias.name] = node.lineno
    return imported


class TestDeletedImportsStayDeleted:
    def test_imports_not_reintroduced(self):
        offenders: list[str] = []
        for rel, name in DELETED_IMPORTS:
            path = PROJECT_ROOT / rel
            assert path.exists(), f"el fichero vigilado desapareció: {rel}"
            if name in _imported_names(path):
                offenders.append(f"{rel}: {name}")

        assert not offenders, (
            "imports sin usar reintroducidos:\n" + "\n".join(offenders)
        )

    def test_imports_are_actually_unused_if_present(self):
        """Auto-verificación del guard: si un símbolo reaparece y sí se usa,
        la lista de vigilados está obsoleta y hay que revisarla.

        Solo cuentan los usos **fuera de cualquier `import`**: un símbolo puede
        seguir siendo válido si el fichero lo importa dentro de una función,
        que es justo el caso tras borrar el import redundante de módulo.
        """
        offenders: list[str] = []
        for rel, name in DELETED_IMPORTS:
            path = PROJECT_ROOT / rel
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue

            used_outside_import = False
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.Name) and node.id == name:
                    used_outside_import = True
                    break
                if isinstance(node, ast.Attribute) and node.attr == name:
                    used_outside_import = True
                    break
                if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "__all__"
                    for t in node.targets
                ):
                    used_outside_import = True
                    break

            if used_outside_import:
                offenders.append(
                    f"{rel}: {name} reaparece Y se usa — actualiza DELETED_IMPORTS"
                )

        assert not offenders, "\n".join(offenders)

    def test_pyflakes_reports_no_unused_imports(self):
        """Barrido general. Se salta si pyflakes no está instalado."""
        executable = shutil.which("pyflakes")
        if executable is None:
            candidate = Path.home() / ".local" / "bin" / "pyflakes"
            if candidate.exists():
                executable = str(candidate)
        if executable is None:
            pytest.skip("pyflakes no disponible en el entorno")

        targets = [str(p.relative_to(PROJECT_ROOT)) for p in _iter_source_files()]
        result = subprocess.run(
            [executable, *targets],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        offenders = [
            line for line in result.stdout.splitlines()
            if "imported but unused" in line
            and "__init__.py" not in line  # re-exports intencionales
        ]
        assert not offenders, (
            "imports sin usar según pyflakes:\n" + "\n".join(offenders)
        )


def _stmt_always_exits(stmts: list[ast.stmt]) -> bool:
    """True si la lista de sentencias sale en todos los caminos posibles.

    Un `return`/`raise` sale siempre. Un `try` sale siempre si su `body` sale
    siempre, **todos** sus `handlers` salen siempre, y no hay `orelse` ni
    `finalbody` que puedan continuar.
    """
    for stmt in stmts:
        if isinstance(stmt, (ast.Return, ast.Raise)):
            return True
        if isinstance(stmt, ast.Try):
            if not stmt.handlers:
                return False
            if not _stmt_always_exits(stmt.body):
                return False
            if not all(_stmt_always_exits(h.body) for h in stmt.handlers):
                return False
            if stmt.orelse and not _stmt_always_exits(stmt.orelse):
                return False
            if stmt.finalbody and not _stmt_always_exits(stmt.finalbody):
                return False
            return True
    return False


def _unreachable_after_try(path: Path) -> list[int]:
    """Líneas inalcanzables: las que siguen a un `try` agotado."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    offenders: list[int] = []

    def scan_body(stmts: list[ast.stmt]) -> None:
        for index, stmt in enumerate(stmts):
            if isinstance(stmt, ast.Try) and _stmt_always_exits([stmt]):
                offenders.extend(s.lineno for s in stmts[index + 1:])
            for child in ast.iter_child_nodes(stmt):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    scan_body(child.body)
                elif isinstance(child, (ast.If, ast.For, ast.While, ast.With,
                                        ast.AsyncWith, ast.AsyncFor)):
                    scan_body(child.body)
                    scan_body(getattr(child, "orelse", []))
                    scan_body(getattr(child, "finalbody", []))
                    for handler in getattr(child, "handlers", []):
                        scan_body(handler.body)

    scan_body(tree.body)
    return offenders


class TestNoUnreachableCode:
    def test_no_statement_after_exhausted_try(self):
        offenders: list[str] = []
        for path in _iter_source_files():
            try:
                offenders.extend(
                    f"{path.relative_to(PROJECT_ROOT)}:{line}"
                    for line in _unreachable_after_try(path)
                )
            except SyntaxError:
                continue

        assert not offenders, (
            "código inalcanzable tras un try que siempre retorna:\n"
            + "\n".join(offenders)
        )

    def test_detector_actually_catches_injected_dead_code(self):
        """Auto-verificación: el detector debe marcar un caso sintético."""
        sample = (
            "def f(x):\n"
            "    try:\n"
            "        return x\n"
            "    except Exception:\n"
            "        return None\n"
            "    print('nunca')\n"
        )
        tree = ast.parse(sample)
        try_stmt = next(n for n in ast.walk(tree) if isinstance(n, ast.Try))
        assert _stmt_always_exits([try_stmt]), "el detector no reconoce el try agotado"

    def test_pyflakes_reports_no_unused_locals(self):
        """Asignaciones locales cuya variable nunca se lee.

        Fichero a fichero, excluyendo scripts de un solo uso, para que el guard
        no dependa de que pyflakes esté en el PATH.
        """
        offenders: list[str] = []
        for path in _iter_source_files():
            rel = path.relative_to(PROJECT_ROOT)
            if rel.parts[0] == "scripts":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            offenders.extend(f"{rel}:{line}" for line in _unused_locals(tree))

        assert not offenders, (
            "variables locales asignadas y nunca leídas:\n" + "\n".join(offenders)
        )

    def test_no_constant_counters_left_dead(self):
        """Contadores que se inicializan pero nunca se incrementan.

        `errors = 0` que solo se devuelve en el payload miente sobre el
        resultado: siempre vale 0 aunque el código haya fallado. Los publishers
        de Facebook y Bluesky lanzan excepción en vez de acumular, así que el
        campo `errors` de su respuesta es decorativo.

        Decisión tomada: se elimina del payload. Si alguien reintroduce un
        contador muerto NUEVO, el test falla para que se notifique.
        """
        found: list[str] = []
        for path in _iter_source_files():
            rel = path.relative_to(PROJECT_ROOT)
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                has_init = any(
                    isinstance(s, ast.Assign)
                    and any(_target_name(t) == "errors" for t in s.targets)
                    for s in ast.walk(node)
                )
                has_incr = any(
                    isinstance(s, ast.AugAssign)
                    and _target_name(s.target) == "errors"
                    for s in ast.walk(node)
                )
                if has_init and not has_incr:
                    found.append(f"{rel}:{node.lineno} ({node.name})")

        assert set(found) <= KNOWN_DEAD_COUNTERS, (
            "contadores 'errors' muertos nuevos:\n"
            + "\n".join(sorted(set(found) - KNOWN_DEAD_COUNTERS))
        )


def _target_name(target: ast.expr) -> str | None:
    return target.id if isinstance(target, ast.Name) else None


# Inventario de deuda conocida. Si alguien introduce un contador 'errors'
# muerto NUEVO (inicializado a 0 pero nunca incrementado), el test falla.
# Facebook y Bluesky ya no devuelven un campo 'errors' que miente: sus
# publishers lanzan excepción en el primer fallo (fail-fast), así que no
# hay nada que contar.
KNOWN_DEAD_COUNTERS: set[str] = set()


def _unused_locals(tree: ast.Module) -> list[int]:
    """Líneas de `x = ...` donde `x` no se lee nunca **dentro de una función**.

    Solo se examina el cuerpo de las funciones y clases, nunca el nivel de
    módulo: una constante de módulo (`MODEL_PATH`) o un re-export público son
    API, no código muerto, aunque este proceso no las lea.

    No se reportan los targets de bucles ni de augmented assignment, donde la
    variable sí se lee en su propia condición o actualización.
    """
    offenders: list[int] = []

    def scan(stmts: list[ast.stmt]) -> None:
        read: set[str] = set()
        assigned: dict[str, int] = {}

        # El recorrido debe bajar a bucles, `with` y `try`: un `x += 1` dentro
        # de un `for` sigue siendo un uso que mantiene vivo al contador, igual
        # que un `x = ...` dentro de un `with`.
        for node in stmts:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                    read.add(sub.id)
                elif isinstance(sub, ast.Attribute):
                    read.add(sub.attr)

        for node in stmts:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, node.lineno)
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                # `for a, b in ...` mete los nombres en un Tuple: hay que
                # bajar a el, no basta con mirar `node.target` como Name.
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                        assigned.setdefault(sub.id, node.lineno)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is not None:
                    assigned.setdefault(node.target.id, node.lineno)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                for item in node.items:
                    if item.optional_vars is not None:
                        for sub in ast.walk(item.optional_vars):
                            if isinstance(sub, ast.Name):
                                assigned.setdefault(sub.id, node.lineno)

        # Un `x += 1` anidado (dentro de un `for`, un `if`, un `try`) mantiene
        # vivo al contador igual que `x = 0` lo crea, asi que se buscan en todo
        # el subarbol, no solo en el nivel superior.
        for node in stmts:
            for sub in ast.walk(node):
                if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name):
                    read.add(sub.target.id)

        for name, lineno in assigned.items():
            if name in read or name.startswith("_"):
                continue
            # Contadores que solo se devuelven nunca incrementan su valor: se
            # leen, asi que el analisis AST no los marca, pero `test_no_constant_
            # counters_left_dead` los vigila aparte.
            offenders.append(lineno)

        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scan(node.body)
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        scan(member.body)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scan(node.body)
        elif isinstance(node, ast.ClassDef):
            # Solo se examinan los metodos: las constantes de clase
            # (`COLLECTION_NAME`, `WP_HOSTING_API_BASE`, ...) son API que se
            # consume como `self.X` / `Clase.X` desde otros ficheros, y aquí
            # solo se vería su lectura por reflection.
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    scan(member.body)

    return offenders


def _is_declarative_class(node: ast.ClassDef) -> bool:
    """True si los `x = valor` del cuerpo son declaraciones, no código muerto.

    `Enum`, los modelos de Pydantic y los `@dataclass` leen sus miembros por
    reflexión: no aparecen como `Name` en ningún punto del módulo, pero son
    parte de la API pública de la clase.
    """
    for base in node.bases:
        if any(token in ast.unparse(base)
               for token in ("Enum", "BaseModel", "Base", "ABC")):
            return True

    for decorator in node.decorator_list:
        if "dataclass" in ast.unparse(decorator):
            return True

    return False


class TestNoOrphanDependencyProviders:
    """Un provider sin `Depends` que lo consuma es cableado muerto."""

    DEAD_PROVIDERS = {"get_content_usecase"}

    def test_dead_providers_not_defined(self):
        deps = PROJECT_ROOT / "src/news/entrypoints/api/dependencies.py"
        tree = ast.parse(deps.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        still_there = sorted(self.DEAD_PROVIDERS & defined)
        assert not still_there, f"providers muertos de nuevo definidos: {still_there}"

    def test_dead_providers_not_referenced(self):
        self_path = Path(__file__).resolve()
        offenders: list[str] = []
        for path in _iter_source_files():
            if path.resolve() == self_path:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for name in self.DEAD_PROVIDERS:
                if name in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)} -> {name}")
        assert not offenders, "providers muertos aún referenciados:\n" + "\n".join(offenders)


class TestNoDeadModuleResidue:
    """Clientes legacy reemplazados por los adaptadores de `ai_factory`."""

    DEAD_MODULES = (
        "src/shared/adapters/gemini_client.py",
        "src/shared/adapters/openrouter_client.py",
    )

    def test_modules_absent(self):
        still_there = [
            rel for rel in self.DEAD_MODULES if (PROJECT_ROOT / rel).exists()
        ]
        assert not still_there, f"módulos muertos reintroducidos: {still_there}"