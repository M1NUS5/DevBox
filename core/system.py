"""
Detecta qué lenguajes de programación y herramientas de desarrollo
están instalados en el sistema, sin instalar nada por su cuenta.

Cada entrada de HERRAMIENTAS define cómo se llama el ejecutable en
la terminal y cómo extraer su versión, para poder decirle al
usuario exactamente qué tiene disponible ahora mismo.
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ResultadoDeteccion:
    id: str
    nombre: str
    categoria: str
    instalado: bool
    version: str | None
    ruta: str | None
    icono: str | None = None


# Carpeta con los logos reales (PNG) de cada lenguaje/herramienta,
# en vez de emojis: se ven consistentes entre sistemas operativos.
# Empaquetado con PyInstaller, __file__ ya no apunta a una ruta real
# del proyecto -en ese caso los datos empaquetados ("datas" del
# .spec) viven junto a sys._MEIPASS.
if getattr(sys, "frozen", False):
    _DIR_BASE = sys._MEIPASS
else:
    _DIR_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DIR_ICONOS = os.path.join(_DIR_BASE, "assets", "icons")

_ICONOS = {
    "python": "python.png",
    "node": "node.png",
    "java": "java.png",
    "kotlin": "kotlin.png",
    "go": "go.png",
    "rust": "rust.png",
    "php": "php.png",
    "ruby": "ruby.png",
    "dotnet": "dotnet.png",
    "swift": "swift.png",
    "cpp": "cpp.png",
    "dart": "dart.png",
    "perl": "perl.png",
    "git": "git.png",
    "docker": "docker.png",
    "npm": "npm.png",
    "pip": "pip.png",
    "brew": "brew.png",
    "vscode": "vscode.png",
    "maven": "maven.png",
    "yarn": "yarn.png",
    "cmake": "cmake.png",
}


def ruta_icono(id_: str) -> str | None:
    """Ruta absoluta al logo de la herramienta, o None si no hay archivo."""
    nombre_archivo = _ICONOS.get(id_)
    if not nombre_archivo:
        return None

    ruta = os.path.join(_DIR_ICONOS, nombre_archivo)
    return ruta if os.path.isfile(ruta) else None


# Cada tupla es: (id, nombre visible, categoría, comando ejecutable,
# argumento de versión, expresión regular para extraer el número)
_DEFINICIONES = [
    ("python", "Python", "lenguaje", "python3", "--version", r"(\d+\.\d+\.\d+)"),
    ("node", "Node.js", "lenguaje", "node", "--version", r"v?(\d+\.\d+\.\d+)"),
    ("java", "Java", "lenguaje", "java", "-version", r'"(\d+[\d._]*)"'),
    ("kotlin", "Kotlin", "lenguaje", "kotlinc", "-version", r"(\d+\.\d+\.\d+)"),
    ("go", "Go", "lenguaje", "go", "version", r"go(\d+\.\d+(?:\.\d+)?)"),
    ("rust", "Rust", "lenguaje", "rustc", "--version", r"(\d+\.\d+\.\d+)"),
    ("php", "PHP", "lenguaje", "php", "--version", r"(\d+\.\d+\.\d+)"),
    ("ruby", "Ruby", "lenguaje", "ruby", "--version", r"(\d+\.\d+\.\d+)"),
    ("dotnet", ".NET", "lenguaje", "dotnet", "--version", r"(\d+\.\d+\.\d+)"),
    ("swift", "Swift", "lenguaje", "swift", "--version", r"(\d+\.\d+(?:\.\d+)?)"),
    ("cpp", "C/C++ (clang)", "lenguaje", "clang", "--version", r"version (\d+\.\d+\.\d+)"),
    ("dart", "Dart", "lenguaje", "dart", "--version", r"(\d+\.\d+\.\d+)"),
    ("perl", "Perl", "lenguaje", "perl", "--version", r"\(v(\d+\.\d+\.\d+)\)"),
    ("git", "Git", "herramienta", "git", "--version", r"(\d+\.\d+\.\d+)"),
    ("docker", "Docker", "herramienta", "docker", "--version", r"(\d+\.\d+\.\d+)"),
    ("npm", "npm", "herramienta", "npm", "--version", r"(\d+\.\d+\.\d+)"),
    ("pip", "pip", "herramienta", "pip3", "--version", r"pip (\d+\.\d+(?:\.\d+)?)"),
    ("brew", "Homebrew", "herramienta", "brew", "--version", r"(\d+\.\d+\.\d+)"),
    ("vscode", "VS Code", "herramienta", "code", "--version", r"(\d+\.\d+\.\d+)"),
    ("maven", "Maven", "herramienta", "mvn", "--version", r"(\d+\.\d+\.\d+)"),
    ("yarn", "Yarn", "herramienta", "yarn", "--version", r"(\d+\.\d+\.\d+)"),
    ("cmake", "CMake", "herramienta", "cmake", "--version", r"(\d+\.\d+\.\d+)"),
]


def _detectar_uno(
    id_: str,
    nombre: str,
    categoria: str,
    comando: str,
    arg_version: str,
    patron_version: str
) -> ResultadoDeteccion:
    icono = ruta_icono(id_)
    ruta = shutil.which(comando)

    if ruta is None:
        return ResultadoDeteccion(id_, nombre, categoria, False, None, None, icono)

    version = None

    try:
        resultado = subprocess.run(
            [comando, arg_version],
            capture_output=True,
            text=True,
            timeout=5,
            check=False
        )

        salida = (resultado.stdout + resultado.stderr).strip()
        coincidencia = re.search(patron_version, salida)

        if coincidencia:
            version = coincidencia.group(1)

    except Exception:
        pass

    return ResultadoDeteccion(id_, nombre, categoria, True, version, ruta, icono)


def detectar_todo() -> list[ResultadoDeteccion]:
    """
    Revisa cada herramienta definida en _DEFINICIONES y devuelve el
    resultado de todas, instaladas o no.
    """
    return [_detectar_uno(*definicion) for definicion in _DEFINICIONES]


def detectar_instalados() -> list[ResultadoDeteccion]:
    """Solo lo que sí está disponible en el sistema."""
    return [r for r in detectar_todo() if r.instalado]


def exportar_a_json(resultados: list[ResultadoDeteccion], ruta_destino: str) -> None:
    """
    Guarda el reporte de detección en un archivo .json legible,
    útil para compartir tu entorno de desarrollo con alguien más.
    """
    import json

    datos = [
        {
            "id": r.id,
            "nombre": r.nombre,
            "categoria": r.categoria,
            "instalado": r.instalado,
            "version": r.version,
            "ruta": r.ruta,
        }
        for r in resultados
    ]

    with open(ruta_destino, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, indent=2, ensure_ascii=False)
