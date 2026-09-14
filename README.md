# DevBox

Centro de herramientas de desarrollo para escritorio (macOS), construido en
Python con `customtkinter`. No es un editor de código ni un clon de VS Code:
es un panel de apoyo para detectar tu entorno, explorar proyectos y contar
con un asistente de IA local que corre 100% en tu máquina.

## Características

### 📊 Dashboard
Detecta 22 lenguajes y herramientas instaladas en tu sistema (Python, Node,
Java, Kotlin, Go, Rust, PHP, Ruby, .NET, Swift, C/C++, Dart, Perl, Git,
Docker, npm, pip, Homebrew, VS Code, Maven, Yarn, CMake), con su versión
exacta y ruta. Incluye buscador en vivo, botón de actualización sin reiniciar
la app, exportación a `.json`, y copiar ruta por herramienta.

### 📁 Explorador de Proyectos
Apunta a una carpeta y detecta automáticamente el tipo de proyecto (Node,
Python, Rust, Go, Java/Kotlin, Ruby, PHP, Swift) según sus archivos clave,
cuenta archivos, revisa si tiene README/`.gitignore`/Git, y extrae las
dependencias reales declaradas.

### 🤖 DevAI — asistente de IA local
Corre sobre [Ollama](https://ollama.com) en tu máquina (modelo
`qwen2.5-coder:7b` por defecto) — sin API key, sin costo, sin límite de uso,
funciona sin internet una vez descargado el modelo.

Requiere:
```
brew install ollama
brew services start ollama
ollama pull qwen2.5-coder:7b
```

Cuatro modos:

- **🤖 Explicar error** — pega un traceback/error y te da causa probable y
  solución. Si seleccionas la carpeta del proyecto, distingue mejor entre un
  archivo local que falta copiar y un paquete que falta instalar con pip.
  Si lo que pegaste no parece un error real (sino una descripción de
  comportamiento incorrecto), te lo dice y te recomienda usar "Corregir
  código" en su lugar.

- **🛠️ Corregir código** — pega un fragmento de código (y opcionalmente el
  error asociado) y te devuelve el código corregido, listo para copiar. Con
  el botón "📂 Cargar archivo" puedes cargar un archivo real en vez de pegar
  a mano, y si la respuesta trae un bloque de código válido aparece
  "✅ Aplicar corrección al archivo" (misma vista previa + respaldo que abajo).

- **✨ Generar código** — describe qué código quieres (en cualquier lenguaje)
  y te genera un archivo completo y funcional desde cero, con un botón para
  guardarlo directo a disco. Sigue reglas fijas de calidad: si usa una base
  de datos, siempre con consultas parametrizadas (nunca concatenación de
  strings en SQL); si pides una "API", genera manejo real de peticiones HTTP,
  no solo funciones sueltas.

- **📄 Revisar archivo completo** — para Python, Node.js, PHP, Go, Ruby,
  Perl, C y C++, usa primero el verificador de sintaxis nativo del lenguaje
  (`ast.parse`, `node --check`, `php -l`, `gofmt`, `ruby -c`, `perl -c`,
  `gcc`/`g++ -fsyntax-only`) para localizar errores de sintaxis de forma
  instantánea y 100% precisa, y solo entonces le pide a la IA que
  explique/corrija esa línea exacta. Si la sintaxis está limpia, hace además
  un vistazo rápido por posibles errores de lógica y, si algo se ve raro, te
  recomienda pasar a "Corregir código". Para otros lenguajes sin verificador
  disponible, usa un modo genérico menos preciso.

  Cuenta con vista previa obligatoria ("Antes"/"Después") y respaldo
  automático (`.bak`) antes de aplicar cualquier corrección directo al
  archivo.

#### Limitaciones conocidas de DevAI

DevAI corre en un modelo local de 7B de parámetros — rápido y gratis, pero
con límites reales de razonamiento:

