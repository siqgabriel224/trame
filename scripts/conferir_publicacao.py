"""Rejeita dados e artefatos privados na lista de arquivos do Git."""

from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_FOLDERS = {"dados", "certificados", "node_modules", ".venv", "entrega", "__pycache__"}
PRIVATE_SUFFIXES = {
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
    ".pem",
    ".key",
    ".cer",
    ".exe",
    ".zip",
    ".pyc",
}


def main():
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files = [name.decode("utf-8") for name in tracked.stdout.split(b"\0") if name]
    rejected = []
    for name in files:
        path = PurePosixPath(name)
        if (
            PRIVATE_FOLDERS.intersection(path.parts)
            or path.suffix in PRIVATE_SUFFIXES
            or ".sqlite3-" in path.name
            or path.name.startswith(".env")
            or path.name in {"rede.json", "chave-primeiro-acesso.txt"}
        ):
            rejected.append(name)
    if rejected:
        print("Retire estes arquivos da publicação:\n" + "\n".join(rejected))
        return 1
    print(
        str(len(files))
        + " arquivos conferidos: sem bancos, sessões, chaves ou pacotes na lista do Git."
    )
    print("Esta verificação de caminhos não substitui a revisão do conteúdo dos arquivos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
