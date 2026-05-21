# 📋 Auditoría de Backend: Arquitectura Hexagonal & SOLID
**Fecha:** 20/05/2026  
**Proyecto:** news_bot_hex  
**Estado:** ⚠️ INCUMPLIMIENTOS IDENTIFICADOS

---

## 📊 Resumen Ejecutivo

Se realizó una auditoría exhaustiva del backend contra los principios de **Arquitectura Hexagonal** y **SOLID**. El proyecto tiene una estructura de directorios correcta (domain → application → infrastructure → entrypoints), pero existen **11 incumplimientos críticos** que violan los principios fundamentales de arquitectura y diseño.

**Conformidad:**
- ✅ Arquitectura Hexagonal: 40% (estructura correcta, implementación deficiente)
- ✅ Principios SOLID: 35% (existen violaciones graves)

---

## 🔴 INCUMPLIMIENTOS CRÍTICOS

### 1. **FALTA DE INYECCIÓN DE DEPENDENCIAS EN ENDPOINTS**
**Severidad:** 🔴 CRÍTICA | **Principio:** DIP (Dependency Inversion Principle)

**Ubicación:** `src/news/entrypoints/api/news_router.py`

**Problema:**
```python
# ❌ INCORRECTO (línea 51)
@router.post("/process_url", response_model=PipelineResponse)
def news_process_url(req: ProcessUrlRequest):
    result = process_news_url(
        url=req.url,
        content_extractor=JinaContentExtractor(),  # ← Creación directa
        ...
    )

# ❌ INCORRECTO (línea 95)
def news_rss_list():
    repo = MongoArticleRepository()  # ← Creación directa
    articles = repo.get_all_articles()
```

**Por qué es un problema:**
- Las dependencias (adaptadores) se crean directamente en los endpoints
- No hay forma de mockear para testing
- El endpoint está acoplado a implementaciones concretas
- Viola el **Dependency Inversion Principle**: clases de alto nivel (endpoints) dependen de clases de bajo nivel (adaptadores)

**Impacto:**
- ❌ No se pueden hacer tests unitarios (sin BD real)
- ❌ No se pueden cambiar adaptadores sin modificar endpoints
- ❌ Se viola la inversión de dependencias

---

### 2. **AUSENCIA DE RAÍZ DE COMPOSICIÓN (COMPOSITION ROOT)**
**Severidad:** 🔴 CRÍTICA | **Principio:** Arquitectura Hexagonal

**Problema:**
- NO existe un punto centralizado de wiring de dependencias
- Las instancias de adaptadores se crean en múltiples lugares:
  - `news_router.py` (línea 51, 95)
  - Dentro de casos de uso con lazy loading (línea 63-68 en `news_to_news.py`)
  - En funciones factory dispersas

**Evidencia:**
```python
# news_to_news.py línea 60-68: lazy loading dentro del usecase ❌
def _get_ai_model(self):
    if self.ai_model is None:
        from src.shared.adapters.ai.ai_factory import get_ai_adapter
        provider = self.model_provider if self.use_ai else "mock"
        self.ai_model = get_ai_adapter(provider, self.ai_config)
    return self.ai_model

# tts_factory.py: factory con caché global ❌
_adapter_cache = {}  # Global mutable state
def get_tts_adapter(mode: str = None) -> TTSPort:
    if mode in _adapter_cache:
        return _adapter_cache[mode]
    ...
```

**Por qué es un problema:**
- No hay punto único para entender qué se crea y cómo
- Lazy loading disperso hace difícil debuggear
- Caché global viola el control de estado
- Imposible cambiar estrategias de instanciación sin buscar en todo el código

**Impacto:**
- ❌ Sistema de wiring invisible
- ❌ Difícil auditar qué adaptadores están en uso
- ❌ State management implícito

---

### 3. **VIOLACIÓN DE SRP: CASOS DE USO CON MÚLTIPLES RESPONSABILIDADES**
**Severidad:** 🔴 CRÍTICA | **Principio:** SRP (Single Responsibility Principle)

**Ubicación:** `src/news/application/usecases/news_to_news.py`