- **Muy confiable con un problema a la vez.** Tanto para errores de sintaxis
  (localizados por el verificador del lenguaje) como para un bug puntual en
  un fragmento de código acotado, la tasa de acierto es prácticamente
  perfecta en las pruebas realizadas.
- **Menos confiable con varios bugs distintos en una sola revisión.** En
  fragmentos con múltiples funciones y múltiples bugs sin ninguna pista de
  localización, el modelo tiende a detectar bien los bugs con una señal
  estructural clara (una condición invertida, un rango de loop mal puesto) y
  puede pasar por alto los que requieren razonar si una operación tiene
  sentido semánticamente (por ejemplo, sumar una tasa en vez de calcular un
  porcentaje). En pruebas repetidas sobre el mismo fragmento, la tasa de
  detección varió entre 25% y 100% de los bugs presentes.
- **Recomendación de uso:** para una revisión confiable, pega una función o
  un bug a la vez en "Corregir código", en vez de un archivo completo con
  varios problemas mezclados.
- Se probó también con un modelo más grande (`qwen2.5-coder:14b`) buscando
  mejorar esto, sin éxito -con cuantización de 4 bits, no superó al de 7B en
  estas mismas pruebas, y es notablemente más lento. Por eso se mantiene el
  7B como modelo por defecto.
