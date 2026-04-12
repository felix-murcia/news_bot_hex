# config/prompts.py
import os
import re
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import html
from .logging_config import setup_logging

logger = setup_logging("news_bot")

# Cargar variables desde .env
load_dotenv(override=True)

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

def _limpiar_para_prompt(texto: str, 
                         max_length: int = None, 
                         preserve_newlines: bool = True,
                         escape_html: bool = True,
                         extract_main_content: bool = True) -> str:
    """
    Limpia texto HTML para incluirlo en prompt de manera segura usando BeautifulSoup.
    
    Args:
        texto: Texto HTML a limpiar
        max_length: Longitud máxima a retornar
        preserve_newlines: Si True, mantiene saltos de línea
        escape_html: Si True, escapa caracteres HTML restantes
        extract_main_content: Si True, intenta extraer solo contenido principal
        
    Returns:
        Texto limpio y seguro para usar en prompts
    """
    if not texto or not isinstance(texto, str):
        return ""
    
    # 0. DETECTAR SI ES HTML (si contiene etiquetas HTML)
    es_html = '<' in texto and '>' in texto
    
    if not es_html:
        # Si no es HTML, limpieza básica
        return _limpiar_texto_simple(texto, max_length, preserve_newlines, escape_html)
    
    # 1. LIMPIEZA CON BEAUTIFULSOUP
    try:
        soup = BeautifulSoup(texto, 'html.parser')
        
        # Eliminar elementos no deseados
        for element in soup(['script', 'style', 'iframe', 'link', 'meta', 'nav', 
                           'header', 'footer', 'aside', 'form', 'button']):
            element.decompose()
        
        # Intentar extraer contenido principal
        if extract_main_content:
            # Buscar el elemento principal del artículo
            main_content = None
            posibles_selectores = [
                'article', 'main', '.article-content', '.post-content',
                '.entry-content', '.story-content', '[role="main"]',
                'div.article', 'div.story', 'div.content'
            ]
            
            for selector in posibles_selectores:
                main_content = soup.select_one(selector)
                if main_content:
                    soup = main_content
                    break
        
        # Extraer solo texto con párrafos preservados
        if preserve_newlines:
            # Mantener estructura de párrafos
            texto_limpio = '\n\n'.join([
                p.get_text(strip=True) for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if p.get_text(strip=True)
            ])
            
            # Si no hay párrafos, extraer todo el texto
            if not texto_limpio:
                texto_limpio = soup.get_text(separator='\n\n', strip=True)
        else:
            texto_limpio = soup.get_text(separator=' ', strip=True)
        
    except Exception as e:
        # Fallback a limpieza regex si BeautifulSoup falla
        print(f"⚠️ BeautifulSoup falló: {e}. Usando fallback regex.")
        texto_limpio = _limpiar_html_con_regex(texto, preserve_newlines)
    
    # 2. LIMPIEZA POST-BEAUTIFULSOUP
    texto_limpio = _limpiar_texto_simple(texto_limpio, max_length, preserve_newlines, escape_html)
    
    return texto_limpio


def _limpiar_html_con_regex(texto: str, preserve_newlines: bool = True) -> str:
    """Fallback para limpiar HTML con regex cuando BeautifulSoup falla."""
    
    # Eliminar scripts, estilos, etc.
    patrones_a_eliminar = [
        (r'<script.*?>.*?</script>', '', re.DOTALL | re.IGNORECASE),
        (r'<style.*?>.*?</style>', '', re.DOTALL | re.IGNORECASE),
        (r'<!--.*?-->', '', re.DOTALL),
        (r'<iframe.*?>.*?</iframe>', '', re.DOTALL | re.IGNORECASE),
        (r'<noscript.*?>.*?</noscript>', '', re.DOTALL | re.IGNORECASE),
        (r'<svg.*?>.*?</svg>', '', re.DOTALL | re.IGNORECASE),
        (r'<form.*?>.*?</form>', '', re.DOTALL | re.IGNORECASE),
        (r'<button.*?>.*?</button>', '', re.DOTALL | re.IGNORECASE),
        (r'<select.*?>.*?</select>', '', re.DOTALL | re.IGNORECASE),
        (r'<input.*?>', '', re.IGNORECASE),
        (r'on\w+="[^"]*"', '', re.IGNORECASE),
        (r'on\w+=\'[^\']*\'', '', re.IGNORECASE),
        (r'javascript:[^"\']*', '', re.IGNORECASE),
    ]
    
    for patron, reemplazo, flags in patrones_a_eliminar:
        texto = re.sub(patron, reemplazo, texto, flags=flags)
    
    # Extraer texto de párrafos y encabezados
    if preserve_newlines:
        # Buscar contenido de párrafos y encabezados
        parrafos = re.findall(r'<(?:p|h[1-6])(?:\s[^>]*)?>(.*?)</(?:p|h[1-6])>', texto, re.DOTALL | re.IGNORECASE)
        if parrafos:
            texto = '\n\n'.join([
                re.sub(r'<[^>]+>', '', p).strip() 
                for p in parrafos 
                if p.strip()
            ])
        else:
            # Eliminar todas las etiquetas
            texto = re.sub(r'<[^>]+>', ' ', texto)
    else:
        # Eliminar todas las etiquetas
        texto = re.sub(r'<[^>]+>', ' ', texto)
    
    return texto

