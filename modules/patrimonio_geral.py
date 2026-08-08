"""Patrimônio — o longo prazo, reunido.

Roteador fino, como o de Configurações: bens/dívidas, investimentos e metas
continuam cada um no módulo seu, e este arquivo só decide qual chamar.

Estão juntos porque falam do mesmo dinheiro em três tempos: o que já é seu
(bens), o que está rendendo (investimentos) e o que você quer que seja (metas).
O `patrimonio.py` inclusive já somava os investimentos no líquido — as telas
eram separadas, os números não.

A divisão do sistema fica assim: **Fluxo de Caixa** é o curto prazo (o mês),
**Patrimônio** é o acúmulo.
"""

import streamlit as st

from modules import investimentos, metas, patrimonio

SECOES = ["💼  Bens e dívidas", "💹  Investimentos", "🎯  Metas"]


def render(conn, usuario):
    secao = st.radio("Seção", SECOES, horizontal=True, key="patr_secao",
                     label_visibility="collapsed")
    st.divider()

    if secao == SECOES[0]:
        patrimonio.render(conn, usuario)
    elif secao == SECOES[1]:
        investimentos.render(conn, usuario)
    else:
        metas.render(conn, usuario)
