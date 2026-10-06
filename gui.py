import sys
import re
import threading
import ast
import tkinter
from pathlib import Path
from importlib import import_module
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

# Asegura que la raíz del proyecto esté disponible al ejecutar este
# archivo directamente, sin importar desde qué carpeta se invoque.
sys.path.insert(0, str(Path(__file__).resolve().parent))

_sistema = import_module("core.system")
detectar_todo = _sistema.detectar_todo
exportar_a_json = _sistema.exportar_a_json

_analizador = import_module("core.project_analyzer")
analizar_proyecto = _analizador.analizar_proyecto

_dev_ai = import_module("core.dev_ai")
chat_devai = _dev_ai.chat_devai
revisar_archivo = _dev_ai.revisar_archivo
generar_vista_previa = _dev_ai.generar_vista_previa
aplicar_correccion = _dev_ai.aplicar_correccion
extraer_bloque_codigo = _dev_ai.extraer_bloque_codigo
analizar_proyecto_con_ia = _dev_ai.analizar_proyecto_con_ia
esta_disponible_ia = _dev_ai.esta_disponible
listar_archivos_proyecto = _dev_ai.listar_archivos_proyecto
leer_contexto_codigo_proyecto = _dev_ai.leer_contexto_codigo_proyecto
OllamaNoDisponible = _dev_ai.OllamaNoDisponible


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --------------------------------------------------------------------
# Sistema de diseño: una sola paleta y set de tipografías para toda la
# app, en vez de colores sueltos repetidos por cada pantalla.
# --------------------------------------------------------------------

BG_VENTANA = "#0b0b0e"       # fondo del sidebar y de la ventana
BG_CONTENIDO = "#111114"     # fondo del área de contenido principal
BG_TARJETA = "#1b1b20"       # tarjetas/filas
BG_TARJETA_HOVER = "#232329"
BG_INPUT = "#17171b"         # cajas de texto, textboxes de solo lectura

ACCENT = "#2dd4bf"           # acento de marca (teal) -botones primarios, activo en sidebar
ACCENT_HOVER = "#25b3a1"

COLOR_INSTALADO = "#34d399"  # éxito/positivo
COLOR_FALTANTE = "#6b7280"   # neutral/ausente
COLOR_ERROR = "#f87171"      # peligro/error
COLOR_ADVERTENCIA = "#fbbf24"  # advertencia

BOTON_SECUNDARIO = "#232329"
BOTON_SECUNDARIO_HOVER = "#2c2c33"
BOTON_EXITO = "#34d399"
BOTON_EXITO_HOVER = "#2bb987"

TEXTO_PRIMARIO = "#f5f5f7"
TEXTO_SECUNDARIO = "#9ca3af"
TEXTO_TENUE = "#6b7280"

RADIO_TARJETA = 14
RADIO_BOTON = 10

# Ancho máximo (en caracteres) de una burbuja de mensaje del chat de
# DevAI -la del usuario más angosta que la del asistente, como en
# ChatGPT/iMessage.
ANCHO_BURBUJA_USUARIO = 52
ANCHO_BURBUJA_ASISTENTE = 72

FUENTE = "Helvetica Neue"


def fuente(tamano: int, peso: str = "normal") -> tuple:
    return (FUENTE, tamano, peso) if peso != "normal" else (FUENTE, tamano)


# --------------------------------------------------------------------
# Iconos reales (PNG), en vez de emojis, para el logo y el sidebar.
# --------------------------------------------------------------------

# Empaquetado con PyInstaller, __file__ ya no apunta a una ruta real
# del proyecto -en ese caso los datos empaquetados ("datas" del
# .spec) viven junto a sys._MEIPASS.
if getattr(sys, "frozen", False):
    _DIR_BASE_GUI = Path(sys._MEIPASS)
else:
    _DIR_BASE_GUI = Path(__file__).resolve().parent

_DIR_ICONOS = _DIR_BASE_GUI / "assets" / "icons"

ICONO_LOGO = str(_DIR_ICONOS / "logo_app.png")
ICONO_DASHBOARD = str(_DIR_ICONOS / "ui_dashboard.png")
ICONO_LENGUAJES = str(_DIR_ICONOS / "ui_lenguajes.png")
ICONO_PROYECTOS = str(_DIR_ICONOS / "ui_proyectos.png")
ICONO_DEVAI = str(_DIR_ICONOS / "ui_devai.png")

# Mismos iconos en tono oscuro, para cuando la sección está activa
# (fondo teal sólido) y el gris claro normal perdería contraste.
ICONO_DASHBOARD_ACTIVO = str(_DIR_ICONOS / "ui_dashboard_activo.png")
ICONO_LENGUAJES_ACTIVO = str(_DIR_ICONOS / "ui_lenguajes_activo.png")
ICONO_PROYECTOS_ACTIVO = str(_DIR_ICONOS / "ui_proyectos_activo.png")
ICONO_DEVAI_ACTIVO = str(_DIR_ICONOS / "ui_devai_activo.png")

ICONO_CHAT_USUARIO = str(_DIR_ICONOS / "chat_usuario.png")
ICONO_CHAT_ASISTENTE = str(_DIR_ICONOS / "chat_asistente.png")
ICONO_COPIAR = str(_DIR_ICONOS / "ui_copy.png")

_cache_iconos: dict[tuple[str, int], "ctk.CTkImage"] = {}


def cargar_icono(ruta: str | None, tamano: int = 20) -> "ctk.CTkImage | None":
    """Carga un PNG como CTkImage, cacheado por (ruta, tamaño)."""
    if not ruta:
        return None

    clave = (ruta, tamano)
    if clave in _cache_iconos:
        return _cache_iconos[clave]

    try:
        imagen = Image.open(ruta)
    except Exception:
        return None

    icono = ctk.CTkImage(light_image=imagen, dark_image=imagen, size=(tamano, tamano))
    _cache_iconos[clave] = icono
    return icono


# --------------------------------------------------------------------
# Resaltado de sintaxis básico para los bloques de código del chat,
# genérico entre lenguajes (no es un parser real por lenguaje, solo
# palabras clave + cadenas + comentarios + números vía regex).
# --------------------------------------------------------------------

PALABRAS_CLAVE_CODIGO = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "in", "is",
    "not", "and", "or", "import", "from", "as", "try", "except", "finally",
    "with", "lambda", "yield", "pass", "break", "continue", "global",
    "nonlocal", "assert", "del", "raise", "async", "await", "True", "False",
    "None", "self",
    "function", "const", "let", "var", "new", "this", "typeof", "instanceof",
    "export", "default", "extends", "implements", "interface", "public",
    "private", "protected", "static", "void", "int", "float", "double",
    "char", "bool", "string", "String", "fun", "val", "when", "switch",
    "case", "do", "null", "undefined", "struct", "enum", "namespace", "using",
}

