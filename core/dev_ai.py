"""
Conecta DevBox con un modelo de IA corriendo localmente vía Ollama
(http://localhost:11434). No requiere API key ni conexión a
internet una vez descargado el modelo.

Requiere que el usuario tenga Ollama instalado y corriendo:
    brew install ollama
    brew services start ollama
    ollama pull qwen2.5-coder:7b
"""

import json
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path


URL_OLLAMA = "http://localhost:11434/api/generate"
MODELO_POR_DEFECTO = "qwen2.5-coder:7b"
TIMEOUT_SEGUNDOS = 120


class OllamaNoDisponible(Exception):
    """Se lanza cuando Ollama no está corriendo o no responde."""


def _consultar(prompt: str, modelo: str = MODELO_POR_DEFECTO, num_ctx: int | None = None) -> str:
    # Temperatura baja a propósito: todo lo que le pedimos a este
    # modelo (explicar un error, corregir código, revisar sintaxis)
    # tiene una respuesta técnicamente correcta, no es una tarea
    # creativa. Con la temperatura por defecto del modelo, pruebas
    # reales mostraron corridas muy inconsistentes con el MISMO
    # prompt (un caso pasó de detectar 4/4 bugs a solo 1/4 sin
    # ningún cambio de código de por medio) y varios casos de datos
    # inventados (una URL falsa, un "falta un dos puntos" que no
    # existía). Bajar la temperatura reduce ese tipo de invención y
    # hace las respuestas más repetibles.
    opciones = {"temperature": 0.2}

    if num_ctx is not None:
        opciones["num_ctx"] = num_ctx

    cuerpo = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": opciones,
    }

    cuerpo = json.dumps(cuerpo).encode("utf-8")

    peticion = urllib.request.Request(
        URL_OLLAMA,
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
            return datos.get("response", "").strip()

    except urllib.error.URLError as error:
        raise OllamaNoDisponible(
            "No se pudo conectar con Ollama. Verifica que esté corriendo "
            "('brew services start ollama') y que hayas descargado el "
            f"modelo ('ollama pull {modelo}')."
        ) from error

    except TimeoutError as error:
        raise OllamaNoDisponible(
            "Ollama tardó demasiado en responder. El modelo puede estar "
            "cargándose por primera vez; intenta de nuevo en un momento."
        ) from error


def explicar_error(texto_error: str, archivos_proyecto: list[str] | None = None) -> str:
    """
    Recibe un traceback/error pegado por el usuario y devuelve una
    explicación en español, con causa probable y solución sugerida.

    Si se pasa 'archivos_proyecto' (una lista de rutas relativas de
    archivos que sí existen en el proyecto), el modelo puede
    distinguir mejor entre un módulo local que falta copiar y un
    paquete de terceros que falta instalar con pip.
    """
    contexto_archivos = ""

    if archivos_proyecto:
        muestra = "\n".join(f"- {archivo}" for archivo in archivos_proyecto[:150])
        contexto_archivos = f"""
Estos son los archivos que SÍ existen actualmente en la carpeta del
proyecto del usuario (úsalos para distinguir si un módulo faltante
es un archivo local que no se copió, o una librería de terceros que
falta instalar con pip):

{muestra}
"""

    prompt = f"""Eres un asistente de programación integrado en una
herramienta de escritorio llamada DevBox. Un desarrollador te pegó
el siguiente texto en la casilla de "error".

Antes que nada, revisa si ese texto es realmente un error o
traceback real (contiene cosas como "Traceback", "Error:",
"Exception", una pila de llamadas, un mensaje real de la terminal,
etc.). Si en cambio es una descripción de un comportamiento
incorrecto SIN ningún error real (por ejemplo "mi función devuelve
el resultado equivocado" o "el programa corre pero hace algo raro"),
NO inventes un "Tipo de error" ni una causa falsa -eso sería peor
que no responder nada. En ese caso responde ÚNICAMENTE con este
texto, sin agregar nada más:

"Esto no parece un error o traceback real -suena más bien a un
comportamiento incorrecto (el programa corre pero no hace lo
esperado). Para este tipo de caso usa mejor el botón 'Corregir
código' y pega ahí el fragmento que sospechas, así la IA revisa la
lógica en vez de intentar explicar un error que no existe."

Si SÍ es un error/traceback real, ignora todo lo anterior y responde
en español, de forma breve y clara, con este formato exacto:

Tipo de error: (una línea)
Causa probable: (1-2 líneas)
Solución sugerida: (pasos concretos, numerados si aplica)

Antes de sugerir "pip install <nombre>", revisa primero si ese
nombre aparece en la lista de archivos del proyecto de abajo (si se
proporcionó). Si el traceback menciona archivos propios del proyecto
del usuario (como main.py, gui.py, etc.) en vez de rutas de
site-packages, es señal de que el módulo faltante probablemente es
un archivo local que no se copió correctamente, NO un paquete de
pip.
{contexto_archivos}
Error:
{texto_error}
"""
    return _consultar(prompt)


def generar_codigo(
    descripcion: str,
    archivos_proyecto: list[str] | None = None,
) -> str:
    """
    Genera un archivo de código nuevo y funcional a partir de una
    descripción en lenguaje natural. A diferencia de corregir_codigo()
    y revisar_archivo(), aquí no hay nada existente que corregir -se
    le pide a la IA que escriba algo desde cero.
    """
    contexto_archivos = ""

    if archivos_proyecto:
        muestra = "\n".join(f"- {archivo}" for archivo in archivos_proyecto[:150])
        contexto_archivos = f"""
Archivos que ya existen en el proyecto (para que lo que generes
encaje con lo que ya hay, y no repitas un nombre de archivo que ya
existe):

{muestra}
"""

    prompt = f"""Eres un asistente de programación integrado en
DevBox. Un desarrollador te describe qué código quiere, y tu trabajo
es escribirlo completo y funcional desde cero -no es un fragmento de
ejemplo, es un archivo real, listo para guardar y ejecutar.

Reglas que debes seguir siempre, sin que haga falta que te las pidan:
- Si el código interactúa con una base de datos, usa SIEMPRE
  consultas parametrizadas o prepared statements (por ejemplo
  $conn->prepare() + bind_param() en PHP con mysqli, parámetros con
  ? o %s en otros lenguajes/drivers). NUNCA construyas una consulta
  SQL concatenando valores directamente en el string -es una
  vulnerabilidad de inyección SQL real, no un detalle de estilo.
- Si te piden una "API" o un "endpoint", genera algo que de verdad
  reciba peticiones HTTP (lee el método y los parámetros de la
  petición, responde en el formato que corresponda) -no generes solo
  funciones sueltas con una llamada de ejemplo al final del archivo;
  eso no es una API.
- No expongas errores internos, consultas SQL completas, ni detalles
  de la base de datos en lo que se le devuelve al usuario final -usa
  mensajes de error genéricos hacia afuera.
- Sigue las prácticas de seguridad estándar del lenguaje que uses
  (validar/sanitizar entradas, no asumas que la entrada es segura).
- Si la tarea pedida en realidad necesita más de un archivo (por
  ejemplo, separar configuración, modelos y rutas), NO simules varios
  archivos con comentarios dentro de uno solo -eso no funciona si se
  guarda como un único archivo real. En vez de eso, genera solo el
  archivo más importante para la tarea, y dilo claramente en "Qué voy
  a generar": explica que la tarea completa necesitaría más archivos,
  y cuáles serían, para que te los pidan uno por uno.
- Antes de usar una función, clase o atributo de una librería,
  asegúrate de que existe REALMENTE en esa librería -no lo asumas por
  analogía con otra librería parecida. Un error común es confundir
  clases de `threading` con las de `multiprocessing` en Python (por
  ejemplo, `threading` NO tiene una clase `Value`). Si no estás seguro
  de que algo existe, usa una alternativa que sepas con certeza que sí
  existe.
- Para procesar tareas en paralelo con un límite de hilos/procesos
  concurrentes en Python, usa `concurrent.futures.ThreadPoolExecutor`
  (o `ProcessPoolExecutor`) con `max_workers=N` -es la forma estándar
  y evita tener que contar hilos activos a mano, que es una fuente
  común de errores. Para un contador compartido de tareas completadas,
  antes que nada haz `import threading` y crea explícitamente
  `lock = threading.Lock()` -nunca uses `with lock:` sin haber creado
  antes ese objeto Lock con esa línea exacta. Incrementa el contador
  dentro de ese `with lock:` justo cuando cada tarea realmente termina
  (por ejemplo, al recibir cada resultado de `as_completed()`).
- Si la descripción menciona un elemento específico (por ejemplo "con
  una contraseña", "con un límite de tamaño", "que no supere N
  intentos"), tu código DEBE usar ese elemento de verdad, no lo
  ignores ni lo reemplaces por otra cosa. Para cifrado de archivos con
  contraseña en Python específicamente: usa `pycryptodome`
  (`Crypto.Cipher.AES` + `Crypto.Protocol.KDF.PBKDF2`) y deriva la
  clave AES a partir de la contraseña con
  `PBKDF2(password.encode(), salt, dkLen=32, count=200000)` (siempre
  con `count` explícito de al menos 200000, nunca el valor por
  defecto de la librería, que es demasiado bajo). NO uses
  `cryptography.fernet.Fernet` para este caso: su patrón habitual,
  `Fernet.generate_key()`, genera una clave aleatoria sin relación
  con ninguna contraseña, que es exactamente el error a evitar. En
  otros lenguajes, usa el equivalente de PBKDF2/scrypt de esa
  plataforma con el mismo criterio: nunca una clave aleatoria cuando
  se pidió una contraseña.
- Al sanitizar un nombre de archivo para evitar path traversal, no
  confíes solo en una función tipo `basename()` sin más: primero
  reemplaza cualquier barra invertida (el carácter de "backslash") por
  barra normal ("/") en el nombre recibido, y DESPUÉS aplica
  `basename()` -así también quedan neutralizados los intentos de
  escape con rutas estilo Windows, no solo los que usan "/".
- Si generas tokens JWT con Flask-JWT-Extended, el parámetro
  `identity` de `create_access_token()` DEBE ser un string, nunca un
  entero directamente -convierte explícitamente con `str(...)` al
  crear el token, y vuelve a convertir con `int(...)` (o el tipo
  original) al leerlo de vuelta con `get_jwt_identity()`. Las
  versiones actuales de esa librería rechazan identidades que no sean
  string con el error "Subject must be a string".
- Si defines modelos con Flask-SQLAlchemy (o cualquier ORM similar),
  siempre incluye el código que crea las tablas antes de que la
  aplicación las use (por ejemplo `with app.app_context():
  db.create_all()`) -nunca asumas que la base de datos y sus tablas
  ya existen de antemano.
- No reutilices el mismo nombre de variable para dos propósitos
  distintos dentro del mismo archivo o función (por ejemplo, no le
  pongas a una lista el mismo nombre que ya usaste para un
  diccionario) -esto sobrescribe silenciosamente el valor anterior y
  puede romper el código más adelante sin ningún aviso.
- Si generas un evaluador de expresiones con precedencia de
  operadores, usa el algoritmo de Shunting-yard de Dijkstra o un
  parser de descenso recursivo con una función por nivel de
  precedencia (por ejemplo `parse_suma`, `parse_termino`,
  `parse_factor`) -NUNCA una sola pila que reduzca el operador
  pendiente en cuanto aparece el siguiente token. Antes de aplicar el
  operador que está en el tope de la pila, compara su precedencia
  contra la del operador que acabas de leer, y solo aplícalo si el de
  la pila tiene precedencia mayor o igual. Al sacar los dos operandos
  de la pila para aplicar un operador, recuerda que el que se sacó
  PRIMERO es el operando derecho y el que se sacó SEGUNDO es el
  izquierdo -si los inviertes, la resta y la división dan mal aunque
  la suma y la multiplicación parezcan estar bien.

Responde en español con este formato exacto:

Qué voy a generar: (1-2 líneas explicando tu interpretación de lo
pedido. Si la descripción no especifica el lenguaje, elige el más
razonable para la tarea y dilo aquí.)
Código generado:
```
(el archivo completo -imports/requires incluidos si hacen falta, sin
marcadores de "TODO" ni partes a medio hacer)
```
Cómo usarlo: (1-2 líneas: cómo ejecutarlo o qué dependencias
instalar, si aplica)

No inventes que el código hace algo que en realidad no hace. Si la
descripción es ambigua, elige la interpretación más simple y
razonable -esto no es una conversación de ida y vuelta, es una sola
respuesta.
{contexto_archivos}
Descripción:
{descripcion}
"""
    return _consultar(prompt)


def analizar_proyecto_con_ia(info_proyecto: dict) -> str:
    """
    Recibe el diccionario de resultado del explorador de proyectos
    (tipo, dependencias, si tiene README/.gitignore/git) y devuelve
    una lectura general en español, con sugerencias.
    """
    resumen = f"""Tipo de proyecto: {info_proyecto.get('tipo')}
Total de archivos: {info_proyecto.get('total_archivos')}
Tiene README: {info_proyecto.get('tiene_readme')}
Tiene .gitignore: {info_proyecto.get('tiene_gitignore')}
Usa control de versiones Git: {info_proyecto.get('tiene_git')}
Dependencias: {', '.join(info_proyecto.get('dependencias', [])) or 'ninguna detectada'}
"""

    prompt = f"""Eres un asistente de programación integrado en DevBox.
Aquí está el resumen de un proyecto que un desarrollador quiere
entender mejor:

{resumen}

Responde en español, breve (máximo 5-6 líneas), con:
1. Qué tipo de proyecto parece ser y para qué podría servir.
2. Un máximo de 2 sugerencias concretas de mejora (por ejemplo, si
   falta README o .gitignore, o si conviene revisar dependencias).
No inventes detalles que no están en el resumen.
"""
    return _consultar(prompt)


def corregir_codigo(
    codigo: str,
    contexto_error: str = "",
    archivos_proyecto: list[str] | None = None
) -> str:
    """
    Recibe un fragmento de código (y opcionalmente el error que
    produce) y devuelve el código corregido, con una breve
    explicación de qué se cambió y por qué.

    Nota sobre una limitación conocida: en fragmentos con varias
    funciones y varios bugs distintos sin ninguna pista de
    localización, el modelo puede detectar bien los bugs con una
    señal estructural clara (una condición invertida, un rango de
    loop mal puesto) y pasar por alto los que requieren razonar sobre
    si la operación tiene sentido semánticamente (por ejemplo, sumar
    una tasa en vez de calcular un porcentaje). Se intentó resolver
    dividiendo el código en funciones y revisando cada una en una
    llamada aislada, pero cada intento reveló una falla nueva
    (mejoras no pedidas en funciones sin bugs, imports/constantes
    reinventados al perder el contexto del módulo, y firmas de
    función completas perdidas en la respuesta) -se revirtió esa
    división por ser menos confiable que mandar todo junto. Para
    revisiones confiables, lo mejor sigue siendo pegar una función (o
    un bug) a la vez.
    """
    contexto_archivos = ""

    if archivos_proyecto:
        muestra = "\n".join(f"- {archivo}" for archivo in archivos_proyecto[:150])
        contexto_archivos = f"""
Archivos que existen en el proyecto (para no confundir un módulo
local con uno de terceros):

{muestra}
"""

    bloque_error = f"\nError relacionado:\n{contexto_error}\n" if contexto_error.strip() else ""

    prompt = f"""Eres un asistente de programación integrado en
DevBox. Un desarrollador te pasó el siguiente código, que tiene un
problema. Responde en español con este formato exacto:

Qué estaba mal: (1-2 líneas)
Código corregido:
```
(aquí el código completo ya corregido, listo para copiar y pegar)
```
Qué cambió: (lista breve de los cambios concretos que hiciste)

No agregues funciones ni cambios que el usuario no pidió. Conserva
el estilo y los nombres de variables originales siempre que sea
posible. Si el código ya está bien y no ves ningún problema, dilo
claramente en vez de inventar cambios innecesarios.
{contexto_archivos}{bloque_error}
Código:
{codigo}
"""
    return _consultar(prompt)


def explicar_error_sintaxis(
    nombre_archivo: str,
    numero_linea: int,
    mensaje_error: str,
    fragmento_codigo: str
) -> str:
    """
    A diferencia de revisar_archivo(), aquí Python YA encontró el
    error exacto (via ast.parse). Le damos a la IA solo el fragmento
    relevante y le pedimos que explique y corrija ESE punto
    específico, en vez de buscar a ciegas en todo el archivo.
    """
    prompt = f"""Eres un asistente de programación integrado en
DevBox. El intérprete de Python ya detectó un error de sintaxis
exacto en este archivo. Tu trabajo es explicarlo y corregirlo, NO
buscar el problema (ya está localizado).

Archivo: {nombre_archivo}
Línea donde Python reportó el error: {numero_linea}
Mensaje exacto de Python: {mensaje_error}

Fragmento de código alrededor de esa línea (con números de línea):
{fragmento_codigo}

Responde en español con este formato exacto, sin agregar nada más:

Qué está mal: (1-2 líneas)
Código corregido:
```
(solo el fragmento de arriba, ya corregido)
```
"""
    return _consultar(prompt)


def revisar_archivo(
    nombre_archivo: str, contenido: str, ruta_completa: str | None = None
) -> tuple[str, dict | None]:
    """
    Revisa un archivo buscando errores. Para lenguajes con un
    verificador de sintaxis gratuito disponible (Python, Node.js,
    PHP, Go, Ruby, Perl, C, C++), lo usa primero: encuentra errores
    de forma instantánea y 100% precisa, sin necesidad de IA. Solo si
    ese verificador encuentra un problema, se le pide a la IA que
    explique y corrija ESA línea exacta -en vez de pedirle que
    busque a ciegas en todo el archivo.

    Para lenguajes sin verificador disponible (o si la herramienta
    correspondiente no está instalada), se le pide a la IA que
    revise el archivo completo, con la limitación conocida de que
    puede no ser tan confiable en archivos largos.

    Devuelve (texto_para_mostrar, info_aplicable). 'info_aplicable'
    es None si no hay una corrección puntual que se pueda aplicar
    automáticamente al archivo (por ejemplo, si no se encontró
    ningún problema, o si se usó el modo genérico de búsqueda a
    ciegas). Si no es None, trae {"ruta", "linea_inicio", "linea_fin"}
    listos para usarse con aplicar_correccion().
    """
    if nombre_archivo.endswith(".py"):
        return _revisar_con_ast_python(nombre_archivo, contenido, ruta_completa)

    if ruta_completa:
        if nombre_archivo.endswith((".js", ".mjs", ".cjs")) and shutil.which("node"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["node", "--check", ruta_completa],
                herramienta="node --check",
                patron_linea=r":(\d+)\n",
                patron_mensaje=r"(?:SyntaxError|Error): (.+)"
            )

        if nombre_archivo.endswith(".php") and shutil.which("php"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["php", "-l", ruta_completa],
                herramienta="php -l",
                patron_linea=r"on line (\d+)",
                patron_mensaje=r"Parse error:\s*(.+?)\s+in\s"
            )

        if nombre_archivo.endswith(".go") and shutil.which("gofmt"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["gofmt", "-e", ruta_completa],
                herramienta="gofmt",
                patron_linea=r":(\d+):\d+:",
                patron_mensaje=r":\d+:\d+:\s*(.+)"
            )

        if nombre_archivo.endswith(".rb") and shutil.which("ruby"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["ruby", "-c", ruta_completa],
                herramienta="ruby -c",
                patron_linea=r":(\d+):",
                patron_mensaje=r":\d+:\s*(.+)"
            )

        if nombre_archivo.endswith((".pl", ".pm")) and shutil.which("perl"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["perl", "-c", ruta_completa],
                herramienta="perl -c",
                patron_linea=r"line (\d+)",
                patron_mensaje=r"(syntax error.*)"
            )

        if nombre_archivo.endswith(".c") and shutil.which("gcc"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["gcc", "-fsyntax-only", ruta_completa],
                herramienta="gcc -fsyntax-only",
                patron_linea=r":(\d+):\d+:\s*error:",
                patron_mensaje=r":\d+:\d+:\s*error:\s*(.+)"
            )

        if nombre_archivo.endswith((".cpp", ".cc", ".cxx")) and shutil.which("g++"):
            return _revisar_con_comando_externo(
                nombre_archivo, contenido, ruta_completa,
                comando=["g++", "-fsyntax-only", ruta_completa],
                herramienta="g++ -fsyntax-only",
                patron_linea=r":(\d+):\d+:\s*error:",
                patron_mensaje=r":\d+:\d+:\s*error:\s*(.+)"
            )

    return _revisar_archivo_generico(nombre_archivo, contenido)


def _mensaje_sintaxis_ok(nombre_archivo: str, contenido: str, herramienta: str) -> str:
    """
    Arma el mensaje que se muestra cuando el verificador de sintaxis
    NO encontró ningún error. Antes de solo decir "todo bien", hace
    una pasada rápida y acotada con la IA (ver
    _revisar_logica_basica) para detectar si algo huele a error de
    LÓGICA y, si es así, redirigir al usuario al botón correcto en
    vez de dejarlo sin pistas.
    """
    base = (
        f"✅ Sintaxis correcta según {herramienta}. No se encontraron "
        f"errores de sintaxis en '{nombre_archivo}'."
    )

    try:
        resultado_logica = _revisar_logica_basica(nombre_archivo, contenido)
    except OllamaNoDisponible:
        return (
            f"{base}\n\n"
            "Nota: esto solo confirma que el archivo es sintácticamente "
            "válido, no revisa errores de lógica."
        )

    if re.search(r"error de l[oó]gica\??:\s*s[ií]", resultado_logica, re.IGNORECASE):
        return (
            f"{base}\n\n"
            "🤔 A simple vista, esto podría tener un error de LÓGICA "
            f"(no de sintaxis):\n{resultado_logica}\n\n"
            "👉 Prueba con el botón 'Corregir código', pegando esta "
            "función o sección -ahí la IA se enfoca en revisar la "
            "lógica en vez de la sintaxis."
        )

    return (
        f"{base}\n\n"
        "También se hizo un vistazo rápido por errores de lógica "
        "obvios y no se detectó nada evidente, pero esto no es un "
        "análisis exhaustivo -si tienes un comportamiento incorrecto, "
        "prueba con 'Corregir código' pegando la parte que sospechas."
    )


def _revisar_logica_basica(nombre_archivo: str, contenido: str) -> str:
    """
    Se llama solo cuando el archivo YA pasó el verificador de
    sintaxis. A diferencia del modo genérico de revisión (que pide un
    análisis completo y estructurado), aquí la tarea es angosta a
    propósito: no localizar ni corregir nada, solo responder sí/no a
    si algo parece un error de lógica -para poder recomendar el botón
    correcto sin arriesgar el mismo problema que tuvo pedirle a un
    modelo de 7B "revisa todo el archivo y dame el fix exacto".
    """
    prompt = f"""Eres un asistente de programación integrado en
DevBox. El archivo '{nombre_archivo}' de abajo YA pasó el
verificador de sintaxis sin ningún error -compila/corre bien. Tu
única tarea es un vistazo rápido, NO una revisión exhaustiva: ¿ves
algo que parezca un error de LÓGICA obvio (un cálculo mal hecho, una
condición invertida, un índice fuera de rango, una comparación al
revés, etc.)? No lo corrijas ni des código, solo responde con este
formato exacto y nada más:

¿Posible error de lógica?: Sí / No
Razón: (si es Sí, una sola línea diciendo qué se ve raro y en qué
función. Si es No, escribe exactamente "No se detectó nada evidente
a simple vista.")

Archivo:
{contenido}
"""
    return _consultar(prompt, num_ctx=8192)


def _revisar_con_ast_python(
    nombre_archivo: str, contenido: str, ruta_completa: str | None
) -> tuple[str, dict | None]:
    import ast

    try:
        ast.parse(contenido)
        return (
            _mensaje_sintaxis_ok(
                nombre_archivo, contenido,
                herramienta="el propio parser de Python (ast.parse)"
            ),
            None
        )

    except SyntaxError as error:
        return _explicar_linea_con_ia(
            nombre_archivo,
            contenido.splitlines(),
            linea_error=error.lineno or 1,
            mensaje_error=error.msg,
            herramienta="el parser de Python (ast.parse)",
            ruta_completa=ruta_completa
        )


def _revisar_con_comando_externo(
    nombre_archivo: str,
    contenido: str,
    ruta_completa: str,
    comando: list[str],
    herramienta: str,
    patron_linea: str,
    patron_mensaje: str,
) -> tuple[str, dict | None]:
    import re
    import subprocess

    try:
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=15, check=False
        )

    except (OSError, subprocess.TimeoutExpired) as error:
        return f"⚠️ No se pudo ejecutar {herramienta}: {error}", None

    salida_completa = resultado.stdout + resultado.stderr

    if resultado.returncode == 0:
        return (
            _mensaje_sintaxis_ok(nombre_archivo, contenido, herramienta),
            None
        )

    coincidencia_linea = re.search(patron_linea, salida_completa)
    coincidencia_mensaje = re.search(patron_mensaje, salida_completa)

    linea_error = int(coincidencia_linea.group(1)) if coincidencia_linea else 1
    mensaje_error = (
        coincidencia_mensaje.group(1).strip()
        if coincidencia_mensaje
        else salida_completa.strip()[:200]
    )

    return _explicar_linea_con_ia(
        nombre_archivo,
        contenido.splitlines(),
        linea_error=linea_error,
        mensaje_error=mensaje_error,
        herramienta=herramienta,
        ruta_completa=ruta_completa
    )