def _limpiar_texto_simple(texto: str, max_length: int = None, 
                         preserve_newlines: bool = True, escape_html: bool = True) -> str:
    """Limpieza básica de texto (sin HTML)."""
    
    # 1. NORMALIZACIÓN DE ESPACIOS Y SALTOS
    if preserve_newlines:
        texto = re.sub(r'\n{3,}', '\n\n', texto)
        texto = texto.replace('\r\n', '\n').replace('\r', '\n')
        # Limpiar espacios alrededor de saltos
        texto = re.sub(r'[ \t]*\n[ \t]*', '\n', texto)
    else:
        texto = re.sub(r'[\r\n]+', ' ', texto)
    
    # 2. ELIMINAR CARACTERES DE CONTROL
    texto = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', texto)
    
    # 3. NORMALIZAR ESPACIOS ESPECIALES
    texto = texto.replace('\xa0', ' ')   # Non-breaking space
    texto = texto.replace('\u200b', '')  # Zero-width space
    texto = texto.replace('\u2028', '\n') if preserve_newlines else texto.replace('\u2028', ' ')
    texto = texto.replace('\u2029', '\n\n') if preserve_newlines else texto.replace('\u2029', ' ')
    texto = texto.replace('</p', '')
    
    # 4. ESCAPE HTML (si se solicita)
    if escape_html:
        texto = html.escape(texto)
    
    # 5. COLAPSAR MÚLTIPLES ESPACIOS
    texto = re.sub(r'[ \t]+', ' ', texto)
    
    # 6. LIMPIEZA DE URLS LARGAS
    texto = re.sub(r'(https?://\S{50,})', lambda m: m.group(0)[:50] + '...', texto)
    
    # 7. ENCODING Y CARACTERES EXTRAÑOS
    try:
        texto = texto.encode('utf-8', 'ignore').decode('utf-8')
    except:
        texto = re.sub(r'[^\x00-\x7F]+', ' ', texto)
    
    # 8. TRIM Y LIMITE DE LONGITUD
    texto = texto.strip()
    
    if max_length and len(texto) > max_length:
        texto = texto[:max_length]
        last_space = texto.rfind(' ')
        if last_space > max_length * 0.8:  # Más flexible
            texto = texto[:last_space] + '...'
        else:
            texto = texto + '...'
    
    # 9. VALIDACIÓN FINAL
    texto = re.sub(r'^[^\w"\'(¿¡-]+', '', texto)  # Más flexible al inicio
    texto = re.sub(r'[^\w"\'.!?…)-]+$', '', texto)  # Más flexible al final
    
    return texto

# Funciones especializadas para tipos de contenido
def limpiar_contenido_noticias(texto: str, fuente: str = "") -> str:
    """Limpieza especializada para contenido de noticias."""
    return _limpiar_para_prompt(
        texto, 
        max_length=5000, 
        preserve_newlines=True,
        escape_html=False,  # No escapar HTML porque ya lo limpiamos
        extract_main_content=True
    )

