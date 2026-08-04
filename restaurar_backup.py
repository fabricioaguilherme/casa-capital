"""restaurar_backup.py — devolve ao banco os dados de um backup.

    python3 restaurar_backup.py backup-completo.json              # só mostra
    python3 restaurar_backup.py backup-completo.json --aplicar    # grava

Sem --aplicar nada é escrito: o script lê o arquivo, confere e imprime o que
faria. Restaurar é a operação mais perigosa do sistema, então ela começa
desarmada.

Aceita o .json solto ou o .zip inteiro que a tela de Backup baixa.

Como os dados voltam
--------------------
Os IDs do backup não são reaproveitados. Cada linha é inserida como nova e o
script guarda de/para (id antigo → id novo) para religar lançamento com conta,
cartão com conta e assim por diante. Isso permite restaurar num banco que já
tem dados sem colidir com os IDs de lá.

Por padrão o destino é um grupo novo, criado na hora. Assim a restauração nunca
mistura com o que já existe — você compara os dois e apaga o que não quiser.
Para jogar dentro de um grupo existente, use --grupo N.
"""

import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import conexao  # noqa: E402

# Ordem importa: quem é apontado entra antes de quem aponta.
ORDEM = ["contas", "cartoes", "lancamentos", "patrimonio_itens", "investimentos", "metas", "anexos"]

# Coluna que aponta para outra tabela → tabela apontada.
CHAVES_ESTRANGEIRAS = {
    "cartoes": {"conta_id": "contas"},
    "lancamentos": {"conta_id": "contas", "cartao_id": "cartoes", "categoria_id": "categorias"},
}


def carregar(caminho):
    if caminho.endswith(".zip"):
        with zipfile.ZipFile(caminho) as z:
            nome = next((n for n in z.namelist() if n.endswith("backup-completo.json")), None)
            if not nome:
                raise SystemExit("O .zip não tem backup-completo.json dentro.")
            dados = json.loads(z.read(nome))
    else:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)

    if dados.get("formato") != "casa-capital-backup":
        raise SystemExit("Este arquivo não é um backup do Casa Capital.")
    return dados


def mapear_categorias(conn, categorias_backup):
    """Casa as categorias do backup com as do banco pelo nome.

    Categorias são a lista padrão do sistema, não pertencem a grupo. Recriá-las
    duplicaria a lista inteira, então o de/para é feito por nome; o que não
    existir no destino é criado.
    """
    atuais = {c["nome"]: c["id"] for c in conn.execute("SELECT id, nome FROM categorias").fetchall()}
    de_para = {}
    criadas = 0
    for cat in categorias_backup:
        if cat["nome"] in atuais:
            de_para[cat["id"]] = atuais[cat["nome"]]
        else:
            cur = conn.execute(
                "INSERT INTO categorias (nome, tipo, icone) VALUES (?, ?, ?)",
                (cat["nome"], cat.get("tipo"), cat.get("icone")),
            )
            de_para[cat["id"]] = cur.lastrowid
            criadas += 1
    if criadas:
        conn.commit()
        print(f"   {criadas} categoria(s) que não existiam no destino foram criadas.")
    return de_para


def restaurar(caminho, aplicar=False, grupo_destino=None, conn=None):
    """conn só é passado pelos testes; em uso normal a conexão vem de conexao.py."""
    backup = carregar(caminho)
    tabelas = backup["tabelas"]

    print(f"Backup de: {backup['grupo']['nome']}")
    print(f"Gerado em: {backup.get('gerado_em', '?')}")
    print("\nConteúdo:")
    for tabela in ORDEM:
        print(f"   {tabela:20} {len(tabelas.get(tabela, []))} linha(s)")

    if not aplicar:
        print("\n--- SIMULAÇÃO: nada foi gravado. ---")
        print("Para gravar de verdade, repita o comando com --aplicar no final.")
        return

    if conn is None:
        conn = conexao.conectar()
        print(f"\nDestino: banco {conexao.modo()}")

    if grupo_destino is None:
        nome = f"{backup['grupo']['nome']} (restaurado)"
        cur = conn.execute("INSERT INTO grupos (nome) VALUES (?)", (nome,))
        conn.commit()
        grupo_destino = cur.lastrowid
        print(f"   Grupo novo criado: '{nome}' (ID {grupo_destino})")
        print("   Vincule seu e-mail a ele na tela de Administração para enxergar os dados.")
    else:
        print(f"   Gravando dentro do grupo existente ID {grupo_destino}")

    de_para = {"categorias": mapear_categorias(conn, tabelas.get("categorias", []))}

    for tabela in ORDEM:
        linhas = tabelas.get(tabela, [])
        if not linhas:
            continue
        de_para[tabela] = {}
        for linha in linhas:
            linha = dict(linha)
            id_antigo = linha.pop("id", None)

            for coluna, alvo in CHAVES_ESTRANGEIRAS.get(tabela, {}).items():
                if linha.get(coluna) is not None:
                    # Se o alvo não veio no backup, deixa nulo em vez de apontar
                    # para um ID de outro grupo — melhor um campo vazio do que
                    # um lançamento pendurado na conta de outra família.
                    linha[coluna] = de_para.get(alvo, {}).get(linha[coluna])

            if "grupo_id" in linha:
                linha["grupo_id"] = grupo_destino

            colunas = ", ".join(linha.keys())
            marcadores = ", ".join("?" for _ in linha)
            cur = conn.execute(
                f"INSERT INTO {tabela} ({colunas}) VALUES ({marcadores})",
                tuple(linha.values()),
            )
            de_para[tabela][id_antigo] = cur.lastrowid

        conn.commit()
        print(f"   {tabela:20} {len(linhas)} linha(s) restaurada(s)")

    print(f"\nPronto. Os dados estão no grupo ID {grupo_destino}.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Restaura um backup do Casa Capital.")
    p.add_argument("arquivo", help="backup-completo.json ou o .zip baixado")
    p.add_argument("--aplicar", action="store_true", help="grava de verdade (sem isto, só simula)")
    p.add_argument("--grupo", type=int, default=None,
                   help="ID de um grupo existente. Sem isto, cria um grupo novo.")
    args = p.parse_args()

    restaurar(args.arquivo, aplicar=args.aplicar, grupo_destino=args.grupo)
    sys.stdout.flush()
    os._exit(0)