def _explicar_linea_con_ia(
    nombre_archivo: str,
    lineas: list[str],
    linea_error: int,
    mensaje_error: str,
    herramienta: str,
    ruta_completa: str | None = None,
) -> tuple[str, dict | None]:
    inicio = max(0, linea_error - 4)
    fin = min(len(lineas), linea_error + 3)

    fragmento = "\n".join(
        f"{numero:>4} | {lineas[numero - 1]}"
        for numero in range(inicio + 1, fin + 1)
        if numero - 1 < len(lineas)
    )

    numero_lineas_fragmento = fragmento.count("\n") + 1

    prompt = f"""Eres un asistente de programación integrado en
DevBox. {herramienta} encontró un error de sintaxis en el archivo
'{nombre_archivo}':

Línea: {linea_error}
Mensaje: {mensaje_error}

Aquí está el fragmento del archivo alrededor de esa línea (con
números de línea reales, no los inventes):

{fragmento}

Responde en español con este formato exacto:

Tipo de error: (una etiqueta corta y precisa, por ejemplo "falta
paréntesis de cierre", "falta punto y coma", "falta dos puntos",
"comilla sin cerrar", "indentación incorrecta". Debe corresponder
EXACTAMENTE a lo que describe el mensaje de {herramienta} de arriba
-no inventes una causa distinta a la que ese mensaje ya indica.)
Qué está mal: (1-2 líneas, en términos claros para un desarrollador,
consistente con el "Tipo de error" de arriba)
Código corregido de esta sección:
```
(TODO el fragmento de arriba, línea por línea, con el error ya
corregido. Debe tener EXACTAMENTE {numero_lineas_fragmento} líneas,
igual que el fragmento original -no omitas ninguna línea de
contexto, aunque no tenga relación con el error.

IMPORTANTE: NO incluyas el número de línea ni el símbolo "|" en tu
respuesta -esos solo eran una referencia para ti, no son parte del
código real. Por ejemplo, si el fragmento de arriba mostraba
"   5 | function suma(a, b) {{", tu código corregido debe decir
solo "function suma(a, b) {{", sin el "5 |" al inicio.)
```
"""
    texto = _consultar(prompt)

    info_aplicable = None

    if ruta_completa:
        info_aplicable = {
            "ruta": ruta_completa,
            "linea_inicio": inicio + 1,
            "linea_fin": fin,
        }

    return texto, info_aplicable


