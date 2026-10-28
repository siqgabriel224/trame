"""Inicia a edição local do Tramê e mantém o servidor no terminal."""

import argparse
import os
import threading
import urllib.error
import urllib.request
import webbrowser


def open_when_ready(url, stopped):
    """Espera pelo servidor antes de abrir a página de entrada."""
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(60):
        if stopped.wait(0.25):
            return
        try:
            with client.open(url + "/health", timeout=1) as response:
                if response.status == 200:
                    webbrowser.open(url)
                    return
        except (urllib.error.URLError, TimeoutError):
            continue


def main():
    parser = argparse.ArgumentParser(description="Tramê — pedidos e produção neste computador.")
    parser.add_argument("--sem-navegador", action="store_true", help="Inicia somente o servidor.")
    parser.add_argument(
        "--verificar-email",
        action="store_true",
        help="Verifica conexão e credenciais de e-mail, sem enviar mensagens nem iniciar o servidor.",
    )
    parser.add_argument("--porta", type=int, default=18743, help="Porta local (padrão: 18743).")
    args = parser.parse_args()
    if not 1024 <= args.porta <= 65535:
        parser.error("A porta deve estar entre 1024 e 65535.")
    if args.verificar_email:
        import access

        try:
            access.check_email_connection()
        except ValueError as exc:
            parser.exit(1, str(exc) + "\n")
        print("Conexão de e-mail verificada. Nenhuma mensagem foi enviada.")
        return

    # Configuração aplicada antes de importar o servidor, que resolve o ambiente ao carregar.
    os.environ["TRAME_LOCAL_ONLY"] = "1"
    os.environ["RADAR_PORT"] = str(args.porta)
    import server

    stopped = threading.Event()
    opener = None
    try:
        # Reserva a porta antes de criar chaves ou arquivos de backup.
        http = server.TrameHTTPServer(("127.0.0.1", args.porta), server.Handler)
    except OSError as exc:
        parser.exit(
            1,
            "Não foi possível abrir a porta local. Feche outra instância ou use --porta.\n"
            + str(exc)
            + "\n",
        )
    try:
        server.connect().close()
        server.network.backup(server)
        server.network.bootstrap(server)
        url = "http://127.0.0.1:" + str(args.porta)
        print("Tramê em " + url, flush=True)
        print("Para encerrar, pressione Ctrl+C neste terminal.", flush=True)
        if not args.sem_navegador:
            opener = threading.Thread(target=open_when_ready, args=(url, stopped), daemon=True)
            opener.start()
        http.serve_forever()
    except KeyboardInterrupt:
        print("\nTramê encerrado.")
    finally:
        stopped.set()
        http.server_close()
        if opener:
            opener.join(timeout=2)


if __name__ == "__main__":
    main()