_PATRON_TOKEN_CODIGO = re.compile(
    r"(?P<comentario>#.*$|//.*$)"
    r"|(?P<cadena>\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?'''|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"
    r"|(?P<numero>\b\d+\.?\d*\b)"
    r"|(?P<palabra>\b[A-Za-z_][A-Za-z0-9_]*\b)",
    re.MULTILINE,
)


class DevBoxApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("DevBox")
        self.geometry("980x640")
        self.minsize(760, 480)
        self.configure(fg_color=BG_VENTANA)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._ultimo_resultado: list = []
        self._ultimo_proyecto = None
        self._carpeta_devai = None
        self._info_aplicable = None
        self._ultimo_codigo_generado = None
        self._historial_chat: list = []
        self._ultima_respuesta_ia = None
        self._seccion_activa = None
        self._botones_sidebar: dict = {}

        self._crear_sidebar()
        self._crear_area_contenido()

        self._ir_a_seccion("dashboard", self.mostrar_dashboard)

    # ------------------------------------------------------------
    # Estructura general
    # ------------------------------------------------------------

    def _crear_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0, fg_color=BG_VENTANA)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_rowconfigure(10, weight=1)

        marca = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        marca.grid(row=0, column=0, padx=20, pady=(26, 34), sticky="w")

        badge_logo = ctk.CTkLabel(
            marca,
            text="",
            image=cargar_icono(ICONO_LOGO, 20),
            fg_color=ACCENT,
            corner_radius=10,
            width=36,
            height=36,
        )
        badge_logo.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            marca,
            text="DevBox",
            font=fuente(18, "bold"),
            text_color=TEXTO_PRIMARIO,
        ).pack(side="left")

        secciones = [
            ("dashboard", ICONO_DASHBOARD, ICONO_DASHBOARD_ACTIVO, "Dashboard", self.mostrar_dashboard),
            ("lenguajes", ICONO_LENGUAJES, ICONO_LENGUAJES_ACTIVO, "Lenguajes", self.mostrar_lenguajes),
            ("proyectos", ICONO_PROYECTOS, ICONO_PROYECTOS_ACTIVO, "Proyectos", self.mostrar_proyectos),
            ("devai", ICONO_DEVAI, ICONO_DEVAI_ACTIVO, "DevAI", self.mostrar_devai),
        ]

        for indice, (clave, icono, icono_activo, texto, accion) in enumerate(secciones, start=1):
            boton = ctk.CTkButton(
                self.sidebar,
                text=f"   {texto}",
                image=cargar_icono(icono, 16),
                compound="left",
                anchor="w",
                font=fuente(13),
                corner_radius=RADIO_BOTON,
                fg_color="transparent",
                hover_color=BG_TARJETA_HOVER,
                text_color=TEXTO_SECUNDARIO,
                command=lambda c=clave, a=accion: self._ir_a_seccion(c, a)
            )
            boton.grid(row=indice, column=0, padx=14, pady=3, sticky="ew")
            self._botones_sidebar[clave] = {
                "boton": boton,
                "icono": cargar_icono(icono, 16),
                "icono_activo": cargar_icono(icono_activo, 16),
            }

    def _ir_a_seccion(self, clave: str, accion):
        self._seccion_activa = clave

        for c, datos in self._botones_sidebar.items():
            if c == clave:
                datos["boton"].configure(
                    fg_color=ACCENT, text_color="#04211c", hover_color=ACCENT_HOVER,
                    image=datos["icono_activo"],
                )
            else:
                datos["boton"].configure(
                    fg_color="transparent", text_color=TEXTO_SECUNDARIO, hover_color=BG_TARJETA_HOVER,
                    image=datos["icono"],
                )

        accion()

    def _crear_area_contenido(self):
        self.contenido = ctk.CTkFrame(self, corner_radius=0, fg_color=BG_CONTENIDO)
        self.contenido.grid(row=0, column=1, sticky="nsew")
        self.contenido.grid_columnconfigure(0, weight=1)

    def _limpiar_contenido(self):
        for widget in self.contenido.winfo_children():
            widget.destroy()

    # ------------------------------------------------------------
    # Vista: Dashboard
    # ------------------------------------------------------------

    def mostrar_dashboard(self):
        self._limpiar_contenido()
        self._refrescar_deteccion()

        encabezado = ctk.CTkFrame(self.contenido, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=30, pady=(30, 0), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Bienvenido a DevBox",
            font=fuente(24, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            encabezado,
            text="📤  Exportar",
            width=110,
            fg_color=BOTON_SECUNDARIO,
            hover_color=BOTON_SECUNDARIO_HOVER,
            command=self._exportar_reporte
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            encabezado,
            text="🔄  Actualizar",
            width=120,
            corner_radius=RADIO_BOTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#04211c",
            command=self._actualizar_dashboard
        ).grid(row=0, column=2)

        fila_resumen = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_resumen.grid(row=1, column=0, padx=30, pady=(6, 4), sticky="ew")
        fila_resumen.grid_columnconfigure(0, weight=1)

        self.lbl_resumen = ctk.CTkLabel(
            fila_resumen,
            text=self._texto_resumen(),
            font=fuente(13),
            text_color=TEXTO_SECUNDARIO
        )
        self.lbl_resumen.grid(row=0, column=0, sticky="w")

        self.lbl_estado_copiado = ctk.CTkLabel(
            fila_resumen,
            text="",
            font=fuente(12),
            text_color=COLOR_INSTALADO
        )
        self.lbl_estado_copiado.grid(row=0, column=1, sticky="e")

        buscador = self._crear_buscador(self.contenido, self._filtrar_dashboard)
        buscador.grid(row=2, column=0, padx=30, pady=(0, 16), sticky="ew")

        self.panel_dashboard = ctk.CTkScrollableFrame(
            self.contenido, fg_color="transparent"
        )
        self.panel_dashboard.grid(row=3, column=0, padx=30, pady=(0, 20), sticky="nsew")
        self.panel_dashboard.grid_columnconfigure(0, weight=1)
        self.contenido.grid_rowconfigure(3, weight=1)

        self._dibujar_agrupado(self.panel_dashboard, self._ultimo_resultado)

    def _filtrar_dashboard(self, texto: str):
        self._dibujar_agrupado(self.panel_dashboard, self._ultimo_resultado, texto)

    def _refrescar_deteccion(self):
        self._ultimo_resultado = detectar_todo()

    def _texto_resumen(self) -> str:
        instalados = [r for r in self._ultimo_resultado if r.instalado]
        total = len(self._ultimo_resultado)
        return f"{len(instalados)} de {total} herramientas detectadas en este equipo"

    def _actualizar_dashboard(self):
        self._refrescar_deteccion()
        self.lbl_resumen.configure(text=self._texto_resumen())
        self._dibujar_agrupado(self.panel_dashboard, self._ultimo_resultado)

    def _exportar_reporte(self):
        if not self._ultimo_resultado:
            messagebox.showinfo("DevBox", "No hay datos para exportar todavía.")
            return

        ruta = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Archivo JSON", "*.json")],
            initialfile="devbox_reporte.json",
            title="Guardar reporte de DevBox"
        )

        if not ruta:
            return

        try:
            exportar_a_json(self._ultimo_resultado, ruta)
            messagebox.showinfo("DevBox", f"Reporte guardado en:\n{ruta}")

        except OSError as error:
            messagebox.showerror("DevBox", f"No se pudo guardar el reporte:\n{error}")

    def _fila_herramienta(self, contenedor, resultado):
        fila = ctk.CTkFrame(contenedor, fg_color=BG_TARJETA, corner_radius=RADIO_TARJETA)
        fila.pack(fill="x", pady=5)

        color = COLOR_INSTALADO if resultado.instalado else COLOR_FALTANTE

        barra = ctk.CTkFrame(fila, fg_color=color, width=4, height=40, corner_radius=2)
        barra.pack_propagate(False)
        barra.pack(side="left", padx=(0, 12), pady=10)

        icono = cargar_icono(resultado.icono, 22)
        ctk.CTkLabel(
            fila,
            text="" if icono else "🔧",
            image=icono,
            font=fuente(16)
        ).pack(side="left", padx=(0, 10), pady=12)

        ctk.CTkLabel(
            fila,
            text=resultado.nombre,
            font=fuente(13, "bold"),
            text_color=TEXTO_PRIMARIO
        ).pack(side="left", pady=12)

        if resultado.instalado and resultado.ruta:
            ctk.CTkButton(
                fila,
                text="📋",
                width=28,
                height=24,
                corner_radius=RADIO_BOTON,
                fg_color=BG_TARJETA_HOVER,
                hover_color=ACCENT,
                command=lambda r=resultado: self._copiar_ruta(r)
            ).pack(side="right", padx=(0, 15), pady=10)

        texto_derecha = resultado.version if resultado.instalado else "No instalado"
        color_derecha = TEXTO_SECUNDARIO if resultado.instalado else TEXTO_TENUE

        ctk.CTkLabel(
            fila,
            text=texto_derecha,
            fg_color=BG_TARJETA_HOVER,
            corner_radius=RADIO_BOTON,
            text_color=color_derecha,
            font=fuente(11, "bold"),
            width=90,
        ).pack(side="right", padx=(15, 10), pady=12, ipady=3)

    def _copiar_ruta(self, resultado):
        self.clipboard_clear()
        self.clipboard_append(resultado.ruta)
        self.lbl_estado_copiado.configure(
            text=f"Ruta de {resultado.nombre} copiada al portapapeles ✓"
        )
        self.after(2500, lambda: self.lbl_estado_copiado.configure(text=""))

    def _crear_buscador(self, contenedor, on_cambio):
        variable = ctk.StringVar()
        variable.trace_add("write", lambda *_: on_cambio(variable.get()))

        entrada = ctk.CTkEntry(
            contenedor,
            placeholder_text="🔍  Buscar por nombre...",
            textvariable=variable
        )
        return entrada

    def _dibujar_agrupado(self, contenedor, resultados, texto_filtro=""):
        for widget in contenedor.winfo_children():
            widget.destroy()

        filtro = texto_filtro.strip().lower()

        if filtro:
            resultados = [r for r in resultados if filtro in r.nombre.lower()]

        lenguajes = [r for r in resultados if r.categoria == "lenguaje"]
        herramientas = [r for r in resultados if r.categoria == "herramienta"]

        if lenguajes:
            ctk.CTkLabel(
                contenedor,
                text="LENGUAJES",
                font=fuente(11, "bold"),
                text_color=TEXTO_TENUE
            ).pack(anchor="w", pady=(4, 6))

            for resultado in lenguajes:
                self._fila_herramienta(contenedor, resultado)

        if herramientas:
            ctk.CTkLabel(
                contenedor,
                text="HERRAMIENTAS",
                font=fuente(11, "bold"),
                text_color=TEXTO_TENUE
            ).pack(anchor="w", pady=(16, 6))

            for resultado in herramientas:
                self._fila_herramienta(contenedor, resultado)

        if not lenguajes and not herramientas:
            ctk.CTkLabel(
                contenedor,
                text="Sin resultados para esa búsqueda.",
                text_color=TEXTO_TENUE
            ).pack(anchor="w", pady=20)

    # ------------------------------------------------------------
    # Vista: Lenguajes (detalle)
    # ------------------------------------------------------------

    def mostrar_lenguajes(self):
        self._limpiar_contenido()

        if not self._ultimo_resultado:
            self._refrescar_deteccion()

        encabezado = ctk.CTkFrame(self.contenido, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=30, pady=(30, 0), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Lenguajes de programación",
            font=fuente(24, "bold")
        ).grid(row=0, column=0, sticky="w")

        self.lbl_estado_copiado = ctk.CTkLabel(
            encabezado,
            text="",
            font=fuente(12),
            text_color=COLOR_INSTALADO
        )
        self.lbl_estado_copiado.grid(row=0, column=1, sticky="e")

        buscador = self._crear_buscador(self.contenido, self._filtrar_lenguajes)
        buscador.grid(row=1, column=0, padx=30, pady=(16, 16), sticky="ew")

        self.panel_lenguajes = ctk.CTkScrollableFrame(self.contenido, fg_color="transparent")
        self.panel_lenguajes.grid(row=2, column=0, padx=30, pady=(0, 20), sticky="nsew")
        self.panel_lenguajes.grid_columnconfigure(0, weight=1)
        self.contenido.grid_rowconfigure(2, weight=1)

        self._dibujar_lista_simple(
            self.panel_lenguajes,
            [r for r in self._ultimo_resultado if r.categoria == "lenguaje"]
        )

    def _filtrar_lenguajes(self, texto: str):
        resultados = [r for r in self._ultimo_resultado if r.categoria == "lenguaje"]
        filtro = texto.strip().lower()

        if filtro:
            resultados = [r for r in resultados if filtro in r.nombre.lower()]

        self._dibujar_lista_simple(self.panel_lenguajes, resultados)

    def _dibujar_lista_simple(self, contenedor, resultados):
        for widget in contenedor.winfo_children():
            widget.destroy()

        if not resultados:
            ctk.CTkLabel(
                contenedor,
                text="Sin resultados para esa búsqueda.",
                text_color=TEXTO_TENUE
            ).pack(anchor="w", pady=20)
            return

        for resultado in resultados:
            self._fila_herramienta(contenedor, resultado)

    # ------------------------------------------------------------
    # Vista: Proyectos (explorador)
    # ------------------------------------------------------------

    def mostrar_proyectos(self):
        self._limpiar_contenido()

        encabezado = ctk.CTkFrame(self.contenido, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=30, pady=(30, 0), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Explorador de proyectos",
            font=fuente(24, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            encabezado,
            text="📁  Seleccionar carpeta",
            width=180,
            corner_radius=RADIO_BOTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#04211c",
            command=self._elegir_carpeta_proyecto
        ).grid(row=0, column=1)

        self.panel_proyecto = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.panel_proyecto.grid(row=1, column=0, padx=30, pady=(20, 20), sticky="nsew")
        self.panel_proyecto.grid_columnconfigure(0, weight=1)
        self.contenido.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.panel_proyecto,
            text="Selecciona una carpeta de proyecto para analizarla.",
            text_color=TEXTO_SECUNDARIO,
            font=fuente(13)
        ).grid(row=0, column=0, sticky="w")

        self.caja_respuesta_ia_proyecto = None

    def _elegir_carpeta_proyecto(self):
        ruta = filedialog.askdirectory(title="Selecciona la carpeta del proyecto")

        if not ruta:
            return

        try:
            resultado = analizar_proyecto(ruta)
            self._ultimo_proyecto = resultado
            self._mostrar_resultado_proyecto(resultado)

        except Exception as error:
            messagebox.showerror("DevBox", f"No se pudo analizar el proyecto:\n{error}")

    def _mostrar_resultado_proyecto(self, resultado):
        for widget in self.panel_proyecto.winfo_children():
            widget.destroy()

        tarjeta = ctk.CTkFrame(self.panel_proyecto, fg_color=BG_TARJETA)
        tarjeta.grid(row=0, column=0, sticky="ew")
        tarjeta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tarjeta,
            text=resultado.ruta,
            font=fuente(12),
            text_color=TEXTO_SECUNDARIO
        ).grid(row=0, column=0, padx=20, pady=(18, 0), sticky="w")

        ctk.CTkLabel(
            tarjeta,
            text=f"Tipo detectado: {resultado.tipo}",
            font=fuente(17, "bold")
        ).grid(row=1, column=0, padx=20, pady=(4, 14), sticky="w")

        checks = [
            ("Archivos (sin dependencias)", str(resultado.total_archivos), True),
            ("README", "Sí" if resultado.tiene_readme else "No", resultado.tiene_readme),
            (".gitignore", "Sí" if resultado.tiene_gitignore else "No", resultado.tiene_gitignore),
            ("Control con Git", "Sí" if resultado.tiene_git else "No", resultado.tiene_git),
        ]

        for indice, (etiqueta, valor, positivo) in enumerate(checks, start=2):
            fila = ctk.CTkFrame(tarjeta, fg_color="transparent")
            fila.grid(row=indice, column=0, padx=20, pady=4, sticky="ew")
            fila.grid_columnconfigure(0, weight=1)

            color = COLOR_INSTALADO if positivo else COLOR_FALTANTE

            ctk.CTkLabel(fila, text=etiqueta, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                fila, text=valor, text_color=color, font=fuente(12, "bold")
            ).grid(row=0, column=1, sticky="e")

        if resultado.dependencias:
            ctk.CTkLabel(
                tarjeta,
                text=f"Dependencias detectadas ({len(resultado.dependencias)})",
                font=fuente(13, "bold")
            ).grid(row=10, column=0, padx=20, pady=(16, 4), sticky="w")

            texto_deps = ", ".join(resultado.dependencias)

            caja_deps = ctk.CTkTextbox(tarjeta, height=90, fg_color=BG_INPUT)
            caja_deps.grid(row=11, column=0, padx=20, pady=(0, 18), sticky="ew")
            caja_deps.insert("1.0", texto_deps)
            caja_deps.configure(state="disabled")
        else:
            ctk.CTkLabel(tarjeta, text="").grid(row=10, column=0, pady=(0, 18))

        boton_ia = ctk.CTkButton(
            self.panel_proyecto,
            text="🤖  Analizar con IA (local, Ollama)",
            corner_radius=RADIO_BOTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#04211c",
            command=self._analizar_proyecto_con_ia
        )
        boton_ia.grid(row=1, column=0, pady=(16, 0), sticky="w")

        self.panel_proyecto.grid_rowconfigure(2, weight=1)
        self.caja_respuesta_ia_proyecto = None

    def _analizar_proyecto_con_ia(self):
        if self._ultimo_proyecto is None:
            return

        if self.caja_respuesta_ia_proyecto is None:
            self.caja_respuesta_ia_proyecto = ctk.CTkTextbox(
                self.panel_proyecto, height=160, fg_color=BG_INPUT
            )
            self.caja_respuesta_ia_proyecto.grid(
                row=2, column=0, pady=(12, 0), sticky="nsew"
            )

        self.caja_respuesta_ia_proyecto.configure(state="normal")
        self.caja_respuesta_ia_proyecto.delete("1.0", "end")
        self.caja_respuesta_ia_proyecto.insert("1.0", "🤖 Pensando...")
        self.caja_respuesta_ia_proyecto.configure(state="disabled")

        info = {
            "tipo": self._ultimo_proyecto.tipo,
            "total_archivos": self._ultimo_proyecto.total_archivos,
            "tiene_readme": self._ultimo_proyecto.tiene_readme,
            "tiene_gitignore": self._ultimo_proyecto.tiene_gitignore,
            "tiene_git": self._ultimo_proyecto.tiene_git,
            "dependencias": self._ultimo_proyecto.dependencias,
        }

        def tarea():
            try:
                respuesta = analizar_proyecto_con_ia(info)
            except OllamaNoDisponible as error:
                respuesta = f"⚠️ {error}"

            self.after(0, lambda: self._mostrar_respuesta_ia_proyecto(respuesta))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_respuesta_ia_proyecto(self, texto: str):
        self.caja_respuesta_ia_proyecto.configure(state="normal")
        self.caja_respuesta_ia_proyecto.delete("1.0", "end")
        self.caja_respuesta_ia_proyecto.insert("1.0", texto)
        self.caja_respuesta_ia_proyecto.configure(state="disabled")

    # ------------------------------------------------------------
    # Vista: DevAI (analizador de errores)
    # ------------------------------------------------------------

    def mostrar_devai(self):
        self._limpiar_contenido()

        encabezado = ctk.CTkFrame(self.contenido, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=30, pady=(30, 0), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="DevAI",
            font=fuente(24, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            encabezado,
            text="🗑️ Nueva conversación",
            width=170,
            height=24,
            fg_color=BOTON_SECUNDARIO,
            hover_color=BOTON_SECUNDARIO_HOVER,
            command=self._nueva_conversacion_chat
        ).grid(row=0, column=1, padx=(0, 12))

        self.lbl_estado_ia = ctk.CTkLabel(
            encabezado,
            text="Revisando Ollama...",
            font=fuente(12),
            text_color=TEXTO_SECUNDARIO
        )
        self.lbl_estado_ia.grid(row=0, column=2, sticky="e")

        fila_carpeta = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_carpeta.grid(row=1, column=0, padx=30, pady=(10, 10), sticky="ew")
        fila_carpeta.grid_columnconfigure(0, weight=1)

        texto_carpeta = self._carpeta_devai or "Ninguna carpeta seleccionada (opcional, pero mejora el diagnóstico)"

        self.lbl_carpeta_devai = ctk.CTkLabel(
            fila_carpeta,
            text=f"📁 {texto_carpeta}",
            font=fuente(12),
            text_color=TEXTO_SECUNDARIO
        )
        self.lbl_carpeta_devai.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            fila_carpeta,
            text="Elegir carpeta del proyecto",
            width=190,
            fg_color=BOTON_SECUNDARIO,
            hover_color=BOTON_SECUNDARIO_HOVER,
            command=self._elegir_carpeta_devai
        ).grid(row=0, column=1)

        self.panel_chat = ctk.CTkScrollableFrame(self.contenido, fg_color=BG_INPUT)
        self.panel_chat.grid(row=2, column=0, padx=30, pady=(0, 10), sticky="nsew")
        self.contenido.grid_rowconfigure(2, weight=1)

        self.lbl_placeholder_chat = None
        self._fila_pensando = None

        for turno in self._historial_chat:
            self._agregar_mensaje_chat(
                "usuario" if turno["role"] == "user" else "asistente",
                turno["content"]
            )

        if not self._historial_chat:
            self._mostrar_placeholder_chat()

        fila_entrada = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_entrada.grid(row=3, column=0, padx=30, pady=(0, 10), sticky="ew")
        fila_entrada.grid_columnconfigure(1, weight=1)

        self.btn_adjuntar_archivo = ctk.CTkButton(
            fila_entrada,
            text="📎",
            width=40,
            fg_color=BOTON_SECUNDARIO,
            hover_color=BOTON_SECUNDARIO_HOVER,
            command=self._adjuntar_archivo_chat
        )
        self.btn_adjuntar_archivo.grid(row=0, column=0, padx=(0, 8))

        self.caja_mensaje = ctk.CTkTextbox(fila_entrada, height=64)
        self.caja_mensaje.grid(row=0, column=1, sticky="ew")
        self.caja_mensaje.bind("<Return>", self._al_presionar_enter)

        self.btn_enviar = ctk.CTkButton(
            fila_entrada,
            text="Enviar ➤",
            width=90,
            corner_radius=RADIO_BOTON,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#04211c",
            command=self._enviar_mensaje_chat
        )
        self.btn_enviar.grid(row=0, column=2, padx=(8, 0))

        fila_acciones = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_acciones.grid(row=4, column=0, padx=30, pady=(0, 20), sticky="w")

        self.btn_aplicar_correccion = ctk.CTkButton(
            fila_acciones,
            text="✅  Aplicar corrección al archivo",
            fg_color=BOTON_EXITO,
            hover_color=BOTON_EXITO_HOVER,
            text_color="#04211c",
            command=self._aplicar_correccion_al_archivo
        )
        self.btn_aplicar_correccion.grid(row=0, column=0, padx=(0, 8))
        self.btn_aplicar_correccion.grid_remove()

        self.btn_guardar_codigo_generado = ctk.CTkButton(
            fila_acciones,
            text="💾  Guardar código como archivo",
            fg_color=BOTON_EXITO,
            hover_color=BOTON_EXITO_HOVER,
            text_color="#04211c",
            command=self._guardar_codigo_generado
        )
        self.btn_guardar_codigo_generado.grid(row=0, column=1)
        self.btn_guardar_codigo_generado.grid_remove()

        threading.Thread(target=self._revisar_estado_ollama, daemon=True).start()

    def _elegir_carpeta_devai(self):
        ruta = filedialog.askdirectory(
            title="Selecciona la carpeta del proyecto (opcional)"
        )

        if not ruta:
            return

        self._carpeta_devai = ruta
        self.lbl_carpeta_devai.configure(text=f"📁 {ruta}")

    def _revisar_estado_ollama(self):
        disponible = esta_disponible_ia()
        texto = "🟢 Ollama conectado" if disponible else "🔴 Ollama no detectado"
        self.after(0, lambda: self.lbl_estado_ia.configure(text=texto))

    def _nueva_conversacion_chat(self):
        self._historial_chat = []
        self._info_aplicable = None
        self._ultimo_codigo_generado = None
        self._ultima_respuesta_ia = None
        self._ocultar_boton_aplicar()
        self.btn_guardar_codigo_generado.grid_remove()

        for widget in self.panel_chat.winfo_children():
            widget.destroy()

        # Resetea el scrollregion de inmediato (no solo de forma
        # diferida) antes de agregar el placeholder: sin esto, un
        # scrollregion inflado que quedó de una conversación larga con
        # bloques de código (cuyos widgets embebidos no liberan su
        # espacio en el canvas de inmediato al destruirse) puede dejar
        # el placeholder nuevo sin mapear igual que le pasaba a los
        # mensajes.
        canvas = self.panel_chat._parent_canvas
        canvas.configure(scrollregion=(0, 0, 0, 0))

        self.lbl_placeholder_chat = None
        self._fila_pensando = None
        self._mostrar_placeholder_chat()

    def _mostrar_placeholder_chat(self):
        self.lbl_placeholder_chat = ctk.CTkLabel(
            self.panel_chat,
            text="Escríbele a DevAI: pega un error, pega código para corregir, "
                 "o describe qué código quieres que genere. También puedes "
                 "adjuntar un archivo completo para revisar su sintaxis.",
            font=fuente(13),
            text_color=TEXTO_SECUNDARIO,
            justify="left",
            wraplength=520,
        )
        self.lbl_placeholder_chat.pack(anchor="w", padx=10, pady=10)
        self._refrescar_scroll_chat(al_fondo=False)

    def _al_presionar_enter(self, evento):
        if evento.state & 0x1:  # Shift+Enter -> salto de línea normal
            return None
        self._enviar_mensaje_chat()
        return "break"

    def _agregar_mensaje_chat(self, remitente: str, texto: str):
        """Agrega un mensaje como una burbuja de chat de verdad -icono,
        nombre y contenido en su propia tarjeta redondeada, alineada a
        la derecha (usuario) o izquierda (DevAI), como en
        ChatGPT/iMessage- en vez de texto plano en un cuadro
        compartido. Devuelve el frame de la fila, para poder quitarlo
        después (usado por el indicador de 'Pensando...')."""
        if self.lbl_placeholder_chat is not None:
            self.lbl_placeholder_chat.destroy()
            self.lbl_placeholder_chat = None

        es_usuario = remitente == "usuario"
        color_burbuja = BG_TARJETA_HOVER if es_usuario else BG_TARJETA
        color_nombre = "#7db8ff" if es_usuario else "#8fd48f"
        icono_nombre = ICONO_CHAT_USUARIO if es_usuario else ICONO_CHAT_ASISTENTE
        nombre = "Tú" if es_usuario else "DevAI"
        ancho_burbuja = ANCHO_BURBUJA_USUARIO if es_usuario else ANCHO_BURBUJA_ASISTENTE

        fila = ctk.CTkFrame(self.panel_chat, fg_color="transparent")
        fila.pack(fill="x", pady=5)

        burbuja = ctk.CTkFrame(fila, fg_color=color_burbuja, corner_radius=RADIO_TARJETA)
        burbuja.pack(anchor="e" if es_usuario else "w")

        encabezado = ctk.CTkFrame(burbuja, fg_color="transparent")
        encabezado.pack(anchor="w", padx=12, pady=(10, 0))

        ctk.CTkLabel(
            encabezado,
            image=cargar_icono(icono_nombre, 14),
            text=f" {nombre}",
            compound="left",
            font=fuente(11, "bold"),
            text_color=color_nombre,
        ).pack(side="left")

        caja_texto = tkinter.Text(
            burbuja, wrap="word", width=ancho_burbuja, borderwidth=0,
            highlightthickness=0, bg=color_burbuja, fg=TEXTO_PRIMARIO,
            padx=12, pady=6, font=fuente(13),
        )
        caja_texto.pack()
        caja_texto.update_idletasks()

        self._configurar_tags_mensaje(caja_texto)
        self._insertar_texto_markdown(caja_texto, texto)

        caja_texto.update_idletasks()
        conteo = caja_texto.count("1.0", "end-1c", "displaylines")
        lineas_mostradas = conteo[0] if conteo else 1
        caja_texto.configure(height=max(lineas_mostradas, 1))
        caja_texto.configure(state="disabled")

        self._refrescar_scroll_chat(al_fondo=True)
        return fila

    def _refrescar_scroll_chat(self, al_fondo: bool):
        """CTkScrollableFrame solo recalcula la región de scroll de su
        canvas interno cuando le llega un evento <Configure> real. Ese
        evento no siempre se despacha a tiempo cuando el contenido del
        chat cambia más de una vez seguida sin ceder al event loop
        entre un cambio y otro (agregar el mensaje del usuario y el de
        "Pensando..." en la misma llamada, o destruir todo y mostrar
        el placeholder en 'Nueva conversación'). Si en ese estado se
        llama yview_moveto(1.0) contra un scrollregion que todavía no
        refleja el contenido real, el canvas termina colocando el
        frame interno en una posición inválida (offset negativo) y
        sus hijos quedan sin mapear -invisibles, aunque su geometría
        se calcule bien. Por eso las correcciones van juntas, en una
        sola llamada diferida y en este orden estricto: primero
        recalcular el scrollregion, y solo entonces (si aplica) bajar
        el scroll."""
        canvas = self.panel_chat._parent_canvas

        def _corregir():
            canvas.configure(scrollregion=canvas.bbox("all"))
            if al_fondo:
                canvas.yview_moveto(1.0)

        self.after(30, _corregir)

    def _deshabilitar_entrada_chat(self):
        self.btn_enviar.configure(state="disabled")
        self.btn_adjuntar_archivo.configure(state="disabled")
        self.caja_mensaje.configure(state="disabled")
        self._ocultar_boton_aplicar()
        self.btn_guardar_codigo_generado.grid_remove()
        self._fila_pensando = self._agregar_mensaje_chat("asistente", "Pensando...")

    def _habilitar_entrada_chat(self):
        self.btn_enviar.configure(state="normal")
        self.btn_adjuntar_archivo.configure(state="normal")
        self.caja_mensaje.configure(state="normal")
        self.caja_mensaje.focus()

    def _configurar_tags_mensaje(self, caja_texto: "tkinter.Text"):
        caja_texto.tag_config("normal", foreground=TEXTO_PRIMARIO, font=fuente(13))
        caja_texto.tag_config("negrita", foreground=TEXTO_PRIMARIO, font=fuente(13, "bold"))
        caja_texto.tag_config("encabezado1", foreground=TEXTO_PRIMARIO, font=fuente(16, "bold"), spacing1=6)
        caja_texto.tag_config("encabezado2", foreground=TEXTO_PRIMARIO, font=fuente(14, "bold"), spacing1=4)
        caja_texto.tag_config("codigo_inline", foreground=ACCENT, font=("Menlo", 12))

    def _insertar_texto_markdown(self, caja_texto: "tkinter.Text", texto: str):
        """Muestra un mensaje del chat interpretando el markdown básico
        que usa el modelo (encabezados #, **negritas**, `código` y
        bloques ```), en vez de mostrar los símbolos tal cual como
        texto plano. Los bloques ``` se muestran como en ChatGPT: con
        una barra de lenguaje + botón de copiar y resaltado de sintaxis."""
        lineas = texto.split("\n")
        en_bloque_codigo = False
        lineas_bloque: list[str] = []
        lenguaje_bloque = ""

        for indice, linea in enumerate(lineas):
            salto = "" if indice == len(lineas) - 1 else "\n"

            coincidencia_valla = re.match(r"^```(\S*)", linea.strip())
            if coincidencia_valla:
                if not en_bloque_codigo:
                    en_bloque_codigo = True
                    lenguaje_bloque = coincidencia_valla.group(1)
                    lineas_bloque = []
                else:
                    en_bloque_codigo = False
                    self._insertar_bloque_codigo(caja_texto, "\n".join(lineas_bloque), lenguaje_bloque)
                continue

            if en_bloque_codigo:
                lineas_bloque.append(linea)
                continue

            encabezado = re.match(r"^(#{1,6})\s+(.*)", linea)
            if encabezado:
                nivel = len(encabezado.group(1))
                tag_encabezado = "encabezado1" if nivel <= 2 else "encabezado2"
                self._insertar_linea_con_estilos(caja_texto, encabezado.group(2), tag_encabezado)
                caja_texto.insert("end", salto)
                continue

            self._insertar_linea_con_estilos(caja_texto, linea, "normal")
            caja_texto.insert("end", salto)

        # Si el mensaje terminó de escribirse (o se cortó) sin cerrar
        # el ``` final, igual mostramos lo que alcanzó a llegar.
        if en_bloque_codigo and lineas_bloque:
            self._insertar_bloque_codigo(caja_texto, "\n".join(lineas_bloque), lenguaje_bloque)

    def _insertar_linea_con_estilos(self, caja_texto: "tkinter.Text", linea: str, tag_base: str):
        """Dentro de una sola línea, alterna entre texto normal,
        **negritas** y `código inline`, cada trozo con su propio tag."""
        tag_negrita = "negrita" if tag_base == "normal" else tag_base

        for trozo in re.split(r"(\*\*.+?\*\*|`.+?`)", linea):
            if not trozo:
                continue
            if trozo.startswith("**") and trozo.endswith("**"):
                caja_texto.insert("end", trozo[2:-2], tag_negrita)
            elif trozo.startswith("`") and trozo.endswith("`"):
                caja_texto.insert("end", trozo[1:-1], "codigo_inline")
            else:
                caja_texto.insert("end", trozo, tag_base)

    def _insertar_bloque_codigo(self, caja_texto: "tkinter.Text", codigo: str, lenguaje: str):
        """Inserta un bloque ``` como un widget aparte embebido dentro
        de la burbuja del mensaje: barra superior con el lenguaje +
        botón de copiar, y el código con resaltado de sintaxis, igual
        que en ChatGPT. Un tono más oscuro que la burbuja que lo
        contiene, para que se note como un elemento aparte."""
        codigo = codigo.strip("\n")
        if not codigo:
            return

        lineas_codigo = codigo.split("\n")
        ancho_disponible = max(caja_texto.winfo_width() - 24, 260)
        alto_codigo = len(lineas_codigo) * 17 + 16
        alto_total = 26 + alto_codigo

        contenedor = ctk.CTkFrame(
            caja_texto, fg_color=BG_INPUT, corner_radius=RADIO_BOTON,
            width=ancho_disponible, height=alto_total,
        )
        contenedor.pack_propagate(False)

        barra = ctk.CTkFrame(contenedor, fg_color=BG_TARJETA, corner_radius=0, height=26)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        ctk.CTkLabel(
            barra, text=lenguaje or "código", font=fuente(11), text_color=TEXTO_SECUNDARIO
        ).pack(side="left", padx=10)

        boton_copiar = ctk.CTkButton(
            barra, text="Copiar", image=cargar_icono(ICONO_COPIAR, 12), compound="left",
            width=64, height=20, corner_radius=6, font=fuente(11),
            fg_color="transparent", hover_color=BG_TARJETA_HOVER, text_color=TEXTO_SECUNDARIO,
            command=lambda c=codigo: self._copiar_codigo_bloque(c),
        )
        boton_copiar.pack(side="right", padx=6, pady=3)

        caja_codigo = tkinter.Text(
            contenedor, bg=BG_INPUT, fg="#d4d4d8", insertbackground="#d4d4d8",
            font=("Menlo", 12), wrap="none", borderwidth=0, highlightthickness=0,
            padx=12, pady=8,
        )
        caja_codigo.pack(fill="both", expand=True)
        self._configurar_tags_codigo(caja_codigo)
        self._insertar_codigo_resaltado(caja_codigo, codigo)
        caja_codigo.configure(state="disabled")

        caja_texto.window_create("end", window=contenedor)
        caja_texto.insert("end", "\n")

    def _configurar_tags_codigo(self, caja_codigo: "tkinter.Text"):
        caja_codigo.tag_config("codigo_palabra_clave", foreground="#c586c0")
        caja_codigo.tag_config("codigo_cadena", foreground="#ce9178")
        caja_codigo.tag_config("codigo_numero", foreground="#b5cea8")
        caja_codigo.tag_config("codigo_comentario", foreground="#6a9955", font=("Menlo", 12, "italic"))

    def _insertar_codigo_resaltado(self, caja_codigo: "tkinter.Text", codigo: str):
        posicion = 0
        for coincidencia in _PATRON_TOKEN_CODIGO.finditer(codigo):
            inicio, fin = coincidencia.span()
            if inicio > posicion:
                caja_codigo.insert("end", codigo[posicion:inicio])

            grupo = coincidencia.lastgroup
            token = coincidencia.group()

            if grupo == "palabra" and token not in PALABRAS_CLAVE_CODIGO:
                caja_codigo.insert("end", token)
            else:
                tag = {
                    "comentario": "codigo_comentario",
                    "cadena": "codigo_cadena",
                    "numero": "codigo_numero",
                    "palabra": "codigo_palabra_clave",
                }[grupo]
                caja_codigo.insert("end", token, tag)

            posicion = fin

        if posicion < len(codigo):
            caja_codigo.insert("end", codigo[posicion:])

    def _copiar_codigo_bloque(self, codigo: str):
        self.clipboard_clear()
        self.clipboard_append(codigo)

    def _reemplazar_indicador_pensando(self, texto: str):
        if self._fila_pensando is not None:
            self._fila_pensando.destroy()
            self._fila_pensando = None
        self._agregar_mensaje_chat("asistente", texto)

    def _enviar_mensaje_chat(self):
        texto = self.caja_mensaje.get("1.0", "end").strip()

        if not texto:
            return

        self.caja_mensaje.delete("1.0", "end")
        self._agregar_mensaje_chat("usuario", texto)
        self._historial_chat.append({"role": "user", "content": texto})

        self._deshabilitar_entrada_chat()

        carpeta = self._carpeta_devai
        historial_copia = list(self._historial_chat)

        def tarea():
            try:
                archivos = listar_archivos_proyecto(carpeta) if carpeta else None
                contexto_codigo = (
                    leer_contexto_codigo_proyecto(carpeta, archivos)
                    if carpeta and archivos else ""
                )
                respuesta = chat_devai(
                    historial_copia, archivos_proyecto=archivos, contexto_codigo=contexto_codigo
                )
            except OllamaNoDisponible as error:
                respuesta = f"⚠️ {error}"

            self.after(0, lambda: self._recibir_respuesta_chat(respuesta))

        threading.Thread(target=tarea, daemon=True).start()

    def _recibir_respuesta_chat(self, texto: str):
        self._historial_chat.append({"role": "assistant", "content": texto})
        self._reemplazar_indicador_pensando(texto)
        self._ultima_respuesta_ia = texto
        self._habilitar_entrada_chat()

        # "Aplicar corrección al archivo" solo aplica al resultado de
        # adjuntar un archivo (ahí sí sabemos el rango exacto de
        # líneas a reemplazar) -una corrección sugerida en el chat
        # libre se copia a mano, no se escribe sola a un archivo.
        self._info_aplicable = None
        self._ocultar_boton_aplicar()

        self._ultimo_codigo_generado = extraer_bloque_codigo(texto)

        if self._ultimo_codigo_generado is not None:
            self.btn_guardar_codigo_generado.grid()
        else:
            self.btn_guardar_codigo_generado.grid_remove()

    def _guardar_codigo_generado(self):
        if not self._ultimo_codigo_generado:
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar código como...",
            filetypes=[("Todos los archivos", "*.*")]
        )

        if not ruta:
            return

        try:
            Path(ruta).write_text(self._ultimo_codigo_generado + "\n", encoding="utf-8")
        except OSError as error:
            messagebox.showerror("DevBox", f"No se pudo guardar el archivo:\n{error}")
            return

        messagebox.showinfo("DevBox", f"Archivo guardado en:\n{ruta}")

    def _adjuntar_archivo_chat(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el archivo a revisar",
            filetypes=[
                ("Archivos de código", "*.py *.js *.ts *.java *.go *.rs *.php *.rb *.pl *.pm *.c *.cpp *.cc *.cxx"),
                ("Todos los archivos", "*.*"),
            ]
        )

        if not ruta:
            return

        try:
            contenido = Path(ruta).read_text(encoding="utf-8")
        except OSError as error:
            messagebox.showerror("DevBox", f"No se pudo leer el archivo:\n{error}")
            return

        nombre = Path(ruta).name

        self._agregar_mensaje_chat("usuario", f"📎 Adjuntó '{nombre}' para revisar su sintaxis.")
        self._historial_chat.append({
            "role": "user",
            "content": f"(Adjunté el archivo '{nombre}' para que revises su sintaxis.)"
        })

        self._deshabilitar_entrada_chat()
        self._info_aplicable = None

        def tarea():
            try:
                texto, info_aplicable = revisar_archivo(
                    nombre, contenido, ruta_completa=ruta
                )
            except OllamaNoDisponible as error:
                texto, info_aplicable = f"⚠️ {error}", None

            self.after(0, lambda: self._recibir_respuesta_archivo(texto, info_aplicable))

        threading.Thread(target=tarea, daemon=True).start()

    def _recibir_respuesta_archivo(self, texto: str, info_aplicable: dict | None):
        self._historial_chat.append({"role": "assistant", "content": texto})
        self._reemplazar_indicador_pensando(texto)
        self._ultima_respuesta_ia = texto
        self._habilitar_entrada_chat()

        self._info_aplicable = info_aplicable

        if info_aplicable is not None:
            self.btn_aplicar_correccion.grid()
        else:
            self._ocultar_boton_aplicar()

        self._ultimo_codigo_generado = extraer_bloque_codigo(texto)

        if self._ultimo_codigo_generado is not None:
            self.btn_guardar_codigo_generado.grid()
        else:
            self.btn_guardar_codigo_generado.grid_remove()

    def _ocultar_boton_aplicar(self):
        if getattr(self, "btn_aplicar_correccion", None) is not None:
            self.btn_aplicar_correccion.grid_remove()

    def _aplicar_correccion_al_archivo(self):
        if not self._info_aplicable or not self._ultima_respuesta_ia:
            return

        ok, vista_previa = generar_vista_previa(self._info_aplicable, self._ultima_respuesta_ia)

        if not ok:
            messagebox.showerror("DevBox", f"No se puede aplicar:\n{vista_previa}")
            return

        self._mostrar_dialogo_vista_previa(vista_previa, self._ultima_respuesta_ia)

    def _mostrar_dialogo_vista_previa(self, vista_previa: str, texto_respuesta: str):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar corrección")
        dialogo.geometry("640x480")
        dialogo.transient(self)
        dialogo.grab_set()

        ctk.CTkLabel(
            dialogo,
            text="Revisa exactamente qué va a cambiar antes de aplicar:",
            font=fuente(13, "bold")
        ).pack(padx=16, pady=(16, 8), anchor="w")

        caja = ctk.CTkTextbox(dialogo, fg_color=BG_INPUT)
        caja.pack(padx=16, pady=(0, 12), fill="both", expand=True)
        caja.insert("1.0", vista_previa)
        caja.configure(state="disabled")

        fila_botones = ctk.CTkFrame(dialogo, fg_color="transparent")
        fila_botones.pack(padx=16, pady=(0, 16), anchor="e")

        def confirmar():
            dialogo.destroy()
            exito, mensaje = aplicar_correccion(self._info_aplicable, texto_respuesta)

            if exito:
                messagebox.showinfo("DevBox", mensaje)
                self._ocultar_boton_aplicar()
            else:
                messagebox.showerror("DevBox", f"No se pudo aplicar la corrección:\n{mensaje}")

        ctk.CTkButton(
            fila_botones, text="Cancelar", fg_color=BOTON_SECUNDARIO,
            hover_color=BOTON_SECUNDARIO_HOVER, command=dialogo.destroy
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            fila_botones, text="✅  Aplicar de todas formas",
            fg_color=BOTON_EXITO, hover_color=BOTON_EXITO_HOVER, text_color="#04211c", command=confirmar
        ).pack(side="left")


if __name__ == "__main__":
    app = DevBoxApp()
    app.mainloop()
