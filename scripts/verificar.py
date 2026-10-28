"""Executa as verificações necessárias antes de compartilhar o código."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(command):
    print("\n> " + " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    node = shutil.which("node")
    if not node:
        raise SystemExit("Instale Node.js 22 ou superior para executar os testes JavaScript.")
    ruff = shutil.which("ruff")
    if not ruff:
        raise SystemExit("Instale requirements-dev.txt para executar a análise Python.")
    run([ruff, "check", "."])
    run([ruff, "format", "--check", "."])
    # Proxies corporativos não devem interceptar o HTTP local dos testes.
    os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"])
    for source in sorted((ROOT / "web").glob("*.js")):
        run([node, "--check", str(source)])
    for suite in sorted((ROOT / "tests").glob("test_*.cjs")):
        run([node, str(suite)])
    run([sys.executable, str(ROOT / "scripts" / "conferir_publicacao.py")])
    print("\nVerificação concluída.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