def _revisar_archivo_generico(nombre_archivo: str, contenido: str) -> tuple[str, None]:
    lineas = contenido.splitlines()
    contenido_numerado = "\n".join(
        f"{numero:>4} | {linea}" for numero, linea in enumerate(lineas, start=1)
    )

    prompt = f"""Eres un asistente de programación integrado en
DevBox. A continuación tienes el contenido de un archivo de código,
con cada línea precedida por su número exacto. No existe un
verificador automático de sintaxis para este lenguaje, así que tu
trabajo es revisarlo tú mismo de principio a fin.

IMPORTANTE: No resumas qué hace el archivo. No describas su
arquitectura. Ve directo a buscar errores de sintaxis evidentes. Si
no encuentras ninguno, responde solo con "No se encontró ningún
problema evidente." y nada más.

Responde en español con EXACTAMENTE este formato:

¿Se encontró un problema?: Sí / No
Línea exacta: (el número que aparece a la izquierda)
Tipo de error: (una etiqueta corta, ej. "falta paréntesis de cierre",
"falta punto y coma", "comilla sin cerrar", "indentación incorrecta")
Qué está mal: (1-2 líneas)
Código corregido de esa sección:
```
(solo el fragmento relevante, ya corregido)
```

Archivo: {nombre_archivo}

Contenido con números de línea:
{contenido_numerado}
"""
    return _consultar(prompt, num_ctx=8192), None