def limpiar_transcripcion_video(texto: str) -> str:
    """Limpieza especializada para transcripciones de video."""
    # Primero limpiar con BeautifulSoup
    texto = _limpiar_para_prompt(
        texto,
        max_length=4000,
        preserve_newlines=False,
        escape_html=False,
        extract_main_content=False
    )
    
    # Limpieza específica de transcripciones
    texto = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', texto)  # Marcadores de tiempo
    texto = re.sub(r'^\s*(?:SPEAKER|HABLANTE|VOZ|INTERLOCUTOR)[\s\d]*:?\s*', '', 
                  texto, flags=re.IGNORECASE | re.MULTILINE)
    
    # Unir líneas muy cortas
    lineas = [linea.strip() for linea in texto.split('\n') if linea.strip()]
    lineas_completas = []
    buffer = ""
    
    for linea in lineas:
        if len(linea) < 25 and not linea.endswith(('.', '!', '?')):
            buffer = f"{buffer} {linea}".strip() if buffer else linea
        else:
            if buffer:
                lineas_completas.append(buffer)
                buffer = ""
            lineas_completas.append(linea)
    
    if buffer:
        lineas_completas.append(buffer)
    
    return ' '.join(lineas_completas)

# Función de compatibilidad para mantener tu código existente
def limpiar_para_prompt(texto: str) -> str:
    """Alias para compatibilidad con código existente."""
    return _limpiar_para_prompt(texto, max_length=5000, preserve_newlines=True, escape_html=False)

def get_news_prompt(titulo: str, fuente: str, contenido_limpio: str, contexto_web: str = "") -> str:
    contenido_limitado = limpiar_contenido_noticias(contenido_limpio)

    contexto_limitado = limpiar_contenido_noticias(
        contexto_web[:2000] if contexto_web else "Añade contexto histórico y análisis comparativo."
    )
    
    return f"""# INSTRUCCIÓN ÚNICA: Genera un artículo de EXACTAMENTE 8 secciones H2

## FUENTES:
TÍTULO: {titulo}
FUENTE: {fuente}
DATOS: {contenido_limitado[:3000]}
CONTEXTO: {contexto_limitado[:1500]}

## REGLAS ABSOLUTAS:
1. **ESTRUCTURA EXACTA:**
   - Línea 1: Título principal (sin HTML)
   - Línea 2+: <h2>Sección 1</h2><p>Párrafo 1.</p><p>Párrafo 2.</p><p>Párrafo 3.</p>
   - REPETIR 8 VECES: 8 secciones H2, cada una con 3 párrafos

2. **LONGITUD POR PÁRRAFO:**
   - Cada <p> = MÁXIMO 120 palabras
   - Dividir inmediatamente si supera 120 palabras
   - 3-5 oraciones por párrafo

3. **VOZ Y TRANSICIONES:**
   - VOZ ACTIVA obligatoria (90%+)
   - Incluir 1-2 palabras de transición por párrafo (además, sin embargo, por tanto, por ejemplo)

4. **CONTENIDO:**
   - Sección 1: Introducción (4 párrafos)
   - Secciones 2-7: Análisis de diferentes ángulos
   - Sección 8: Conclusión/futuro
   - Expandir cada punto 3x con contexto histórico, comparaciones, proyecciones

## EJEMPLO DE FORMATO CORRECTO:
Título del artículo

<h2>Contexto histórico del conflicto</h2>
<p>El conflicto tiene raíces profundas. Por ejemplo, se remonta a la década de 1990. Además, factores económicos han agravado la situación.</p>
<p>La situación actual es compleja. Sin embargo, existen oportunidades de diálogo. Por tanto, ambas partes buscan soluciones.</p>
<p>En definitiva, el contexto explica la tensión actual. Asimismo, sugiere posibles vías de resolución.</p>

<h2>Análisis de los actores clave</h2>
<p>El gobierno australiano adoptó una postura firme. Primero, reafirmó la confianza en sus agencias. Además, proyectó unidad interna.</p>
<p>Por otro lado, Israel criticó la respuesta. Netanyahu utilizó términos específicos. Por ejemplo, calificó la reacción como "flácida".</p>
<p>Estas posturas reflejan diferencias estratégicas. Por tanto, la diplomacia será crucial.</p>

... CONTINUAR CON 6 SECCIONES MÁS ...

## NO HACER:
- ❌ Menos de 6 secciones H2
- ❌ Párrafos > 120 palabras
- ❌ Sin transiciones
- ❌ Voz pasiva predominante

**COMIENZA AHORA CON EL TÍTULO EN LA PRIMERA LÍNEA.**
"""