**Análisis:**
```python
class NewsToNewsUseCase:
    def __init__(
        self,
        content_extractor: ContentExtractor,      # ← Responsabilidad 1: Extracción
        use_ai: bool = True,
        model_provider: str = Settings.AI_PROVIDER,  # ← Responsabilidad 2: Config
        ai_config: Optional[dict] = None,           # ← Responsabilidad 3: Configuración
        ai_model=None,
        video_generator: Optional[VideoGeneratorPort] = None,  # ← Responsabilidad 4: Video
    ):
        ...
        self.ai_model = ai_model                        # ← Responsabilidad 5: IA
        self.video_generator = video_generator or self._get_default_video_generator()
        self.article_generator = None

    def _get_default_video_generator(self) -> VideoGeneratorPort:
        """Obtiene el generador de videos por defecto."""  # ← Extra responsabilidad
        ...

    def _get_ai_model(self):  # ← Extra responsabilidad
        """Obtiene el modelo de IA (lazy loading)."""
        ...

    def _get_article_generator(self):  # ← Extra responsabilidad
        ...

    def _load_from_cache(self, url: str):  # ← Extra responsabilidad (caching)
        ...

    def _save_to_cache(self, url: str, content: str):  # ← Extra responsabilidad (caching)
        ...
```

**Responsabilidades encontradas (6+):**
1. Extracción de contenido
2. Generación de artículos
3. Generación de videos
4. Configuración de IA
5. Caching de contenido
6. Lazy loading de dependencias
7. Orquestación general

**Por qué es un problema:**
- Cada responsabilidad es una razón para cambiar la clase
- Hace testing extremadamente difícil
- Imposible reutilizar partes de la lógica
- Causa "god objects"

**Impacto:**
- ❌ Modificar cualquier aspecto requiere entender todo el caso de uso
- ❌ Testing: necesitas mocker 5+ puertos para cada test
- ❌ No se pueden testear responsabilidades individualmente

---

### 4. **SINGLETON PATTERN VIOLANDO DIP**
**Severidad:** 🔴 CRÍTICA | **Principio:** DIP + SRP

**Ubicación:** `src/shared/adapters/mongo_db.py` (línea 16-23)

**Problema:**
```python
class MongoDBClient:
    _instance = None  # ← Global mutable state

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance  # ← Siempre la misma instancia

def get_database():
    return MongoDBClient().get_database()  # ← Hidden global dependency

# Uso en repositorios (línea 26-28 en mongo_repositories.py):
class MongoArticleRepository(ArticleRepository):
    def __init__(self):
        from src.shared.adapters.mongo_db import get_database
        self._db = get_database()  # ← Obtiene el global singleton
```

**Por qué es un problema:**
- **Global Mutable State**: El singleton es accesible desde cualquier lugar
- **Service Locator Pattern**: Los repositorios "buscan" su dependencia en lugar de recibirla
- **Imposible mockear**: No puedes reemplazar la BD para testing
- **Violación de DIP**: Los repositorios dependen de un global mutable, no de una abstracción

**Impacto:**
- ❌ Tests integrados son obligatorios (no se puede mockear MongoDB)
- ❌ Imposible tener tests paralelos (estado compartido)
- ❌ Imposible tener múltiples instancias de BD
- ❌ Hidden dependencies (no está claro qué depende de qué)

---

### 5. **IMPORTACIONES DINÁMICAS EN LÓGICA DE NEGOCIO**
**Severidad:** 🟠 ALTA | **Principio:** Arquitectura Hexagonal

**Ubicaciones múltiples:**

```python
# news_to_news.py línea 72-80: Import dentro del caso de uso
def _get_article_generator(self):
    if self.article_generator is None:
        from src.news.application.usecases.article_from_news import (
            ArticleFromNewsUseCase,
        )
        self.article_generator = ArticleFromNewsUseCase(...)
    return self.article_generator

# news_to_news.py línea 85-88: Import dinámica de cache
def _load_from_cache(self, url: str):
    from src.shared.adapters.cache_manager import load_content_from_cache
    ...

# ai_factory.py línea 52-59: Import dinámica vía importlib
module = importlib.import_module(module_name)
adapter_class = getattr(module, class_name)
```

**Por qué es un problema:**
- Las importaciones dinámicas hacen difícil entender dependencias
- No se pueden detectar errores en import-time
- Ralentiza ejecución (import en runtime)
- Oculta qué adaptadores se necesitan

**Impacto:**
- ❌ Dependencias ocultas
- ❌ Errores aparecen en runtime, no en static analysis
- ❌ Difícil de refactorizar (IDEs no pueden seguir imports)

---

### 6. **REPOSITORIOS VIOLANDO LISKOV SUBSTITUTION PRINCIPLE**
**Severidad:** 🟠 ALTA | **Principio:** LSP

**Ubicación:** `src/news/infrastructure/adapters/mongo_repositories.py`

**Problema:**
```python
class MongoArticleRepository(ArticleRepository):
    def get_all_articles(self) -> List[Article]:
        try:
            raw = list(self._collection.find({}))
            return [Article.from_dict(item) for item in raw]
        except Exception as e:
            logger.error(f"Error retrieving raw news: {e}")
            return []  # ← Retorna [] en error, no levanta excepción
```

