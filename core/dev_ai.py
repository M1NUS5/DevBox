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
URL_OLLAMA_CHAT = "http://localhost:11434/api/chat"
MODELO_POR_DEFECTO = "qwen2.5-coder:7b"
TIMEOUT_SEGUNDOS = 240


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


def _consultar_chat(mensajes: list[dict], modelo: str = MODELO_POR_DEFECTO, num_ctx: int = 8192) -> str:
    """
    Como _consultar(), pero habla con /api/chat en vez de /api/generate:
    manda una lista de mensajes {"role", "content"} (system/user/
    assistant) en vez de un solo prompt, así Ollama mantiene el
    contexto de toda la conversación -necesario para que el chat de
    DevAI recuerde lo que se dijo en turnos anteriores.
    """
    cuerpo = {
        "model": modelo,
        "messages": mensajes,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": num_ctx},
    }

    cuerpo = json.dumps(cuerpo).encode("utf-8")

    peticion = urllib.request.Request(
        URL_OLLAMA_CHAT,
        data=cuerpo,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT_SEGUNDOS) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
            return datos.get("message", {}).get("content", "").strip()

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


def _mensaje_sistema_chat(
    archivos_proyecto: list[str] | None = None, contexto_codigo: str = ""
) -> str:
    """
    Mensaje de sistema del chat de DevAI. Reúne, en un solo lugar,
    todo lo que antes eran tres prompts separados (explicar_error,
    corregir_codigo, generar_codigo) -incluidas las reglas de calidad
    para código generado que se afinaron y verificaron una por una
    (ver core/dev_ai.py en el historial de git y la memoria del
    proyecto para el porqué de cada una).
    """
    contexto_archivos = ""

    if archivos_proyecto:
        muestra = "\n".join(f"- {archivo}" for archivo in archivos_proyecto[:150])
        contexto_archivos = f"""

Archivos que existen actualmente en la carpeta del proyecto del
usuario (úsalos para no confundir un módulo local que falta copiar
con una librería de terceros que falta instalar, y para que el
código que generes encaje con lo que ya existe):

{muestra}
"""

    if contexto_codigo:
        contexto_archivos += f"""

Contenido real de algunos archivos de código de ese proyecto (puede
no ser el proyecto completo si es muy grande -se cortó por espacio).
Úsalo para revisar cómo interactúan funciones que viven en archivos
distintos al que el usuario pegó directamente en el chat: si pregunta
por o pega una función que llama a otra definida en uno de estos
archivos, no asumas cómo es esa otra función -revisa su código real
aquí abajo antes de responder:
{contexto_codigo}
"""

    return f"""Eres DevAI, el asistente de programación integrado en
la aplicación de escritorio DevBox. Corres localmente sobre Ollama,
sin conexión a internet ni límite de uso. Hablas en español, claro y
directo. Esto es un chat de ida y vuelta, no un formulario de una
sola respuesta: puedes hacer preguntas de vuelta si algo es
ambiguo, y recuerdas lo que se dijo antes en la conversación.

Según lo que el desarrollador te pida en cada mensaje, puedes:

1. Explicar un error o traceback real que te pegue (causa probable y
   solución). Si en cambio describe un comportamiento incorrecto sin
   ningún error real (el programa corre pero hace algo raro), dilo
   claramente y pide que te pase el código relacionado -no inventes
   una causa falsa de "error" para algo que no lo es.

2. Corregir un fragmento de código que te pase, cuando tenga un
   problema. Da el código completo ya corregido en un bloque con tres
   comillas invertidas (```), listo para copiar -no agregues cambios
   que no se pidieron, y si el código ya está bien dilo en vez de
   inventar un cambio innecesario.

3. Generar código nuevo desde una descripción -un archivo completo y
   funcional, no un fragmento de ejemplo. Cuando generes algo nuevo,
   sigue estas reglas siempre, sin que haga falta que te las pidan:
   - Si te piden una página o aplicación para administrar algún tipo
     de información (un inventario, una lista de tareas, un
     directorio de contactos, etc.), entrégala realmente completa y
     usable, no una maqueta mínima, aunque el usuario haya descrito
     la idea en una sola frase corta:
     - Los datos deben persistir de verdad. En una página web sin
       backend, usa `localStorage` (guarda y lee un JSON) para que
       la información sobreviva a recargar la página -nunca datos
       que solo viven en memoria mientras el usuario no navegue a
       otro lado. Si el proyecto sí tiene backend, usa una base de
       datos real (SQLite es suficiente casi siempre).
     - Incluye agregar, ver, EDITAR y eliminar -no solo agregar y
       eliminar. Un botón "Editar" que precargue el formulario con
       los datos del elemento y actualice en vez de duplicar.
     - Antes de definir los campos de cada elemento, piensa qué
       necesitaría de verdad ese tipo de información en la vida
       real -por ejemplo, un inventario normalmente necesita
       cantidad, ubicación y estado, no solo un nombre- e inclúyelos
       aunque el usuario no los haya mencionado uno por uno.
     - Solo entrega algo más simple si el usuario pide explícitamente
       una versión básica, de prueba, o sin guardar datos.
   - Si interactúa con una base de datos, usa SIEMPRE consultas
     parametrizadas o prepared statements (por ejemplo
     $conn->prepare() + bind_param() en PHP con mysqli, parámetros
     con ? o %s en otros lenguajes). NUNCA concatenes valores
     directamente en un string SQL -es una vulnerabilidad de
     inyección SQL real.
   - Si generas HTML/JavaScript que muestra en la página datos que
     vienen de un formulario, de la URL, o de cualquier fuente que el
     usuario final controle, NUNCA los insertes con `innerHTML`
     usando un template literal (por ejemplo
     `div.innerHTML = \`<p>${{nombre}}</p>\``) -eso es una
     vulnerabilidad XSS real si ese dato contiene HTML o JavaScript.
     En vez de eso, crea el elemento con `document.createElement(...)`
     y pon el dato con `.textContent` (nunca `.innerHTML`) en ese
     nodo específico. `innerHTML` solo es aceptable para markup fijo
     que tú mismo escribiste, nunca para datos externos.
   - Este error aparece TÍPICAMENTE al renderizar una lista o tabla
     desde un arreglo de objetos -por ejemplo, al recorrer un
     inventario con `.forEach(item => ...)` para dibujar cada fila.
     En ese caso específico, arma cada celda por separado, así:
     `const celda = document.createElement('td');` seguido de
     `celda.textContent = item.campo;` y `fila.appendChild(celda);`
     -repetido por cada campo- en vez de construir la fila entera
     como un string HTML con los valores del objeto interpolados
     adentro. Este patrón (una fila armada como string con datos del
     objeto metidos con ${{}}) es exactamente el que debes evitar.
   - Si te piden una "API" o "endpoint", genera algo que de verdad
     reciba peticiones HTTP (lee método y parámetros, responde en el
     formato que corresponda) -no solo funciones sueltas con una
     llamada de ejemplo.
   - No expongas errores internos ni consultas SQL completas en lo
     que se le devuelve al usuario final -usa mensajes genéricos.
   - Si la tarea en realidad necesita más de un archivo, NO simules
     varios archivos con comentarios dentro de uno solo -eso no
     funciona guardado como un único archivo real. Genera el archivo
     más importante, y di claramente que la tarea completa
     necesitaría más archivos, y cuáles serían.
   - Antes de usar una función/clase de una librería, asegúrate de
     que existe REALMENTE ahí -no lo asumas por analogía con otra
     librería parecida (por ejemplo, `threading` de Python NO tiene
     una clase `Value`, esa es de `multiprocessing`).
   - Para procesar tareas en paralelo con límite de concurrencia en
     Python, usa `concurrent.futures.ThreadPoolExecutor` con
     `max_workers=N`, no cuentes hilos activos a mano. Para un
     contador compartido, crea explícitamente
     `lock = threading.Lock()` antes de cualquier `with lock:`, e
     incrementa el contador ahí justo cuando cada tarea termina.
   - Si la descripción menciona un elemento específico ("con una
     contraseña", "con un límite de tamaño", etc.), tu código DEBE
     usarlo de verdad. Para cifrado con contraseña en Python: usa
     `pycryptodome` (`Crypto.Cipher.AES` + `Crypto.Protocol.KDF.PBKDF2`,
     `PBKDF2(password.encode(), salt, dkLen=32, count=200000)`,
     nunca el count por defecto). NO uses
     `cryptography.fernet.Fernet` para esto (`Fernet.generate_key()`
     no deriva nada de la contraseña).
   - Esto es distinto de lo anterior: si generas un sistema de LOGIN
     o registro de usuarios, la contraseña NUNCA se guarda en texto
     plano ni cifrada de forma reversible -se guarda solo un HASH de
     un solo sentido (nunca se necesita recuperar la contraseña
     original, solo verificarla). En Python usa
     `werkzeug.security.generate_password_hash()` /
     `check_password_hash()` (ya viene con Flask) o la librería
     `bcrypt`; en PHP usa las funciones nativas `password_hash()` /
     `password_verify()`. NUNCA uses `md5()`, `sha1()`, ni PBKDF2 con
     AES para esto -eso es cifrado reversible, lo correcto para
     contraseñas de login es un hash de un solo sentido.
   - Al sanitizar un nombre de archivo contra path traversal,
     reemplaza cualquier barra invertida por barra normal ANTES de
     aplicar `basename()`, para cubrir también rutas estilo Windows.
   - Con Flask-JWT-Extended, `create_access_token(identity=...)`
     necesita un string (`str(user.id)`), nunca un entero directo.
   - Con Flask-SQLAlchemy (o cualquier ORM), siempre incluye el
     código que crea las tablas (`db.create_all()` dentro de
     `app.app_context()`) antes de usarlas.
   - No reutilices el mismo nombre de variable para dos propósitos
     distintos en el mismo archivo/función.
   - Si generas un evaluador de expresiones con precedencia de
     operadores, usa descenso recursivo con una función por nivel de
     precedencia (`parse_suma`/`parse_termino`/`parse_factor`), nunca
     una sola pila que reduzca en cuanto aparece el siguiente token
     -compara precedencias antes de reducir, y cuidado con el orden
     de los operandos al sacarlos de la pila (el primero que sale es
     el derecho).
   - En Kotlin, al leer texto del usuario con `readLine()` para
     compararlo contra valores exactos (por ejemplo en un `when` que
     compara contra strings literales), encadena SIEMPRE `.trim()`
     antes de `.lowercase()`/`.uppercase()` -por ejemplo
     `readLine()?.trim()?.lowercase()`- así un espacio de más al
     principio o al final no hace que la comparación falle sin razón.
   - En Kotlin, si un campo de una `data class` necesita cambiar de
     valor después de creada la instancia (por ejemplo, marcar una
     tarea como completada), NUNCA lo declares `val` y luego intentes
     reasignarlo (`instancia.campo = valor`) -eso NO compila
     ("Val cannot be reassigned"). Dos opciones correctas: declara
     ese campo específico `var` en la `data class`
     (`data class Tarea(val id: Int, var completada: Boolean)`), o si
     prefieres mantenerla inmutable, usa el método `.copy(campo =
     nuevoValor)` que Kotlin genera automáticamente para crear una
     copia con ese campo actualizado, en vez de mutar la instancia
     original.
   - En Kotlin con Jetpack Compose, para obtener un ViewModel dentro
     de una función `@Composable`, usa SIEMPRE
     `val nombre: TuViewModel = viewModel()` (de
     `androidx.lifecycle.viewmodel.compose.viewModel`, dependencia
     `androidx.lifecycle:lifecycle-viewmodel-compose`). NUNCA uses
     `ViewModelProvider(this).get(TuViewModel::class.java)` dentro de
     una función `@Composable` -ese patrón solo es válido dentro de
     una Activity/Fragment clásica (basada en XML), porque ahí sí
     existe `this` como referencia a la Activity. Dentro de una
     función `@Composable` suelta, `this` no existe y el código no
     compila.
   - En Kotlin, si usas `MutableStateFlow`/`StateFlow` con el método
     `.update {{ estadoActual -> estadoActual.copy(...) }}` para
     actualizar el estado, agrega SIEMPRE el import
     `import kotlinx.coroutines.flow.update` de forma explícita,
     además de los imports de `MutableStateFlow`/`StateFlow` -`update`
     es una función de extensión, no un método de la clase, y sin ese
     import exacto da "Unresolved reference 'update'" y, en cadena,
     también falla la inferencia de tipo del parámetro del lambda y el
     `.copy(...)` de adentro.
   - En Kotlin con Android, si usas `Toast.makeText(...)` en
     cualquier parte del código (dentro o fuera de un `@Composable`),
     agrega SIEMPRE el import `import android.widget.Toast` de forma
     explícita -ese import se omite con frecuencia incluso cuando sí
     se usa correctamente `LocalContext.current` como primer
     argumento, y sin él da "Unresolved reference 'Toast'".
   - En Kotlin, al comparar un valor `Double` contra un rango con el
     operador `in` (por ejemplo `distancia in 2..10`), escribe SIEMPRE
     los límites del rango como `Double` (`distancia in 2.0..10.0`),
     nunca como enteros (`2..10`, que crea un `IntRange`) -comparar un
     `Double` contra un `IntRange` no compila ("type inference failed,
     el valor del parámetro de tipo T debe mencionarse en los tipos de
     entrada").

Sin importar cuál de los tres casos aplique, CUALQUIER código que
muestres -así sea una sola línea- va SIEMPRE dentro de un bloque
delimitado con tres comillas invertidas y el nombre del lenguaje
justo después de las comillas de apertura (```python, ```html,
```css, ```javascript, ```kotlin, etc.), cerrado con otras tres
comillas invertidas al final. Nunca pegues código suelto fuera de
esas comillas, ni siquiera como parte de una explicación. Si la
tarea necesita varios archivos, cada archivo va en su propio bloque
```lenguaje separado, con su nombre de archivo indicado justo antes
del bloque.

No inventes que el código hace algo que en realidad no hace. Si la
descripción es ambigua, puedes preguntar antes de responder, ya que
esto es una conversación.

Cuando el usuario te pida modificar o agregarle algo a código que ya
generaste antes en esta misma conversación, parte de ese código
existente -no lo reescribas desde cero ni le cambies nombres de
función/variable sin necesidad. Y si lo que pide ya lo hace el
código anterior, dilo directamente ("eso ya lo maneja el código de
arriba, no hace falta cambiar nada") en vez de disculparte por un
error que no existió y devolver el mismo código como si lo hubieras
corregido -eso es fingir un arreglo falso, y es tan malo como
inventar que el código hace algo que no hace.
{contexto_archivos}"""


