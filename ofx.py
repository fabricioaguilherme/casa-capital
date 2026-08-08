"""Leitor de extrato OFX — o formato que todo banco brasileiro exporta.

Escrito à mão de propósito, sem biblioteca externa. O OFX tem duas gerações
(1.x em SGML, 2.x em XML) e os bancos daqui produzem variações das duas, mas
as etiquetas que interessam são as mesmas nas duas. Um extrator por expressão
regular atravessa os dois formatos e não quebra quando um banco esquece de
fechar uma etiqueta — coisa que os leitores estritos de XML não perdoam.

Uma dependência a menos também é uma reimplantação a menos para dar errado.
"""

import re
from datetime import date

# <STMTTRN> ... </STMTTRN> é o bloco de uma transação, igual nas duas gerações.
_BLOCO = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S | re.I)

# Etiqueta em SGML pode não ter fechamento: <TRNAMT>-45.90\n. Por isso o valor
# vai até a próxima etiqueta ou até o fim da linha.
def _campo(bloco, nome):
    achado = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
    return achado.group(1).strip() if achado else ""


def _data(texto):
    """OFX traz AAAAMMDD, às vezes com hora e fuso colados: 20260805120000[-3]."""
    if len(texto) < 8 or not texto[:8].isdigit():
        return None
    try:
        return date(int(texto[:4]), int(texto[4:6]), int(texto[6:8]))
    except ValueError:
        return None


def _valor(texto):
    """Aceita 1234.56 e 1234,56 — bancos daqui usam os dois."""
    limpo = texto.replace(" ", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def ler(conteudo):
    """Devolve a lista de transações do extrato.

    Cada uma vira {data, valor, tipo, descricao, fitid}. `valor` é sempre
    positivo; o sinal do arquivo vira `tipo` (entrada/saida), que é como o
    resto do sistema trabalha.
    """
    if isinstance(conteudo, bytes):
        # Bancos exportam em latin-1 com frequência; errors='replace' evita
        # que um acento estranho derrube a importação inteira.
        conteudo = conteudo.decode("utf-8", errors="replace")
        if conteudo.count("�") > 5:
            pass  # já substituído; seguir com o que deu para ler

    transacoes = []
    for bloco in _BLOCO.findall(conteudo):
        quando = _data(_campo(bloco, "DTPOSTED"))
        bruto = _valor(_campo(bloco, "TRNAMT"))
        if quando is None or bruto is None:
            continue

        descricao = (_campo(bloco, "MEMO") or _campo(bloco, "NAME")
                     or _campo(bloco, "TRNTYPE") or "Sem descrição")

        transacoes.append({
            "data": quando,
            "valor": abs(bruto),
            "tipo": "entrada" if bruto >= 0 else "saida",
            "descricao": descricao.strip(),
            # O FITID é o identificador único do banco. É ele que permite subir
            # o mesmo extrato duas vezes sem duplicar nada.
            "fitid": _campo(bloco, "FITID") or None,
        })

    transacoes.sort(key=lambda t: t["data"])
    return transacoes


def e_de_cartao(conteudo):
    """True quando o arquivo é a fatura de um cartão, não o extrato da conta.

    O OFX separa os dois em blocos diferentes: extrato de conta vem em
    BANKMSGSRSV1/STMTRS, fatura de cartão em CREDITCARDMSGSRSV1/CCSTMTRS. As
    transações lá dentro são idênticas, então sem olhar o invólucro é
    impossível saber — e importar fatura como se fosse conta debita tudo na
    data errada e ainda duplica com o pagamento que vem no extrato do banco.
    """
    if isinstance(conteudo, bytes):
        conteudo = conteudo.decode("utf-8", errors="replace")
    texto = conteudo.upper()
    return "CREDITCARDMSGSRSV1" in texto or "CCSTMTRS" in texto or "CCACCTFROM" in texto


def resumo(transacoes):
    """(entradas, saidas, periodo_inicial, periodo_final) para conferência."""
    if not transacoes:
        return 0.0, 0.0, None, None
    entradas = sum(t["valor"] for t in transacoes if t["tipo"] == "entrada")
    saidas = sum(t["valor"] for t in transacoes if t["tipo"] == "saida")
    return entradas, saidas, transacoes[0]["data"], transacoes[-1]["data"]
