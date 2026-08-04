"""Backup e exportação dos dados do grupo.

Existe por um motivo simples: os dados moram num banco na nuvem de plano
gratuito. Se a conta do Turso sumir, se o serviço mudar de regra, ou se um dia
você quiser sair, é preciso ter os números na mão sem depender de ninguém.

Dois formatos, propósitos diferentes:

- CSV: abre no Excel, serve para conferir e trabalhar os números.
- JSON: guarda tudo junto, inclusive as ligações entre as tabelas. É o formato
  que `restaurar_backup.py` sabe ler para reconstruir o banco.
"""

import io
import json
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st

import theme

# Cada tabela e como buscar as linhas do grupo. As tabelas ligadas a uma conta
# (cartoes) e as fichas de anexo entram pela conta/grupo, não por coluna direta.
CONSULTAS = {
    "contas": "SELECT * FROM contas WHERE grupo_id = ?",
    "lancamentos": "SELECT * FROM lancamentos WHERE grupo_id = ?",
    "patrimonio_itens": "SELECT * FROM patrimonio_itens WHERE grupo_id = ?",
    "investimentos": "SELECT * FROM investimentos WHERE grupo_id = ?",
    "metas": "SELECT * FROM metas WHERE grupo_id = ?",
    "anexos": "SELECT * FROM anexos WHERE grupo_id = ?",
    "cartoes": (
        "SELECT cartoes.* FROM cartoes "
        "JOIN contas ON contas.id = cartoes.conta_id WHERE contas.grupo_id = ?"
    ),
}

# Categorias não pertencem a grupo nenhum (são a lista padrão do sistema), mas
# entram no backup porque os lançamentos apontam para elas.
CONSULTA_CATEGORIAS = "SELECT * FROM categorias"

ROTULOS = {
    "contas": "Contas",
    "lancamentos": "Lançamentos",
    "patrimonio_itens": "Patrimônio",
    "investimentos": "Investimentos",
    "metas": "Metas",
    "anexos": "Fichas de anexo",
    "cartoes": "Cartões",
    "categorias": "Categorias",
}


def _coletar(conn, grupo_id):
    """Lê todas as tabelas do grupo e devolve {tabela: [linhas]}."""
    dados = {}
    for tabela, sql in CONSULTAS.items():
        linhas = conn.execute(sql, (grupo_id,)).fetchall()
        dados[tabela] = [dict(linha) for linha in linhas]
    dados["categorias"] = [dict(linha) for linha in conn.execute(CONSULTA_CATEGORIAS).fetchall()]
    return dados


def _montar_zip(dados, grupo_nome, grupo_id):
    """Um único arquivo .zip com os CSVs e o JSON completo dentro."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for tabela, linhas in dados.items():
            if not linhas:
                continue
            csv = pd.DataFrame(linhas).to_csv(index=False)
            # utf-8-sig para o Excel do Windows não estragar os acentos
            z.writestr(f"csv/{tabela}.csv", csv.encode("utf-8-sig"))

        completo = {
            "formato": "casa-capital-backup",
            "versao": 1,
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "grupo": {"id": grupo_id, "nome": grupo_nome},
            "tabelas": dados,
        }
        z.writestr(
            "backup-completo.json",
            json.dumps(completo, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        )
        z.writestr("LEIA-ME.txt", _leia_me(grupo_nome).encode("utf-8"))

    buffer.seek(0)
    return buffer.getvalue()


def _leia_me(grupo_nome):
    return (
        "BACKUP CASA CAPITAL\n"
        "===================\n\n"
        f"Grupo: {grupo_nome}\n"
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}\n\n"
        "O que tem aqui dentro\n"
        "---------------------\n"
        "csv/                 uma planilha por tabela. Abre direto no Excel.\n"
        "backup-completo.json todos os dados juntos, com as ligações entre as\n"
        "                     tabelas preservadas.\n\n"
        "Como voltar com esses dados\n"
        "---------------------------\n"
        "Use o backup-completo.json (os CSVs perdem as ligações entre tabelas):\n\n"
        "    python3 restaurar_backup.py backup-completo.json\n\n"
        "O comando acima só mostra o que faria. Para gravar de verdade, repita\n"
        "com --aplicar no final.\n\n"
        "Anexos\n"
        "------\n"
        "Este backup traz a ficha dos anexos (nome, data, tamanho), não os\n"
        "arquivos em si. Guarde os originais por sua conta.\n"
    )


def render(conn, usuario):
    grupo_id = usuario["grupo_id"]
    grupo_nome = usuario.get("grupo_nome") or f"Grupo {grupo_id}"

    st.markdown(
        "Seus dados ficam num banco na nuvem de plano gratuito. Baixe uma cópia "
        "de vez em quando — é o que garante que eles continuam seus mesmo que o "
        "serviço saia do ar."
    )

    dados = _coletar(conn, grupo_id)
    total = sum(len(v) for k, v in dados.items() if k != "categorias")

    st.markdown("#### O que vai no backup")
    with st.container(border=True):
        colunas = st.columns(4)
        for i, (tabela, linhas) in enumerate(dados.items()):
            colunas[i % 4].metric(ROTULOS.get(tabela, tabela), len(linhas))

    if total == 0:
        st.info("Ainda não há dados para exportar.")
        return

    conteudo = _montar_zip(dados, grupo_nome, grupo_id)
    nome_arquivo = f"casa-capital-backup-{datetime.now().strftime('%Y-%m-%d')}.zip"

    st.markdown("#### Baixar")
    with st.container(border=True):
        st.download_button(
            "⬇️  Baixar backup completo (.zip)",
            data=conteudo,
            file_name=nome_arquivo,
            mime="application/zip",
            use_container_width=True,
            type="primary",
        )
        st.caption(
            f"{total} registro(s) · planilhas em CSV para o Excel e um JSON "
            "que o `restaurar_backup.py` sabe ler de volta."
        )

    st.markdown("#### Conferir antes de baixar")
    tabela_escolhida = st.selectbox(
        "Tabela",
        [t for t in dados if dados[t]],
        format_func=lambda t: f"{ROTULOS.get(t, t)} ({len(dados[t])})",
    )
    st.dataframe(pd.DataFrame(dados[tabela_escolhida]), use_container_width=True, height=320)

    st.caption(
        "O backup guarda a ficha dos anexos (nome, data, tamanho), não os arquivos. "
        "Enquanto o armazenamento definitivo não fica pronto, guarde os originais "
        "no seu computador."
    )