def chat_devai(
    historial: list[dict],
    archivos_proyecto: list[str] | None = None,
    contexto_codigo: str = "",
) -> str:
    """
    Continúa la conversación de chat de DevAI. 'historial' es la
    lista de turnos previos (roles "user"/"assistant", sin el
    mensaje de sistema -este se antepone aquí en cada llamada, para
    que si el usuario cambia de carpeta de proyecto a medio chat, el
    contexto de archivos se actualice sin tener que reconstruir todo
    el historial).
    """
    mensajes = [
        {"role": "system", "content": _mensaje_sistema_chat(archivos_proyecto, contexto_codigo)}
    ] + historial

    respuesta = _consultar_chat(mensajes)
    respuesta = _corregir_deprecaciones_kotlin(respuesta)
    return _advertir_xss_potencial(respuesta)


def _corregir_deprecaciones_kotlin(texto_respuesta: str) -> str:
    """
    Red de seguridad determinista para un problema real confirmado
    con pruebas repetidas: al generar Kotlin, el modelo usa
    `toLowerCase()`/`toUpperCase()` de forma consistente (3 de 3
    intentos, incluso después de agregar una regla explícita en el
    prompt pidiendo lo contrario -esa regla no se le pegó y se quitó
    del prompt de sistema). Esas funciones ya no compilan en
    versiones recientes de Kotlin (son un ERROR, no un warning).

    En vez de seguir insistiendo por prompt (ya se confirmó que no
    funciona), se corrige aquí mismo con una sustitución de texto
    simple, aplicada SOLO dentro de bloques de código marcados
    explícitamente como ```kotlin -nunca fuera de esos bloques, para
    no romper JavaScript u otros lenguajes donde `toLowerCase()`/
    `toUpperCase()` sí son las funciones correctas.
    """
    def _reemplazar_en_bloque(coincidencia: re.Match) -> str:
        bloque = coincidencia.group(0)
        bloque = bloque.replace(".toLowerCase()", ".lowercase()")
        bloque = bloque.replace(".toUpperCase()", ".uppercase()")
        return bloque

    return re.sub(
        r"```kotlin\n.*?```",
        _reemplazar_en_bloque,
        texto_respuesta,
        flags=re.DOTALL,
    )