def get_audio_prompt(titulo: str, transcripcion_limpia: str) -> str:
    return f"""# INSTRUCCIÓN: Generar artículo periodístico desde TRANSCRIPCIÓN DE AUDIO (NOTICIA)

## TU ROL:
Eres un redactor de noticias especializado. Tu tarea es transformar una transcripción breve de un audio informativo en un artículo de noticia completo, bien estructurado y objetivo.

## FUENTE:
**Título:** {titulo}
**Transcripción de Audio (Noticia):**
{transcripcion_limpia}

## INSTRUCCIONES CRÍTICAS:
1. **Estructura de Salida (OBLIGATORIO):**
   - **Línea 1:** Solo el TÍTULO del artículo (sin etiquetas HTML).
   - **Línea 2 en adelante:** Contenido en HTML, usando **EXCLUSIVAMENTE** las etiquetas `<h2>` para los subtítulos y `<p>` para los párrafos.
   - **NO USES** markdown (`##`), bloques de código (` ```html `), ni ningún otro formato.

2. **Estructura del Contenido:**
   - **Introducción:** 1-2 párrafos que resuman la noticia.
   - **Cuerpo:** 4-6 secciones con sus propios `<h2>`. Cada sección debe desarrollar un aspecto distinto de la noticia (antecedentes, declaraciones, datos, reacciones, consecuencias).
   - **Conclusión:** 1 párrafo final.

3. **Estilo y Calidad:**
   - **Tono:** Periodístico objetivo, basado en hechos.
   - **Expansión:** Interpreta y desarrolla los puntos clave de la transcripción. No limites a copiar o parafrasear.
   - **Longitud:** El artículo final debe ser sustancialmente más largo y detallado que la transcripción original.

## EJEMPLO DE FORMATO CORRECTO:
Título de la Noticia Aquí

<h2>Primer aspecto de la noticia</h2>
<p>Este es el primer párrafo que desarrolla la idea.</p>
<p>Este es un segundo párrafo con más detalles.</p>

<h2>Segundo aspecto importante</h2>
<p>Aquí se explican otros elementos relevantes.</p>

**COMIENZA DIRECTAMENTE CON EL TÍTULO EN LA PRIMERA LÍNEA.**
"""