La interfaz `ArticleRepository` promete retornar `List[Article]`, pero:
- En caso de error, retorna `[]` silenciosamente
- Quien usa el repositorio no sabe si falló o si no hay artículos
- No cumple el contrato del puerto

**Por qué es un problema:**
- **LSP viola:** Los subtipos no pueden reemplazarse por el tipo base sin romper comportamiento
- Quienusa el repositorio no puede confiar en el contrato
- Errores se silencian

**Impacto:**
- ❌ Errores de BD se ignoran silenciosamente
- ❌ Debugging imposible
- ❌ No se pueden confiar en abstracción

---

### 7. **VIOLACIÓN DE OPEN/CLOSED PRINCIPLE**
**Severidad:** 🟠 ALTA | **Principio:** OCP (Open/Closed Principle)

**Ubicación:** `src/news/entrypoints/api/news_router.py` (línea 142-158)

**Problema:**
```python
@router.post("/article", response_model=PipelineResponse)
def news_article(provider: str | None = None, limit: int = 1):
    """Generar artículos profesionales desde noticias verificadas."""
    try:
        from src.news.application.usecases.article import run  # ← Hard-coded
        ...
        results = run(limit=limit, use_gemini=True, model_provider=model_provider)  # ← Hard-coded
        return PipelineResponse(status="ok", message=f"Generated {len(results)} article(s)", ...)
    except Exception as e:
        logger.error(f"Error generando artículos: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

Para añadir una nueva estrategia de generación (ej: usar un modelo diferente), necesitas:
1. Modificar el endpoint
2. Modificar el caso de uso
3. Recompilar y re-deployar

**Por qué es un problema:**
- **OCP**: Clases deben estar cerradas para modificación, abiertas para extensión
- No hay forma de extender sin modificar
- Usando composición y DI sería posible

**Impacto:**
- ❌ Agregar nuevas estrategias requiere cambiar código existente
- ❌ No se pueden plugear nuevos adaptadores
- ❌ Alto riesgo de romper funcionalidad existente

---

### 8. **INTERFACE SEGREGATION PROBLEM: PUERTOS MUY GENÉRICOS**
**Severidad:** 🟡 MEDIA | **Principio:** ISP (Interface Segregation Principle)

**Ubicación:** `src/news/domain/ports/__init__.py`

**Problema:**
```python
class ScoringConfigRepository(ABC):
    """Puerto para obtener configuración de scoring."""
    @abstractmethod
    def get_scoring_config(self) -> dict:  # ← dict genérico
        pass

class FakeNewsModel(ABC):
    """Puerto para el modelo de detección de fake news."""
    @abstractmethod
    def predict_batch(self, texts: List[str]) -> tuple[List[bool], List[float]]:  # ← tuple genérica
        pass
```

**Por qué es un problema:**
- Retornan tipos genéricos (dict, tuple) en lugar de tipos específicos
- El cliente debe conocer la estructura interna
- Cambios en estructura rompen clientes

**Impacto:**
- ⚠️ Acoplamiento implícito a estructura de datos
- ⚠️ Sin verificación de tipos
- ⚠️ Documentación es crítica (pero ausente)

---

### 9. **INYECCIÓN DE DEPENDENCIAS PARCIAL EN CASOS DE USO**
**Severidad:** 🟡 MEDIA | **Principio:** DIP + SRP

**Ubicación:** `src/news/application/usecases/news_to_news.py` (línea 34-52)

**Problema:**
```python
class NewsToNewsUseCase:
    def __init__(
        self,
        content_extractor: ContentExtractor,  # ✅ Inyectado
        use_ai: bool = True,                  # ❌ Configuración mezclada
        model_provider: str = Settings.AI_PROVIDER,  # ❌ Settings hardcodeado
        ai_config: Optional[dict] = None,     # ❌ Extra parámetro
        ai_model=None,                         # ⚠️ Lazy loading
        video_generator: Optional[VideoGeneratorPort] = None,  # ✅ Inyectado con default
    ):
