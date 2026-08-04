"""teste_backup.py — exporta, restaura e confere que os números voltam iguais.

    python3 teste_backup.py

Um backup que não foi testado é só um arquivo. Este teste faz o caminho inteiro
num banco descartável: cria dados, gera o .zip, restaura num grupo novo e
compara os totais e as ligações entre as tabelas.
"""

import json
import os
import sqlite3
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db  # noqa: E402
import restaurar_backup  # noqa: E402
from modules import backup  # noqa: E402


def _conexao_descartavel():
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-backup-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    return conn


def executar():
    conn = _conexao_descartavel()
    db.init_db(conn)
    falhas = []

    grupo = db.criar_grupo(conn, "Família Teste")
    categoria = [c for c in db.listar_categorias(conn) if c["tipo"] in ("saida", "despesa")][0]["id"]

    conta = db.criar_conta(conn, "Banco Teste", "banco", 5000.0, grupo_id=grupo)
    cartao = db.criar_cartao(conn, "Cartão Teste", 25, 5, 3000.0, grupo_id=grupo)
    for i in range(3):
        db.criar_lancamento(conn, f"2026-08-0{i+1}", conta, categoria, f"Despesa {i+1}",
                            100.0 * (i + 1), "saida", "pago", 1, grupo_id=grupo)
    db.criar_patrimonio_item(conn, "Apartamento", "ativo", "Imóvel", 400000.0, 1, grupo_id=grupo)
    db.criar_investimento(conn, "Tesouro", "Renda Fixa", 1000.0, 1100.0, 1, grupo_id=grupo)
    db.criar_meta(conn, "Viagem", 8000.0, "2026-12-31", 1, grupo_id=grupo)

    saldo_antes = db.saldo_total(conn, grupo_id=grupo)
    patrimonio_antes = db.patrimonio_liquido(conn, grupo_id=grupo)
    print(f"Origem (grupo {grupo}): saldo {saldo_antes:,.2f} · patrimônio {patrimonio_antes:,.2f}")

    # ── Exportar ─────────────────────────────────────────────────────────
    dados = backup._coletar(conn, grupo)
    conteudo = backup._montar_zip(dados, "Família Teste", grupo)
    caminho_zip = os.path.join(tempfile.mkdtemp(), "backup.zip")
    with open(caminho_zip, "wb") as f:
        f.write(conteudo)

    with zipfile.ZipFile(caminho_zip) as z:
        nomes = z.namelist()
        pacote = json.loads(z.read("backup-completo.json"))
    print(f"\nZip gerado com {len(nomes)} arquivo(s): {', '.join(sorted(nomes)[:4])}…")

    if not any(n.startswith("csv/") for n in nomes):
        falhas.append("zip sem CSVs")
    if "LEIA-ME.txt" not in nomes:
        falhas.append("zip sem LEIA-ME")
    if len(pacote["tabelas"]["lancamentos"]) != 3:
        falhas.append("lançamentos não entraram no backup")
    if len(pacote["tabelas"]["cartoes"]) != 1:
        falhas.append("cartão não entrou no backup")

    # ── Restaurar no mesmo banco, num grupo novo ─────────────────────────
    print("\nRestaurando…")
    restaurar_backup.restaurar(caminho_zip, aplicar=True, conn=conn)

    grupos = conn.execute("SELECT id FROM grupos ORDER BY id").fetchall()
    novo = grupos[-1]["id"]
    if novo == grupo:
        falhas.append("restauração não criou grupo novo")

    saldo_depois = db.saldo_total(conn, grupo_id=novo)
    patrimonio_depois = db.patrimonio_liquido(conn, grupo_id=novo)
    print(f"\nDestino (grupo {novo}): saldo {saldo_depois:,.2f} · patrimônio {patrimonio_depois:,.2f}")

    if abs(saldo_antes - saldo_depois) > 0.001:
        falhas.append(f"saldo mudou: {saldo_antes} -> {saldo_depois}")
    if abs(patrimonio_antes - patrimonio_depois) > 0.001:
        falhas.append(f"patrimônio mudou: {patrimonio_antes} -> {patrimonio_depois}")

    # O grupo original não pode ter sido tocado.
    if abs(db.saldo_total(conn, grupo_id=grupo) - saldo_antes) > 0.001:
        falhas.append("restauração alterou o grupo de origem")

    # As ligações precisam apontar para as linhas novas, não para as antigas.
    contas_novas = {c["id"] for c in db.listar_contas(conn, apenas_ativas=False, grupo_id=novo)}
    for lanc in db.listar_lancamentos(conn, grupo_id=novo):
        if lanc["conta_id"] not in contas_novas:
            falhas.append("lançamento restaurado aponta para conta de outro grupo")
            break
    print(f"  {len(contas_novas)} conta(s) e {len(db.listar_lancamentos(conn, grupo_id=novo))} "
          f"lançamento(s) religados corretamente")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — o backup volta idêntico e sem encostar no grupo original.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