_PATRON_INNERHTML_RIESGOSO = re.compile(
    r"\.innerHTML\s*=\s*`[^`]*\$\{\s*\w+\.\w+", re.DOTALL
)


def _advertir_xss_potencial(texto_respuesta: str) -> str:
    """
    Red de seguridad determinista para un problema real confirmado con
    pruebas repetidas: al generar HTML/JavaScript que renderiza una
    lista/tabla desde un arreglo de objetos (ej. un inventario), el
    modelo usa con frecuencia `elemento.innerHTML = \`...${item.campo}...\``
    para armar cada fila -eso es una vulnerabilidad XSS real si ese
    dato viene de un formulario. Se agregó una regla explícita al
    prompt pidiendo usar `textContent`/`createElement` en su lugar,
    pero verificado con regeneraciones repetidas, solo se cumple
    ~40% de las veces -el mismo perfil que el caso de `toLowerCase()`
    en Kotlin: un hábito demasiado arraigado para que una instrucción
    de prompt lo corrija de forma confiable.

    A diferencia del caso de Kotlin, aquí NO se reescribe el código
    automáticamente -cambiar de construir HTML por string a construir
    nodos del DOM es una transformación estructural, no una simple
    sustitución de texto, y un regex genérico arriesga romper código
    válido. En vez de eso, esta función solo detecta el patrón
    peligroso y agrega una advertencia visible al final de la
    respuesta, para que el usuario sepa que debe revisarlo antes de
    usar ese código con datos reales.
    """
    if not _PATRON_INNERHTML_RIESGOSO.search(texto_respuesta):
        return texto_respuesta

    advertencia = (
        "\n\n---\n"
        "⚠️ **Nota de seguridad:** el código de arriba parece insertar "
        "datos con `innerHTML` usando un valor interpolado (por ejemplo "
        "`elemento.innerHTML = \\`...${item.campo}...\\``). Si ese dato "
        "viene de un formulario u otra fuente externa, esto permite "
        "XSS -alguien podría escribir HTML/JavaScript en vez de un "
        "valor normal y que se ejecute en la página. Antes de usarlo "
        "con datos reales, cambia esa parte para construir el elemento "
        "con `document.createElement(...)` y asignar el dato con "
        "`.textContent` en vez de `.innerHTML`."
    )
    return texto_respuesta + advertencia


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