def get_video_prompt(titulo: str, contenido_limitado: str) -> str:
    transcripcion_limpia = limpiar_transcripcion_video(contenido_limitado)
    
    return f"""# GENERAR ARTÍCULO PERIODÍSTICO EXTENSO DESDE LA TRANSCRIPCIÓN

## TU ROL:
Eres un **periodista investigador senior** especializado en convertir contenido audiovisual en artículos periodísticos en profundidad.

## REQUISITOS DE LONGITUD Y PROFUNDIDAD:
- **MÍNIMO 1500-2000 palabras** (8,000-12,000 caracteres)
- **MÍNIMO 8-10 secciones** con subtítulos H2 organizadas temáticamente
- **Cada sección debe tener 3-4 párrafos** de 80-120 palabras
- **Expansión significativa:** El artículo debe ser 5-8 veces más extenso que la transcripción

TÍTULO:
{titulo}

## TRANSCRIPCIÓN:
{transcripcion_limpia}

## ESTRUCTURA OBLIGATORIA:

### 1. TÍTULO PRINCIPAL (línea 1, sin HTML)
- Impactante, informativo, 60-80 caracteres
- Debe reflejar el análisis en profundidad

### 2. INTRODUCCIÓN PROFUNDA (4-5 párrafos, ~200 palabras)
- Resumen ejecutivo esencial
- Contextualización global actual
- Relevancia e importancia
- Principales interrogantes

### 3. ANÁLISIS COMPLETO (MÍNIMO 6 SECCIONES H2)
Cada sección debe tener título ÚNICO basado en contenido específico de la transcripción.

## REGLAS YOAST SEO (CRÍTICAS):

### ✅ OBLIGATORIO PARA CADA PÁRRAFO:
1. **MÁXIMO 150 palabras** por párrafo (Yoast recomienda <150)
2. **Dividir** párrafos largos en varios más cortos
3. **Ideal:** 100-120 palabras, 3-5 oraciones

### ✅ OBLIGATORIO PARA CADA ORACIÓN:
1. **MÁXIMO 25 palabras** por oración (Yoast recomienda <25% sobre 20 palabras)
2. **Dividir** oraciones complejas con puntos y comas
3. **Promedio:** 15-18 palabras por oración

### ✅ OBLIGATORIO PARA VOZ:
1. **MÍNIMO 90% voz activa** (Yoast recomienda >90%)
2. **ESTRUCTURA ACTIVA:** "El gobierno anunció medidas" ✅
3. **EVITAR PASIVA:** "Medidas fueron anunciadas por el gobierno" ❌

### ❌ INCORRECTO (párrafo largo, voz pasiva):
"Fue anunciado por la empresa que serán implementadas nuevas tecnologías que permitirán mejorar la eficiencia operativa en todos los departamentos mediante la automatización de procesos manuales que actualmente requieren intervención humana constante." (35 palabras, pasivo)

### ✅ CORRECTO (dividido, voz activa):
"La empresa anunció nuevas tecnologías. Estas mejorarán la eficiencia operativa en todos los departamentos.

La automatización reemplazará procesos manuales. Actualmente, estos procesos requieren intervención humana constante." (4 oraciones, activo)

## ADVERTENCIAS CRÍTICAS:
- **⚠️ NO** artículos cortos (menos de 8 secciones H2)
- **⚠️ NO** repetir simplemente la transcripción
- **⚠️ NO** párrafos >150 palabras
- **⚠️ NO** oraciones >25 palabras
- **⚠️ NO** voz pasiva predominante
- **✅ SÍ** expandir cada punto con análisis
- **✅ SÍ** crear títulos H2 únicos por sección
- **✅ SÍ** mantener tono periodístico objetivo

## VERIFICACIÓN FINAL (ANTES DE ENVIAR):
Para cada párrafo escrito, preguntar:
1. ¿Menos de 150 palabras? ✅
2. ¿Oraciones <25 palabras? ✅  
3. ¿Voz activa? ✅

## FORMATO EXACTO (CRÍTICO):
1. **Línea 1:** Título principal (solo texto, sin etiquetas HTML)
2. **Línea 2 en adelante:** Artículo completo en HTML con esta estructura:
   - <h2>Texto del subtítulo</h2>
   - <p>Primer párrafo de la sección.</p>
   - <p>Segundo párrafo de la sección.</p>
   - <p>Tercer párrafo (opcional).</p>
3. **NADA más:** Sin explicaciones, sin comentarios, sin metatexto
4. **NO usar:** Bloques de código ```html, ```, markdown, ni wrappers

**COMIENZA DIRECTAMENTE CON EL TÍTULO EN LA PRIMERA LÍNEA.**

**RECUERDA: Si la transcripción menciona un tema durante 30 segundos, tú debes dedicarle al menos 4-5 párrafos de análisis en profundidad. La transcripción es solo el punto de partida para un análisis periodístico exhaustivo.**
"""

def get_transcript_prompt(transcript: str, titulo: str) -> str:
    contenido_limitado = transcript[:5000]
    transcripcion_limpia = limpiar_transcripcion_video(contenido_limitado)
    
    return f"""# ARTÍCULO PERIODÍSTICO DESDE TRANSCRIPCIÓN

Eres un periodista que redacta artículos basados en transcripciones informativas.

## INFORMACIÓN:
**Título:** {titulo}
**Fuente:** NBES TRANSCRIPTS

## TRANSCRIPCIÓN COMPLETA:
{transcripcion_limpia}

## INSTRUCCIONES:
1. Redacta un artículo periodístico objetivo basado ÚNICAMENTE en la transcripción
2. Estructura:
- Título principal (máximo 60 caracteres)
- Párrafo introductorio con lo más importante
- 2-3 subtítulos H2 con 2-3 párrafos cada uno
- Párrafo final de cierre

3. Estilo periodístico:
- 100% basado en hechos, sin opiniones personales
- Incluye contexto cuando sea relevante
- Lenguaje claro y accesible
- Sin sensacionalismo

4. Formato:
- HTML simple con <h2> y <p>
- Sin listas, tablas ni bullets
- Sin bloques de código

Genera ÚNICAMENTE el artículo en HTML, comenzando con el título en la primera línea."""