def extraer_bloque_codigo(texto_respuesta: str) -> str | None:
    """
    Saca el fragmento de código entre los ``` de la respuesta de la
    IA, para poder aplicarlo directo al archivo. Devuelve None si no
    encuentra un bloque de código reconocible.

    Busca el bloque que viene DESPUÉS de la etiqueta "Código
    corregido" o "Código generado" (en cualquiera de sus variantes:
    "...de esta sección", "...de esa sección", etc.), no el primer
    ``` que aparezca en todo el texto. Una prueba real mostró que a
    veces el modelo cita el código original dentro de "Qué estaba
    mal" a modo de ejemplo -si tomáramos a ciegas el primer ``` del
    texto completo, agarraríamos ese fragmento incompleto en vez de
    la corrección real, dejando el código aplicado roto (con una
    función a la que le falta el "def ...:").

    Como red de seguridad extra, también quita cualquier prefijo de
    número de línea (formato "  12 | codigo") que el modelo haya
    copiado por error del fragmento numerado que le mandamos como
    contexto -si no se limpia, ese texto queda como código literal
    roto al aplicar la corrección.
    """
    texto_busqueda = texto_respuesta
    ancla = re.search(r"[Cc]ódigo (?:corregido|generado)[^\n]*\n", texto_respuesta)

    if ancla:
        texto_busqueda = texto_respuesta[ancla.end():]

    coincidencia = re.search(r"```(?:\w*\n)?(.*?)```", texto_busqueda, re.DOTALL)

    if not coincidencia:
        return None

    bloque = coincidencia.group(1).rstrip("\n")
    return _quitar_numeros_de_linea(bloque)