```

**Problemas:**
- Mezcla configuración con dependencias
- No hay garantía de que el adaptador esté disponible en constructor
- Lazy loading en método rompe garantías de composición
- Demasiados parámetros (constructor pollution)

**Impacto:**
- ⚠️ Constructor frágil
- ⚠️ No está claro qué es obligatorio vs opcional
- ⚠️ Composición tardía (runtime) es frágil

---

### 10. **SIN DEFINICIÓN CLARA DE DTOs EN CASOS DE USO**
**Severidad:** 🟡 MEDIA | **Principio:** Arquitectura Hexagonal

**Ubicación:** `src/news/application/usecases/`

**Problema:**
```python
# No hay DTOs definidos para entrada/salida
def process_news_url(
    url: str,                              # ← raw string
    content_extractor: ContentExtractor,
    model_provider: str,                   # ← raw string
    use_ai: bool,                          # ← raw bool
) -> dict:  # ← dict anónimo

# En cambio hay:
class ProcessUrlRequest(BaseModel):  # ← En el router, no en el caso de uso
    url: str
    provider: str | None = None
    use_ai: bool = True
```

**Por qué es un problema:**
- No hay contrato claro de entrada/salida
- El router define DTOs, no el caso de uso
- Acoplamiento implícito entre router y caso de uso
- No documentado

**Impacto:**
- ⚠️ Contratos poco claros
- ⚠️ Sin validación tipada en casos de uso
- ⚠️ Difícil de testear sin entender router

---

### 11. **FALTA DE MANEJO CONSISTENTE DE ERRORES**
**Severidad:** 🟡 MEDIA | **Principio:** Arquitectura Hexagonal

**Ubicación:** Múltiples repositorios

**Problema:**
```python
# mongo_repositories.py: silencia errores
def get_all_articles(self) -> List[Article]:
    try:
        raw = list(self._collection.find({}))
        return [Article.from_dict(item) for item in raw]
    except Exception as e:
        logger.error(f"Error retrieving raw news: {e}")
        return []  # ← Silencia el error

# news_router.py: exponecomo HTTP 500
@router.post("/process_url", response_model=PipelineResponse)
def news_process_url(req: ProcessUrlRequest):
    try:
        result = process_news_url(...)
        return PipelineResponse(status="ok", ...)
    except Exception as e:
        logger.error(f"Error procesando URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))  # ← Genérico
```

**Por qué es un problema:**
- Los adaptadores silencian errores
- Los routers los exponen genéricamente
- No hay excepción específica del dominio
- El cliente no sabe qué falló

**Impacto:**
- ⚠️ Debugging difícil
- ⚠️ Sin información específica del error
- ⚠️ Clientes no pueden tomar decisiones basadas en error

---

## 📈 MATRIZ DE INCUMPLIMIENTOS

| # | Incumplimiento | Severidad | SOLID | Hexagonal | Archivos Afectados |
|---|---|---|---|---|---|
| 1 | Falta DI en endpoints | 🔴 CRÍTICA | DIP | ❌ | news_router.py |
| 2 | Sin composition root | 🔴 CRÍTICA | DIP | ❌ | Todo el proyecto |
| 3 | SRP violado en usecases | 🔴 CRÍTICA | SRP | ❌ | news_to_news.py |
| 4 | Singleton anti-patrón | 🔴 CRÍTICA | DIP | ❌ | mongo_db.py |
| 5 | Imports dinámicos | 🟠 ALTA | DIP | ❌ | news_to_news.py, ai_factory.py |
| 6 | LSP violado en repos | 🟠 ALTA | LSP | ❌ | mongo_repositories.py |
| 7 | OCP violado | 🟠 ALTA | OCP | ❌ | news_router.py |
| 8 | ISP: puertos genéricos | 🟡 MEDIA | ISP | ⚠️ | domain/ports/ |
| 9 | DI parcial en usecases | 🟡 MEDIA | DIP | ⚠️ | news_to_news.py |
| 10 | Sin DTOs en usecases | 🟡 MEDIA | - | ⚠️ | application/usecases/ |
| 11 | Errores inconsistentes | 🟡 MEDIA | - | ⚠️ | Múltiples |

---

## 🎯 RECOMENDACIONES PRIORITARIAS

### Fase 1 (Semanal): CRÍTICAS
1. **Crear Composition Root** centralizado
2. **Eliminar Singleton** de MongoDBClient
3. **Inyectar dependencias** en endpoints
4. **Dividir casos de uso** (SRP)

### Fase 2 (Bi-semanal): ALTAS
5. Eliminar imports dinámicos
6. Mejorar manejo de errores
7. Definir DTOs para usecases

### Fase 3 (Mensual): MEDIAS
8. Mejorar contratos de puertos (ISP)
9. Documento de decisiones arquitectónicas
10. Refactor gradual del codebase

---

## 📝 PRÓXIMOS PASOS

Se ha generado este informe como base para la **Fase de Resolución**. 

Cada incumplimiento tiene un plan de remediación específico en la siguiente sección.