def get_simple_fallback_prompt(transcript: str, titulo: str) -> str:
    trascripcion_limpia = limpiar_transcripcion_video(transcript)
    
    return f"""Convierte esta transcripción de video en un artículo periodístico:

Título: {titulo}

Transcripción:
{trascripcion_limpia}

Escribe un artículo periodístico en español con:
- Título atractivo
- Párrafo introductorio
- 2 secciones con subtítulos H2
- 2-3 párrafos por sección
- Párrafo final

Formato HTML con <h2> y <p>. Solo el artículo."""

def get_resume_prompt(query: str, resultados: str, max_tokens: int = 500) -> str:
    return f"""Extrae información factual ACTUAL y RELEVANTE sobre este tema:

TEMA DE BÚSQUEDA: {query}

RESULTADOS ENCONTRADOS:
{resultados[:2500]}

INSTRUCCIONES:
1. Extrae SOLO información que amplíe o contextualice el tema
2. Incluye: fechas recientes, cifras actualizadas, declaraciones oficiales
3. Excluye: publicidad, contenido irrelevante, información desactualizada
4. Máximo {max_tokens} palabras, estilo periodístico conciso

INFORMACIÓN CONTEXTUAL RELEVANTE:"""

def get_resumen_ejecutivo_prompt(resumen_ejecutivo: str, seccion_instrucciones: str = "1", seccion_ejemplo: str = "2") -> str:
    return f"""GENERAR ARTÍCULO PERIODÍSTICO

{resumen_ejecutivo}

SECCIÓN {seccion_instrucciones}: INSTRUCCIONES
- Escribe en estilo periodístico objetivo
- Usa solo información factual
- Estructura: título, intro, 3 secciones, cierre
- Formato: HTML con <h2> y <p>

SECCIÓN {seccion_ejemplo}: EJEMPLO
<h2>Desarrollo de la situación</h2>
<p>[párrafo factual 1]</p>
<p>[párrafo factual 2]</p>

RESULTADO: Solo el artículo HTML."""

def get_simple_summary_prompt(titulo: str, informacion_factual: str) -> str:
    return f"""Como periodista, escribe un artículo objetivo sobre:

Tema: {titulo}

Información factual disponible:
{informacion_factual}

Estructura:
1. Título breve
2. Párrafo introductorio
3. Tres secciones con subtítulos H2
4. Párrafo de cierre

Reglas:
- Solo hechos verificables
- No uses la primera persona del singular o plural. Ejemplos(Voy a proponer, )
- Lenguaje periodístico neutral
- Sin opiniones personales
- Formato HTML simple

Genera solo el artículo HTML."""



# Ejemplo de uso en pipeline
if __name__ == "__main__":
    # En video_pipeline.py
    contenido_sucio = """
    <script>alert('peligro')</script>
    VIDEO TRANSCRIPCIÓN:
    [00:01] HABLANTE 1: Hola mundo.
    [00:05] Esto es un   texto   con   muchos   espacios.
    
    Y también saltos
    de línea excesivos.
    
    URL larga: https://ejemplo.com/una/url/muy/muy/muy/muy/muy/larga/que/deberia/acortarse
    """
    
    limpio = limpiar_transcripcion_video(contenido_sucio)
    print("Video limpio:")
    print(limpio)
    print("\n" + "="*50 + "\n")
    
    # En  news_pipeline.py
    noticia_sucia = """
    ACTUALIZADO: 15 de marzo 2024
    
    <iframe src="malicious.com"></iframe>
    Título de la noticia importante.
    
    Contenido con múltiples    espacios.
    
    Síguenos en Twitter @example
    
    También te puede interesar: Otra noticia
    """
    
    limpio_noticia = limpiar_contenido_noticias(noticia_sucia)
    print("Noticia limpia:")
    print(limpio_noticia)