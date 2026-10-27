"""Abre uma instalação de demonstração isolada, sem usar os dados reais."""

import argparse
from contextlib import closing
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.request import build_opener, ProxyHandler
import webbrowser

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(
        description="Tramê — demonstração com três meses de dados fictícios."
    )
    parser.add_argument("--porta", type=int, default=18750)
    parser.add_argument("--data", type=date.fromisoformat, default=date.today())
    parser.add_argument("--sem-navegador", action="store_true")
    parser.add_argument(
        "--recriar", action="store_true", help="Arquiva a demonstração anterior e cria outra."
    )
    args = parser.parse_args()
    if not 1024 <= args.porta <= 65535:
        parser.error("Use uma porta entre 1024 e 65535.")
    home = ROOT / ".demo"
    if home.resolve().parent != ROOT.resolve():
        parser.error("A pasta .demo precisa estar dentro do projeto.")
    database = home / "trame-demo.sqlite3"
    url = f"http://127.0.0.1:{args.porta}"
    client = build_opener(ProxyHandler({}))
    try:
        with client.open(url + "/health", timeout=2) as response:
            health = json.load(response)
        expected = hashlib.sha256(str(database.resolve()).casefold().encode()).hexdigest()
        if health.get("instance") != expected:
            parser.exit(
                1, "Esta porta pertence a outra instalação. Use --porta com outro número.\n"
            )
        if args.recriar:
            parser.exit(1, "Encerre a demonstração antes de recriar os dados.\n")
        if not args.sem_navegador:
            webbrowser.open(url)
        print("Demonstração já aberta em " + url)
        return
    except (URLError, TimeoutError):
        pass
    home.mkdir(exist_ok=True)
    if args.recriar and database.exists():
        previous = home / ("arquivo-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        previous.mkdir()
        for file in home.glob("trame-demo.sqlite3*"):
            file.rename(previous / file.name)
    os.environ.update(
        TRAME_LOCAL_ONLY="1", TRAME_DEMO="1", RADAR_DB=str(database), RADAR_PORT=str(args.porta)
    )
    import server
    import access

    if (
        server.DB.resolve() != database.resolve()
        or server.PORT != args.porta
        or server.CONFIG["bind"] != "127.0.0.1"
    ):
        raise RuntimeError(
            "Abra a demonstração em um novo processo Python. A configuração atual pertence a outra instalação."
        )

    if not database.exists():
        from demo_data import build_scenario

        state = build_scenario(args.data)
        with closing(server.connect()) as con:
            access.create_user(
                con,
                {
                    "name": "Equipe de demonstração",
                    "username": "demo",
                    "password": "Trame-Demo-2026!",
                },
                first=True,
            )
            con.execute(
                "UPDATE state SET revision=96,payload=? WHERE id=1",
                (json.dumps(state, ensure_ascii=False),),
            )
            user = con.execute("SELECT id FROM users WHERE username=?", ("demo",)).fetchone()[0]
            for current in state["orders"]:
                timestamp = datetime.fromisoformat(current["entry"] + "T10:30:00").timestamp()
                con.execute(
                    "INSERT INTO audit(at,user_id,name,action,details) VALUES(?,?,?,?,?)",
                    (
                        timestamp,
                        user,
                        "Equipe de demonstração",
                        "Registro fictício de operação",
                        current["client"] + " · " + current["description"],
                    ),
                )
            con.commit()
        (home / "LEIA-ME.txt").write_text(
            "DEMONSTRAÇÃO DO TRAMÊ — DADOS FICTÍCIOS\nLogin: demo\nSenha: Trame-Demo-2026!\nBase de referência: "
            + args.data.isoformat()
            + "\nEsta pasta não contém nem usa os dados da instalação real.\n",
            encoding="utf-8",
        )
    print("DEMONSTRAÇÃO — login: demo | senha: Trame-Demo-2026!", flush=True)
    import iniciar

    sys.argv = ["iniciar.py", "--porta", str(args.porta)] + (
        ["--sem-navegador"] if args.sem_navegador else []
    )
    iniciar.main()


if __name__ == "__main__":
    main()