def _quitar_numeros_de_linea(texto: str) -> str:
    import re

    patron_prefijo = re.compile(r"^\s*\d+\s*\|\s?")

    lineas_limpias = [
        patron_prefijo.sub("", linea) for linea in texto.splitlines()
    ]

    return "\n".join(lineas_limpias)


def generar_vista_previa(info_aplicable: dict, texto_respuesta: str) -> tuple[bool, str]:
    """
    Arma un texto tipo "antes / después" para que el usuario vea
    EXACTAMENTE qué líneas se van a borrar y con qué se van a
    reemplazar, antes de tocar el archivo de verdad. No escribe
    nada, solo prepara la vista previa.

    Devuelve (se_puede_aplicar, texto_vista_previa).
    """
    codigo_nuevo = extraer_bloque_codigo(texto_respuesta)

    if codigo_nuevo is None:
        return False, "No se encontró un bloque de código en la respuesta de la IA."

    ruta = Path(info_aplicable["ruta"])
    linea_inicio = info_aplicable["linea_inicio"]
    linea_fin = info_aplicable["linea_fin"]

    try:
        lineas_actuales = ruta.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        return False, f"No se pudo leer el archivo: {error}"

    if linea_inicio < 1 or linea_fin > len(lineas_actuales) or linea_inicio > linea_fin:
        return False, "El rango de líneas ya no coincide con el archivo actual."

    lineas_antes = lineas_actuales[linea_inicio - 1: linea_fin]
    lineas_despues = codigo_nuevo.splitlines()

    texto = (
        f"--- ANTES (líneas {linea_inicio}-{linea_fin}) ---\n"
        + "\n".join(lineas_antes)
        + "\n\n--- DESPUÉS ---\n"
        + "\n".join(lineas_despues)
    )

    if len(lineas_despues) < len(lineas_antes):
        texto = (
            "⚠️ ATENCIÓN: la corrección tiene MENOS líneas que el "
            "fragmento original -esto puede significar que se va a "
            "perder código que no tenía relación con el error. Revisa "
            "con cuidado antes de aplicar.\n\n" + texto
        )

    return True, texto