- **"Generar código" es muy bueno en archivos autocontenidos, incluso
  complejos** (una API REST completa con Express, N-reinas por backtracking,
  el problema del viajante con programación dinámica, un servidor de chat
  con sockets TCP, cifrado AES con contraseña real vía PBKDF2) -verificado
  ejecutando el código de verdad en cada caso, no solo leyéndolo. Pero se le
  probaron 14 niveles de dificultad y aparecieron límites reales, cada uno
  de una naturaleza distinta:
  - **No repartía una tarea en varios archivos** (por ejemplo, una
    autenticación con config/modelo/rutas separados) -intentaba simularlo
    con comentarios dentro de un solo archivo, con un `return` a nivel
    superior que cortaba la ejecución o `require`/`import` a archivos que no
    existían. **Se corrigió** agregando una regla al prompt: ahora reconoce
    explícitamente que la tarea necesita varios archivos, dice cuáles son, y
    da a cada uno contenido real y compatible entre sí -verificado
    levantando un servidor Flask real con los dos archivos generados
    (registro, login y ruta protegida con JWT funcionando).
  - **Puede fallar en la lógica fina de algoritmos con roles que se
    alternan** (por ejemplo minimax en un juego de dos jugadores) -la
    función de la IA para "O" terminó evaluando la jugada como si fuera "X",
    y perdía contra un rival que jugara perfecto, pese a que el código corre
    sin errores. Se intentó corregir con una regla explícita y **no
    funcionó** -se confirmó con una simulación real que el bug persistía
    igual, byte por byte. Si generas este tipo de algoritmo, pruébalo
    jugando/ejecutando varios casos, no solo revisando que corra.
  - **Puede inventar una función o clase que no existe** en la librería que
    usa (por ejemplo `threading.Value`, que en realidad es de
    `multiprocessing`, no de `threading`). **Se corrigió** en dos vueltas:
    primero diciéndole que use `concurrent.futures.ThreadPoolExecutor` (la
    forma estándar de limitar hilos concurrentes en Python) en vez de contar
    hilos a mano, y luego siendo explícito con la línea exacta
    (`lock = threading.Lock()`) para el contador compartido. Verificado
    ejecutándolo de verdad: procesa las 10 tareas respetando el límite, y el
    contador llega exactamente a 10.
  - **Puede ignorar en silencio un requisito explícito de la descripción**
    (se le pidió cifrado "con una contraseña" y generó una clave aleatoria
    que no usaba ninguna contraseña). **Se corrigió** con una regla
    puntual -ahora deriva la clave con PBKDF2 a partir de la contraseña,
    verificado con un round-trip real que además rechaza correctamente una
    contraseña equivocada. Ojo: la primera versión de esta regla no
    especificaba la librería, y en la práctica el modelo a veces elegía
    `cryptography.fernet.Fernet` (con `Fernet.generate_key()`, otra vez sin
    contraseña) en vez de `pycryptodome` -tuvo que nombrarse explícitamente
    "usa pycryptodome, no Fernet.generate_key()" para que fuera consistente
    (confirmado 3/3 en corridas repetidas).
  - **Puede reutilizar el mismo nombre de variable para dos cosas
    distintas**, pisando un valor sin avisar (un diccionario de operadores
    sobrescrito por una lista, en un evaluador de expresiones). **Se
    corrigió** nombrando el algoritmo correcto explícitamente (descenso
    recursivo con una función por nivel de precedencia:
    `parse_factor`/`parse_termino`/`parse_suma`) en vez de solo decir qué
    no hacer -verificado con 7 casos, incluyendo asociatividad izquierda y
    paréntesis anidados, todos correctos.
  - **La protección contra path traversal no cubría rutas estilo Windows**
    (con `\` en vez de `/`). **Se corrigió** reemplazando las barras
    invertidas por barras normales antes de aplicar `basename()` -verificado
    contra 5 intentos de escape reales, incluido el de Windows que antes
    pasaba sin tocar.
  - **Un ejemplo de autenticación con Flask necesitó parches a mano**
    (faltaba crear las tablas de la base de datos, y el token JWT se creaba
    con un ID numérico cuando la librería actual exige texto). **Se
    corrigieron ambos** con reglas puntuales, confirmado con una API Flask
    real funcionando de extremo a extremo. Nota: en la regeneración de
    prueba, el modelo eligió una estructura de código distinta (un
    middleware con `before_request`) que introdujo un bug nuevo y no
    relacionado (`/protected` fallaba porque leía el usuario antes de que el
    token se verificara) -no se persiguió con una regla nueva, porque cada
    generación puede inventar una estructura distinta y no es viable cubrir
    cada variante posible. Los dos defectos puntuales que sí se apuntaron
    quedaron confirmados como arreglados.

  **Patrón general, confirmado varias veces:** una regla que le da al
  modelo un patrón o algoritmo correcto **concreto y nombrado** a seguir
  (usar PBKDF2, usar `ThreadPoolExecutor`, usar descenso recursivo con
  funciones por nivel de precedencia) funciona de forma confiable. Una
  regla que solo dice qué NO hacer, sin nombrar la alternativa correcta,
  tiende a evitar justo ese síntoma puntual pero deja la tarea de fondo
  igual de rota por otro camino -a veces uno más peligroso, porque falla en
  silencio en vez de con un error visible. La única excepción real
  encontrada es el bug del minimax (arriba): ni siquiera nombrando la
  regla correcta explícitamente se pudo arreglar, porque requiere que el
  modelo verifique su propio razonamiento sobre un algoritmo adversarial,
  no solo seguir un patrón conocido.

  **Nota sobre cómo verificar un arreglo:** una sola corrida exitosa no
  confirma que algo quedó arreglado -el caso de la contraseña pasó una
  vez y luego regresó al bug original en la siguiente corrida, porque el
  modelo a veces elegía una librería distinta (`Fernet` en vez de
  `pycryptodome`) que la regla no cubría todavía. Repetir la misma
  descripción 2-3 veces antes de dar algo por resuelto reveló esto -una
  corrida no es suficiente.

## Requisitos

- macOS
- Python 3.12+ (entorno virtual propio del proyecto en `.venv/`)
- [Ollama](https://ollama.com) con el modelo `qwen2.5-coder:7b` para usar DevAI

## Uso

```
cd DevBox
.venv/bin/python3 main.py
```

## Estructura

```
DevBox/
├── main.py
├── gui.py
└── core/
    ├── system.py           # detección de lenguajes/herramientas
    ├── project_analyzer.py # explorador de proyectos
    └── dev_ai.py            # integración con Ollama
```
