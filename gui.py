import sys
import threading
import ast
from pathlib import Path
from importlib import import_module
from tkinter import filedialog, messagebox

import customtkinter as ctk

# Asegura que la raíz del proyecto esté disponible al ejecutar este
# archivo directamente, sin importar desde qué carpeta se invoque.
sys.path.insert(0, str(Path(__file__).resolve().parent))

_sistema = import_module("core.system")
detectar_todo = _sistema.detectar_todo
exportar_a_json = _sistema.exportar_a_json

_analizador = import_module("core.project_analyzer")
analizar_proyecto = _analizador.analizar_proyecto

_dev_ai = import_module("core.dev_ai")
explicar_error = _dev_ai.explicar_error
generar_codigo = _dev_ai.generar_codigo
corregir_codigo = _dev_ai.corregir_codigo
revisar_archivo = _dev_ai.revisar_archivo
generar_vista_previa = _dev_ai.generar_vista_previa
aplicar_correccion = _dev_ai.aplicar_correccion
extraer_bloque_codigo = _dev_ai.extraer_bloque_codigo
analizar_proyecto_con_ia = _dev_ai.analizar_proyecto_con_ia
esta_disponible_ia = _dev_ai.esta_disponible
listar_archivos_proyecto = _dev_ai.listar_archivos_proyecto
OllamaNoDisponible = _dev_ai.OllamaNoDisponible


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_INSTALADO = "#2ecc71"
COLOR_FALTANTE = "#7f8c8d"


class DevBoxApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("DevBox")
        self.geometry("900x600")
        self.minsize(760, 480)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._ultimo_resultado: list = []
        self._ultimo_proyecto = None
        self._carpeta_devai = None
        self._info_aplicable = None
        self._ruta_codigo_cargado = None
        self._ultimo_codigo_generado = None

        self._crear_sidebar()
        self._crear_area_contenido()

        self.mostrar_dashboard()

    # ------------------------------------------------------------
    # Estructura general
    # ------------------------------------------------------------

    def _crear_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="🧰 DevBox",
            font=("Segoe UI", 20, "bold")
        ).grid(row=0, column=0, padx=20, pady=(24, 30), sticky="w")

        botones = [
            ("🏠  Dashboard", self.mostrar_dashboard),
            ("💻  Lenguajes", self.mostrar_lenguajes),
            ("📁  Proyectos", self.mostrar_proyectos),
            ("🤖  DevAI", self.mostrar_devai),
        ]

        for indice, (texto, accion) in enumerate(botones, start=1):
            boton = ctk.CTkButton(
                self.sidebar,
                text=texto,
                anchor="w",
                fg_color="transparent",
                hover_color="#2b2b2b",
                command=accion
            )
            boton.grid(row=indice, column=0, padx=12, pady=4, sticky="ew")

    def _crear_area_contenido(self):
        self.contenido = ctk.CTkFrame(self, corner_radius=0)
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
            font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            encabezado,
            text="📤  Exportar",
            width=110,
            fg_color="#333333",
            hover_color="#444444",
            command=self._exportar_reporte
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            encabezado,
            text="🔄  Actualizar",
            width=120,
            command=self._actualizar_dashboard
        ).grid(row=0, column=2)

        fila_resumen = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_resumen.grid(row=1, column=0, padx=30, pady=(6, 4), sticky="ew")
        fila_resumen.grid_columnconfigure(0, weight=1)

        self.lbl_resumen = ctk.CTkLabel(
            fila_resumen,
            text=self._texto_resumen(),
            font=("Segoe UI", 13),
            text_color="#a0a0a0"
        )
        self.lbl_resumen.grid(row=0, column=0, sticky="w")

        self.lbl_estado_copiado = ctk.CTkLabel(
            fila_resumen,
            text="",
            font=("Segoe UI", 12),
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
        fila = ctk.CTkFrame(contenedor, fg_color="#242424")
        fila.pack(fill="x", pady=4)

        color = COLOR_INSTALADO if resultado.instalado else COLOR_FALTANTE
        punto = "●" if resultado.instalado else "○"

        ctk.CTkLabel(
            fila,
            text=punto,
            text_color=color,
            font=("Segoe UI", 14)
        ).pack(side="left", padx=(15, 6), pady=10)

        ctk.CTkLabel(
            fila,
            text=resultado.icono,
            font=("Segoe UI", 15)
        ).pack(side="left", padx=(0, 8), pady=10)

        ctk.CTkLabel(
            fila,
            text=resultado.nombre,
            font=("Segoe UI", 13, "bold")
        ).pack(side="left", pady=10)

        if resultado.instalado and resultado.ruta:
            ctk.CTkButton(
                fila,
                text="📋",
                width=28,
                height=24,
                fg_color="#333333",
                hover_color="#444444",
                command=lambda r=resultado: self._copiar_ruta(r)
            ).pack(side="right", padx=(0, 15), pady=10)

        texto_derecha = resultado.version if resultado.instalado else "No instalado"

        ctk.CTkLabel(
            fila,
            text=texto_derecha,
            text_color="#a0a0a0",
            font=("Segoe UI", 12)
        ).pack(side="right", padx=(15, 8), pady=10)

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
                font=("Segoe UI", 11, "bold"),
                text_color="#707070"
            ).pack(anchor="w", pady=(4, 6))

            for resultado in lenguajes:
                self._fila_herramienta(contenedor, resultado)

        if herramientas:
            ctk.CTkLabel(
                contenedor,
                text="HERRAMIENTAS",
                font=("Segoe UI", 11, "bold"),
                text_color="#707070"
            ).pack(anchor="w", pady=(16, 6))

            for resultado in herramientas:
                self._fila_herramienta(contenedor, resultado)

        if not lenguajes and not herramientas:
            ctk.CTkLabel(
                contenedor,
                text="Sin resultados para esa búsqueda.",
                text_color="#707070"
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
            font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, sticky="w")

        self.lbl_estado_copiado = ctk.CTkLabel(
            encabezado,
            text="",
            font=("Segoe UI", 12),
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
                text_color="#707070"
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
            font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            encabezado,
            text="📁  Seleccionar carpeta",
            width=180,
            command=self._elegir_carpeta_proyecto
        ).grid(row=0, column=1)

        self.panel_proyecto = ctk.CTkFrame(self.contenido, fg_color="transparent")
        self.panel_proyecto.grid(row=1, column=0, padx=30, pady=(20, 20), sticky="nsew")
        self.panel_proyecto.grid_columnconfigure(0, weight=1)
        self.contenido.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.panel_proyecto,
            text="Selecciona una carpeta de proyecto para analizarla.",
            text_color="#a0a0a0",
            font=("Segoe UI", 13)
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

        tarjeta = ctk.CTkFrame(self.panel_proyecto, fg_color="#242424")
        tarjeta.grid(row=0, column=0, sticky="ew")
        tarjeta.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tarjeta,
            text=resultado.ruta,
            font=("Segoe UI", 12),
            text_color="#a0a0a0"
        ).grid(row=0, column=0, padx=20, pady=(18, 0), sticky="w")

        ctk.CTkLabel(
            tarjeta,
            text=f"Tipo detectado: {resultado.tipo}",
            font=("Segoe UI", 17, "bold")
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
                fila, text=valor, text_color=color, font=("Segoe UI", 12, "bold")
            ).grid(row=0, column=1, sticky="e")

        if resultado.dependencias:
            ctk.CTkLabel(
                tarjeta,
                text=f"Dependencias detectadas ({len(resultado.dependencias)})",
                font=("Segoe UI", 13, "bold")
            ).grid(row=10, column=0, padx=20, pady=(16, 4), sticky="w")

            texto_deps = ", ".join(resultado.dependencias)

            caja_deps = ctk.CTkTextbox(tarjeta, height=90, fg_color="#1a1a1a")
            caja_deps.grid(row=11, column=0, padx=20, pady=(0, 18), sticky="ew")
            caja_deps.insert("1.0", texto_deps)
            caja_deps.configure(state="disabled")
        else:
            ctk.CTkLabel(tarjeta, text="").grid(row=10, column=0, pady=(0, 18))

        boton_ia = ctk.CTkButton(
            self.panel_proyecto,
            text="🤖  Analizar con IA (local, Ollama)",
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
                self.panel_proyecto, height=160, fg_color="#1a1a1a"
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
            text="🤖 DevAI",
            font=("Segoe UI", 24, "bold")
        ).grid(row=0, column=0, sticky="w")

        self.lbl_estado_ia = ctk.CTkLabel(
            encabezado,
            text="Revisando Ollama...",
            font=("Segoe UI", 12),
            text_color="#a0a0a0"
        )
        self.lbl_estado_ia.grid(row=0, column=1, sticky="e")

        fila_carpeta = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_carpeta.grid(row=1, column=0, padx=30, pady=(10, 10), sticky="ew")
        fila_carpeta.grid_columnconfigure(0, weight=1)

        texto_carpeta = self._carpeta_devai or "Ninguna carpeta seleccionada (opcional, pero mejora el diagnóstico)"

        self.lbl_carpeta_devai = ctk.CTkLabel(
            fila_carpeta,
            text=f"📁 {texto_carpeta}",
            font=("Segoe UI", 12),
            text_color="#a0a0a0"
        )
        self.lbl_carpeta_devai.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            fila_carpeta,
            text="Elegir carpeta del proyecto",
            width=190,
            fg_color="#333333",
            hover_color="#444444",
            command=self._elegir_carpeta_devai
        ).grid(row=0, column=1)

        ctk.CTkLabel(
            self.contenido,
            text="Error / traceback (opcional si solo quieres corregir código):",
            text_color="#a0a0a0",
            font=("Segoe UI", 12)
        ).grid(row=2, column=0, padx=30, pady=(0, 4), sticky="w")

        self.caja_error = ctk.CTkTextbox(self.contenido, height=90)
        self.caja_error.grid(row=3, column=0, padx=30, pady=(0, 10), sticky="ew")

        fila_label_codigo = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_label_codigo.grid(row=4, column=0, padx=30, pady=(0, 4), sticky="ew")
        fila_label_codigo.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            fila_label_codigo,
            text="Código relacionado (opcional si solo quieres explicar un error):",
            text_color="#a0a0a0",
            font=("Segoe UI", 12)
        ).grid(row=0, column=0, sticky="w")

        self.btn_cargar_archivo_codigo = ctk.CTkButton(
            fila_label_codigo,
            text="📂 Cargar archivo",
            width=140,
            height=24,
            fg_color="#3a3a3a",
            hover_color="#4a4a4a",
            command=self._cargar_archivo_en_caja_codigo
        )
        self.btn_cargar_archivo_codigo.grid(row=0, column=1, sticky="e")

        self.caja_codigo = ctk.CTkTextbox(self.contenido, height=110)
        self.caja_codigo.grid(row=5, column=0, padx=30, pady=(0, 10), sticky="ew")

        fila_botones = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_botones.grid(row=6, column=0, padx=30, pady=(0, 16), sticky="w")

        self.btn_analizar_error = ctk.CTkButton(
            fila_botones,
            text="🤖  Explicar error",
            command=self._explicar_error_pegado
        )
        self.btn_analizar_error.grid(row=0, column=0, padx=(0, 8))

        self.btn_corregir_codigo = ctk.CTkButton(
            fila_botones,
            text="🛠️  Corregir código",
            fg_color="#2b6b3a",
            hover_color="#347f46",
            command=self._corregir_codigo_pegado
        )
        self.btn_corregir_codigo.grid(row=0, column=1, padx=(0, 8))

        self.btn_revisar_archivo = ctk.CTkButton(
            fila_botones,
            text="📄  Revisar archivo completo",
            fg_color="#6b4e2b",
            hover_color="#7f5f34",
            command=self._revisar_archivo_completo
        )
        self.btn_revisar_archivo.grid(row=0, column=2)

        ctk.CTkLabel(
            self.contenido,
            text="✨ Generar código nuevo desde una descripción:",
            text_color="#a0a0a0",
            font=("Segoe UI", 12)
        ).grid(row=7, column=0, padx=30, pady=(6, 4), sticky="w")

        self.caja_descripcion_generar = ctk.CTkTextbox(self.contenido, height=80)
        self.caja_descripcion_generar.grid(row=8, column=0, padx=30, pady=(0, 10), sticky="ew")

        fila_botones_generar = ctk.CTkFrame(self.contenido, fg_color="transparent")
        fila_botones_generar.grid(row=9, column=0, padx=30, pady=(0, 16), sticky="w")

        self.btn_generar_codigo = ctk.CTkButton(
            fila_botones_generar,
            text="✨  Generar código",
            fg_color="#5b3a8f",
            hover_color="#6d46a8",
            command=self._generar_codigo_desde_descripcion
        )
        self.btn_generar_codigo.grid(row=0, column=0, padx=(0, 8))

        self.btn_guardar_codigo_generado = ctk.CTkButton(
            fila_botones_generar,
            text="💾  Guardar como archivo",
            fg_color="#1f7a3d",
            hover_color="#25914a",
            command=self._guardar_codigo_generado
        )
        self.btn_guardar_codigo_generado.grid(row=0, column=1)
        self.btn_guardar_codigo_generado.grid_remove()

        self.btn_aplicar_correccion = ctk.CTkButton(
            self.contenido,
            text="✅  Aplicar corrección al archivo",
            fg_color="#1f7a3d",
            hover_color="#25914a",
            command=self._aplicar_correccion_al_archivo
        )
        self.btn_aplicar_correccion.grid(row=10, column=0, padx=30, pady=(0, 12), sticky="w")
        self.btn_aplicar_correccion.grid_remove()

        self.caja_respuesta_error = ctk.CTkTextbox(
            self.contenido, fg_color="#1a1a1a"
        )
        self.caja_respuesta_error.grid(row=11, column=0, padx=30, pady=(0, 20), sticky="nsew")
        self.contenido.grid_rowconfigure(11, weight=1)
        self.caja_respuesta_error.insert("1.0", "Aquí aparecerá la respuesta...")
        self.caja_respuesta_error.configure(state="disabled")

        threading.Thread(target=self._revisar_estado_ollama, daemon=True).start()

    def _elegir_carpeta_devai(self):
        ruta = filedialog.askdirectory(
            title="Selecciona la carpeta del proyecto (opcional)"
        )

        if not ruta:
            return

        self._carpeta_devai = ruta
        self.lbl_carpeta_devai.configure(text=f"📁 {ruta}")

    def _cargar_archivo_en_caja_codigo(self):
        ruta = filedialog.askopenfilename(
            title="Selecciona el archivo a corregir",
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

        self.caja_codigo.delete("1.0", "end")
        self.caja_codigo.insert("1.0", contenido)
        self._ruta_codigo_cargado = ruta

    def _revisar_estado_ollama(self):
        disponible = esta_disponible_ia()
        texto = "🟢 Ollama conectado" if disponible else "🔴 Ollama no detectado"
        self.after(0, lambda: self.lbl_estado_ia.configure(text=texto))

    def _explicar_error_pegado(self):
        texto_error = self.caja_error.get("1.0", "end").strip()

        if not texto_error:
            messagebox.showinfo("DevBox", "Pega un error primero.")
            return

        self._deshabilitar_botones_ia("🤖  Pensando...")

        carpeta = self._carpeta_devai

        def tarea():
            try:
                archivos = listar_archivos_proyecto(carpeta) if carpeta else None
                respuesta = explicar_error(texto_error, archivos_proyecto=archivos)
            except OllamaNoDisponible as error:
                respuesta = f"⚠️ {error}"

            self.after(0, lambda: self._mostrar_respuesta_error(respuesta))

        threading.Thread(target=tarea, daemon=True).start()

    def _corregir_codigo_pegado(self):
        codigo = self.caja_codigo.get("1.0", "end").strip()

        if not codigo:
            messagebox.showinfo("DevBox", "Pega el código que quieres corregir primero.")
            return

        texto_error = self.caja_error.get("1.0", "end").strip()
        ruta_cargada = self._ruta_codigo_cargado

        self._deshabilitar_botones_ia("🛠️  Corrigiendo...")

        carpeta = self._carpeta_devai

        def tarea():
            try:
                archivos = listar_archivos_proyecto(carpeta) if carpeta else None
                respuesta = corregir_codigo(
                    codigo,
                    contexto_error=texto_error,
                    archivos_proyecto=archivos
                )
            except OllamaNoDisponible as error:
                respuesta = f"⚠️ {error}"
                self.after(0, lambda: self._mostrar_respuesta_error(respuesta))
                return

            # Si el código vino de un archivo cargado (no solo pegado a
            # mano) y la IA devolvió un bloque de código reconocible,
            # se puede ofrecer aplicar la corrección directo a ese
            # archivo -reutilizando la misma vista previa + respaldo
            # que ya usa "Revisar archivo completo". El rango cubre
            # el archivo completo porque corregir_codigo() siempre
            # devuelve el fragmento entero ya corregido, no una línea
            # puntual.
            info_aplicable = None

            if ruta_cargada and extraer_bloque_codigo(respuesta) is not None:
                info_aplicable = {
                    "ruta": ruta_cargada,
                    "linea_inicio": 1,
                    "linea_fin": len(codigo.splitlines()),
                }

            self.after(0, lambda: self._mostrar_respuesta_error(respuesta, info_aplicable))

        threading.Thread(target=tarea, daemon=True).start()

    def _deshabilitar_botones_ia(self, texto_boton_activo: str):
        self.btn_analizar_error.configure(state="disabled")
        self.btn_corregir_codigo.configure(state="disabled")
        self.btn_revisar_archivo.configure(state="disabled")
        self.btn_generar_codigo.configure(state="disabled")
        self._ocultar_boton_aplicar()
        self.btn_guardar_codigo_generado.grid_remove()

        self.caja_respuesta_error.configure(state="normal")
        self.caja_respuesta_error.delete("1.0", "end")
        self.caja_respuesta_error.insert("1.0", f"{texto_boton_activo} un momento...")
        self.caja_respuesta_error.configure(state="disabled")

    def _mostrar_respuesta_error(self, texto: str, info_aplicable: dict | None = None):
        self.caja_respuesta_error.configure(state="normal")
        self.caja_respuesta_error.delete("1.0", "end")
        self.caja_respuesta_error.insert("1.0", texto)
        self.caja_respuesta_error.configure(state="disabled")
        self.btn_analizar_error.configure(state="normal", text="🤖  Explicar error")
        self.btn_corregir_codigo.configure(state="normal", text="🛠️  Corregir código")
        self.btn_revisar_archivo.configure(state="normal", text="📄  Revisar archivo completo")
        self.btn_generar_codigo.configure(state="normal", text="✨  Generar código")

        self._info_aplicable = info_aplicable

        if info_aplicable is not None:
            self.btn_aplicar_correccion.grid()
        else:
            self._ocultar_boton_aplicar()

    def _generar_codigo_desde_descripcion(self):
        descripcion = self.caja_descripcion_generar.get("1.0", "end").strip()

        if not descripcion:
            messagebox.showinfo("DevBox", "Describe primero qué código quieres que genere.")
            return

        self._deshabilitar_botones_ia("✨  Generando...")

        carpeta = self._carpeta_devai

        def tarea():
            try:
                archivos = listar_archivos_proyecto(carpeta) if carpeta else None
                respuesta = generar_codigo(descripcion, archivos_proyecto=archivos)
            except OllamaNoDisponible as error:
                respuesta = f"⚠️ {error}"

            self.after(0, lambda: self._mostrar_respuesta_generada(respuesta))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_respuesta_generada(self, texto: str):
        self.caja_respuesta_error.configure(state="normal")
        self.caja_respuesta_error.delete("1.0", "end")
        self.caja_respuesta_error.insert("1.0", texto)
        self.caja_respuesta_error.configure(state="disabled")
        self.btn_analizar_error.configure(state="normal", text="🤖  Explicar error")
        self.btn_corregir_codigo.configure(state="normal", text="🛠️  Corregir código")
        self.btn_revisar_archivo.configure(state="normal", text="📄  Revisar archivo completo")
        self.btn_generar_codigo.configure(state="normal", text="✨  Generar código")

        self._ultimo_codigo_generado = extraer_bloque_codigo(texto)

        if self._ultimo_codigo_generado is not None:
            self.btn_guardar_codigo_generado.grid()
        else:
            self.btn_guardar_codigo_generado.grid_remove()

    def _guardar_codigo_generado(self):
        if not self._ultimo_codigo_generado:
            return

        ruta = filedialog.asksaveasfilename(
            title="Guardar código generado como...",
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

    def _revisar_archivo_completo(self):
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

        self._deshabilitar_botones_ia("📄  Revisando...")
        self._info_aplicable = None
        self._ocultar_boton_aplicar()

        def tarea():
            try:
                texto, info_aplicable = revisar_archivo(
                    nombre, contenido, ruta_completa=ruta
                )
            except OllamaNoDisponible as error:
                texto, info_aplicable = f"⚠️ {error}", None

            self.after(
                0, lambda: self._mostrar_respuesta_error(texto, info_aplicable)
            )

        threading.Thread(target=tarea, daemon=True).start()

    def _ocultar_boton_aplicar(self):
        if getattr(self, "btn_aplicar_correccion", None) is not None:
            self.btn_aplicar_correccion.grid_remove()

    def _aplicar_correccion_al_archivo(self):
        if not self._info_aplicable:
            return

        texto_actual = self.caja_respuesta_error.get("1.0", "end")
        ok, vista_previa = generar_vista_previa(self._info_aplicable, texto_actual)

        if not ok:
            messagebox.showerror("DevBox", f"No se puede aplicar:\n{vista_previa}")
            return

        self._mostrar_dialogo_vista_previa(vista_previa, texto_actual)

    def _mostrar_dialogo_vista_previa(self, vista_previa: str, texto_respuesta: str):
        dialogo = ctk.CTkToplevel(self)
        dialogo.title("Confirmar corrección")
        dialogo.geometry("640x480")
        dialogo.transient(self)
        dialogo.grab_set()

        ctk.CTkLabel(
            dialogo,
            text="Revisa exactamente qué va a cambiar antes de aplicar:",
            font=("Segoe UI", 13, "bold")
        ).pack(padx=16, pady=(16, 8), anchor="w")

        caja = ctk.CTkTextbox(dialogo, fg_color="#1a1a1a")
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
            fila_botones, text="Cancelar", fg_color="#333333",
            hover_color="#444444", command=dialogo.destroy
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            fila_botones, text="✅  Aplicar de todas formas",
            fg_color="#1f7a3d", hover_color="#25914a", command=confirmar
        ).pack(side="left")


if __name__ == "__main__":
    app = DevBoxApp()
    app.mainloop()
