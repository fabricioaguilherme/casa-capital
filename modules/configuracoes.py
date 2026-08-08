"""Configurações — reúne o que não é operação do dia a dia.

Roteador fino de propósito: cada seção continua no módulo dela (`cadastros`,
`backup`, `ajuda`) e este arquivo só decide qual chamar. Assim o menu encurta
sem que as áreas percam a independência — mexer em Backup continua sendo abrir
`backup.py`, e nada mais.
"""

import streamlit as st

from modules import ajuda, backup, cadastros

SECOES = ["📋  Cadastros", "💾  Backup", "❔  Ajuda"]


def render(conn, usuario):
    secao = st.radio("Seção", SECOES, horizontal=True, key="config_secao",
                     label_visibility="collapsed")
    st.divider()

    if secao == SECOES[0]:
        cadastros.render(conn, usuario)
    elif secao == SECOES[1]:
        backup.render(conn, usuario)
    else:
        ajuda.render(conn, usuario)