def aplicar_correccion(info_aplicable: dict, texto_respuesta: str) -> tuple[bool, str]:
    """
    Reemplaza las líneas [linea_inicio, linea_fin] del archivo en
    'info_aplicable["ruta"]' con el bloque de código que la IA
    devolvió en 'texto_respuesta'. Antes de tocar el archivo, guarda
    una copia de respaldo (archivo.bak).

    Devuelve (exito, mensaje).
    """
    codigo_nuevo = extraer_bloque_codigo(texto_respuesta)

    if codigo_nuevo is None:
        return False, "No se encontró un bloque de código en la respuesta de la IA."

    ruta = Path(info_aplicable["ruta"])
    linea_inicio = info_aplicable["linea_inicio"]
    linea_fin = info_aplicable["linea_fin"]

    try:
        contenido_actual = ruta.read_text(encoding="utf-8")
    except OSError as error:
        return False, f"No se pudo leer el archivo: {error}"

    lineas_actuales = contenido_actual.splitlines()

    if linea_inicio < 1 or linea_fin > len(lineas_actuales) or linea_inicio > linea_fin:
        return False, "El rango de líneas ya no coincide con el archivo actual (¿se modificó mientras tanto?)."

    ruta_respaldo = ruta.with_suffix(ruta.suffix + ".bak")

    try:
        ruta_respaldo.write_text(contenido_actual, encoding="utf-8")
    except OSError as error:
        return False, f"No se pudo crear el respaldo, se canceló por seguridad: {error}"

    lineas_nuevas = (
        lineas_actuales[: linea_inicio - 1]
        + codigo_nuevo.splitlines()
        + lineas_actuales[linea_fin:]
    )

    try:
        ruta.write_text("\n".join(lineas_nuevas) + "\n", encoding="utf-8")
    except OSError as error:
        return False, f"No se pudo escribir el archivo corregido: {error}"

    return True, f"Corrección aplicada. Respaldo guardado en '{ruta_respaldo.name}'."


def esta_disponible() -> bool:
    """Revisa rápido si Ollama está corriendo, sin lanzar excepción."""
    try:
        peticion = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(peticion, timeout=3):
            return True

    except Exception:
        return False


def listar_archivos_proyecto(ruta_carpeta: str, limite: int = 150) -> list[str]:
    """
    Lista rutas relativas de archivos dentro de una carpeta de
    proyecto, para dárselas como contexto a explicar_error(). Ignora
    carpetas de dependencias/entornos que no aportan nada útil.
    """
    import os

    ignoradas = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "env", "dist", "build", ".next", "target", ".idea", ".vscode",
    }

    resultado = []
    base = Path(ruta_carpeta)

    for raiz, carpetas, archivos in os.walk(base):
        carpetas[:] = [c for c in carpetas if c not in ignoradas]

        for archivo in archivos:
            ruta_relativa = str(Path(raiz, archivo).relative_to(base))
            resultado.append(ruta_relativa)

            if len(resultado) >= limite:
                return resultado

    return resultado
