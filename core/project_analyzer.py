"""
Analiza una carpeta de proyecto y detecta de qué tipo es (Python,
Node.js, Java, Rust, Go, etc.) según los archivos característicos
que encuentre en la raíz, además de un resumen general: cuántos
archivos tiene, si cuenta con README, .gitignore, y control de
versiones con Git.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


# Carpetas que no aportan nada al conteo y solo inflan el número
# de archivos (dependencias instaladas, entornos virtuales, etc.)
_CARPETAS_IGNORADAS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".next", "target", ".idea", ".vscode",
}

# (archivo clave, nombre del tipo de proyecto, categoría del lenguaje)
_DEFINICIONES_PROYECTO = [
    ("package.json", "Node.js / JavaScript", "node"),
    ("requirements.txt", "Python", "python"),
    ("pyproject.toml", "Python", "python"),
    ("Cargo.toml", "Rust", "rust"),
    ("go.mod", "Go", "go"),
    ("pom.xml", "Java (Maven)", "java"),
    ("build.gradle", "Java/Kotlin (Gradle)", "java"),
    ("build.gradle.kts", "Java/Kotlin (Gradle)", "kotlin"),
    ("Gemfile", "Ruby", "ruby"),
    ("composer.json", "PHP", "php"),
    ("Package.swift", "Swift", "swift"),
]


@dataclass
class ResultadoProyecto:
    ruta: str
    tipo: str
    archivo_clave: str | None
    total_archivos: int
    tiene_readme: bool
    tiene_gitignore: bool
    tiene_git: bool
    dependencias: list[str] = field(default_factory=list)


def _contar_archivos(ruta: Path) -> int:
    total = 0

    for raiz, carpetas, archivos in os.walk(ruta):
        carpetas[:] = [c for c in carpetas if c not in _CARPETAS_IGNORADAS]
        total += len(archivos)

    return total


def _buscar_archivo_insensible(ruta: Path, nombres: list[str]) -> bool:
    existentes = {p.name.lower() for p in ruta.iterdir() if p.is_file()}
    return any(nombre.lower() in existentes for nombre in nombres)


def _extraer_dependencias_python(ruta_requirements: Path) -> list[str]:
    dependencias = []

    try:
        for linea in ruta_requirements.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()

            if not linea or linea.startswith("#"):
                continue

            # Corta en el primer caracter que indique una versión
            # (==, >=, <=, ~=, etc.) para quedarnos solo con el nombre.
            for separador in ["==", ">=", "<=", "~=", ">", "<", "!="]:
                if separador in linea:
                    linea = linea.split(separador)[0]
                    break

            dependencias.append(linea.strip())

    except OSError:
        pass

    return dependencias


def _extraer_dependencias_node(ruta_package_json: Path) -> list[str]:
    import json

    try:
        datos = json.loads(ruta_package_json.read_text(encoding="utf-8"))
        dependencias = list(datos.get("dependencies", {}).keys())
        dependencias += list(datos.get("devDependencies", {}).keys())
        return dependencias

    except (OSError, json.JSONDecodeError):
        return []


def analizar_proyecto(ruta_carpeta: str) -> ResultadoProyecto:
    ruta = Path(ruta_carpeta)

    tipo = "Desconocido"
    archivo_clave = None
    dependencias: list[str] = []

    for nombre_archivo, nombre_tipo, _categoria in _DEFINICIONES_PROYECTO:
        candidato = ruta / nombre_archivo

        if candidato.exists():
            tipo = nombre_tipo
            archivo_clave = nombre_archivo

            if nombre_archivo == "requirements.txt":
                dependencias = _extraer_dependencias_python(candidato)
            elif nombre_archivo == "package.json":
                dependencias = _extraer_dependencias_node(candidato)

            break

    return ResultadoProyecto(
        ruta=str(ruta),
        tipo=tipo,
        archivo_clave=archivo_clave,
        total_archivos=_contar_archivos(ruta),
        tiene_readme=_buscar_archivo_insensible(
            ruta, ["README.md", "README.rst", "README.txt", "README"]
        ),
        tiene_gitignore=_buscar_archivo_insensible(ruta, [".gitignore"]),
        tiene_git=(ruta / ".git").exists(),
        dependencias=dependencias,
    )