_EXTENSIONES_CODIGO = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java",
    ".go", ".rs", ".php", ".rb", ".pl", ".pm", ".c", ".h", ".cpp",
    ".cc", ".cxx", ".hpp", ".kt", ".swift", ".cs",
}


def leer_contexto_codigo_proyecto(
    ruta_carpeta: str, archivos: list[str], presupuesto_caracteres: int = 8000
) -> str:
    """
    A diferencia de listar_archivos_proyecto() (que solo da NOMBRES de
    archivo), esto lee el CONTENIDO real de un subconjunto de archivos
    de código del proyecto -para que el chat pueda razonar sobre cómo
    interactúan funciones que viven en archivos DISTINTOS al que el
    usuario pegó en el mensaje, en vez de solo ver ese fragmento
    aislado.

    Se limita a extensiones de código conocidas (ignora imágenes,
    binarios, etc.) y a un presupuesto total de caracteres, para no
    exceder la ventana de contexto del modelo (num_ctx=8192 en el
    chat) -se detiene apenas se alcanza el presupuesto, sin intentar
    leer el resto de la lista.

    Limitación conocida: el orden de inclusión es el de
    listar_archivos_proyecto() (orden de recorrido de carpetas), no un
    orden por relevancia -en un proyecto grande esto puede incluir
    archivos sin relación con la pregunta del usuario y dejar fuera el
    que sí importa. Funciona mejor cuanto más chico es el proyecto.
    """
    partes = []
    total = 0
    base = Path(ruta_carpeta)

    for relativa in archivos:
        if Path(relativa).suffix not in _EXTENSIONES_CODIGO:
            continue

        try:
            contenido = (base / relativa).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        bloque = f"\n--- {relativa} ---\n{contenido}\n"

        if total + len(bloque) > presupuesto_caracteres:
            break

        partes.append(bloque)
        total += len(bloque)

    return "".join(partes)


def listar_archivos_proyecto(ruta_carpeta: str, limite: int = 150) -> list[str]:
    """
    Lista rutas relativas de archivos dentro de una carpeta de
    proyecto, para dárselas como contexto al chat de DevAI. Ignora
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
