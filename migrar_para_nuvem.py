"""Copia o banco local (SQLite) para o Turso.

Uso:
    python3 migrar_para_nuvem.py           # simulação, não grava nada
    python3 migrar_para_nuvem.py --aplicar # grava de verdade

Seguro de repetir: recusa rodar se o destino já tiver dados,
a menos que você passe --limpar-destino.
"""

import argparse
import pathlib
import sqlite3
import sys

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import conexao
import database as db

TABELAS = [
    "usuarios", "contas", "cartoes", "categorias", "lancamentos",
    "patrimonio_itens", "investimentos", "metas", "anexos",
]
# sessoes fica de fora: são tokens do navegador local, não fazem sentido migrar


def credenciais():
    caminho = pathlib.Path(__file__).parent / ".streamlit" / "secrets.toml"
    if not caminho.exists():
        sys.exit("❌ .streamlit/secrets.toml não encontrado.")
    cfg = tomllib.loads(caminho.read_text())
    if "turso" not in cfg:
        sys.exit("❌ Seção [turso] ausente no secrets.toml.")
    return cfg["turso"]["url"], cfg["turso"]["auth_token"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="grava de verdade")
    ap.add_argument("--limpar-destino", action="store_true", help="apaga dados do Turso antes")
    args = ap.parse_args()

    origem = sqlite3.connect(conexao.CAMINHO_LOCAL)
    origem.row_factory = sqlite3.Row

    url, token = credenciais()
    destino = conexao.ConexaoTurso(url, token)

    print("Criando estrutura no destino…")
    if args.aplicar:
        db.init_db(destino)
    print("  ok\n")

    # o destino já tem dados?
    if args.aplicar and not args.limpar_destino:
        ocupadas = []
        for t in TABELAS:
            try:
                n = destino.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                if n:
                    ocupadas.append(f"{t}({n})")
            except Exception:
                pass
        if ocupadas:
            sys.exit(
                "❌ O banco na nuvem já tem dados: " + ", ".join(ocupadas) +
                "\n   Use --limpar-destino para sobrescrever."
            )

    if args.aplicar and args.limpar_destino:
        print("Limpando destino…")
        for t in reversed(TABELAS):
            try:
                destino.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        print("  ok\n")

    total = 0
    for tabela in TABELAS:
        try:
            linhas = origem.execute(f"SELECT * FROM {tabela}").fetchall()
        except sqlite3.OperationalError:
            print(f"  {tabela}: não existe na origem, pulando")
            continue

        if not linhas:
            print(f"  {tabela}: vazia")
            continue

        colunas = linhas[0].keys()
        marcadores = ",".join("?" for _ in colunas)
        sql = f"INSERT INTO {tabela} ({','.join(colunas)}) VALUES ({marcadores})"

        if args.aplicar:
            destino.executemany(sql, [tuple(l) for l in linhas])

        print(f"  {tabela}: {len(linhas)} registro(s){'' if args.aplicar else ' (simulação)'}")
        total += len(linhas)

    print(f"\n{'✅ Migrado' if args.aplicar else '🔍 Simulação'}: {total} registros.")

    if args.aplicar:
        print("\nConferindo o destino:")
        for tabela in TABELAS:
            try:
                n = destino.execute(f"SELECT COUNT(*) AS n FROM {tabela}").fetchone()["n"]
                if n:
                    print(f"  {tabela}: {n}")
            except Exception as e:
                print(f"  {tabela}: erro ao conferir — {e}")
    else:
        print("\nPara gravar de verdade:  python3 migrar_para_nuvem.py --aplicar")

    destino.close()
    origem.close()


if __name__ == "__main__":
    main()
