"""teste_cupom.py — a leitura do cupom não pode inventar número.

    python3 teste_cupom.py

Não chama a API: o que se testa aqui é a **interpretação** da resposta, que é
onde o erro passa despercebido. Valor lido errado não dá exceção — dá um
número plausível, que entra no fluxo de caixa e ninguém confere.

Cobre também o caminho débito × crédito no banco, porque é o que muda o dia
em que o dinheiro sai: débito hoje, crédito no vencimento da fatura.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cupom  # noqa: E402
import database as db  # noqa: E402
from modules import cupom_foto  # noqa: E402

HOJE = date(2026, 8, 8)


def _conferir(rotulo, obtido, esperado, falhas):
    ok = obtido == esperado
    print(f"  {rotulo}: {obtido!r} (esperado {esperado!r})   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append(f"{rotulo}: veio {obtido!r}, esperado {esperado!r}")


def leitura():
    falhas = []
    print("Interpretação da resposta do modelo:")

    # Formato brasileiro, embrulhado em cerca de código, com frase antes.
    bruto = """Claro! Aqui está:
```json
{"valor": "R$ 1.234,56", "data": "2026-08-07", "estabelecimento": "SUPERMERCADO EXTRA",
 "forma": "CRÉDITO", "parcelas": "3", "observacao": "VISA ****1234", "confianca": "alta"}
```"""
    lido = cupom.interpretar(bruto, HOJE)
    _conferir("valor brasileiro", lido["valor"], 1234.56, falhas)
    _conferir("data", lido["data"], date(2026, 8, 7), falhas)
    _conferir("parcelas em texto", lido["parcelas"], 3, falhas)
    # Acento e caixa são reconhecidos: o canhoto imprime "CRÉDITO".
    _conferir("CRÉDITO com acento", lido["forma"], "credito", falhas)

    for escrito, esperado in (("CARTÃO DE CRÉDITO", "credito"), ("Débito à vista", "debito"),
                              ("PIX", "pix"), ("", "desconhecido"), ("vale-refeição", "desconhecido")):
        obtido = cupom.interpretar(
            '{"valor": 10, "forma": "%s"}' % escrito, HOJE)["forma"]
        ok = obtido == esperado
        print(f"  forma {escrito!r} -> {obtido!r}   {'ok' if ok else 'ERRADO'}")
        if not ok:
            falhas.append(f"forma {escrito!r} virou {obtido!r}, esperado {esperado!r}")

    # Número simples, sem cerca, com texto em volta.
    lido = cupom.interpretar(
        'A leitura deu: {"valor": 45.9, "data": "2026-08-08", '
        '"estabelecimento": "PADARIA", "forma": "debito", "confianca": "media"}', HOJE)
    _conferir("valor simples", lido["valor"], 45.9, falhas)
    _conferir("débito", lido["forma"], "debito", falhas)
    _conferir("parcelas ausente", lido["parcelas"], 1, falhas)

    print("\nDatas implausíveis viram vazio (a tela usa hoje):")
    for texto, motivo in ((f'{{"valor": 10, "data": "2020-01-05", "forma": "debito"}}', "década errada"),
                          (f'{{"valor": 10, "data": "2027-01-05", "forma": "debito"}}', "no futuro")):
        lido = cupom.interpretar(texto, HOJE)
        ok = lido["data"] is None
        print(f"  {motivo}: {lido['data']}   {'ok' if ok else 'ERRADO'}")
        if not ok:
            falhas.append(f"data {motivo} foi aceita")

    print("\nRecusas:")
    for texto, motivo in (('{"erro": "não é um comprovante"}', "não é comprovante"),
                          ('{"valor": 0, "forma": "debito"}', "valor zero"),
                          ('{"valor": null, "forma": "debito"}', "sem valor"),
                          ("desculpe, não consegui", "resposta sem JSON")):
        try:
            cupom.interpretar(texto, HOJE)
            print(f"  {motivo}: ACEITOU   ERRADO")
            falhas.append(f"aceitou {motivo}")
        except cupom.CupomIlegivel:
            print(f"  {motivo}: recusou   ok")

    return falhas


def debito_e_credito():
    """A mesma compra, nas duas formas, sai do caixa em dias diferentes."""
    falhas = []
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-cup-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    db.init_db(conn)

    hoje = date.today()
    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 5000.0, grupo_id=grupo)
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]
    fecha, vence = (hoje + timedelta(days=6)).day, (hoje + timedelta(days=21)).day
    cartao = db.criar_cartao(conn, "Nubank", fecha, vence, 9000.0, grupo_id=grupo)

    print("\nDébito × crédito (R$ 200 no mesmo dia):")

    # Débito: já saiu.
    db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, "Padaria (débito)",
                        200.0, "saida", "pago", 1, forma_pagamento="Débito", grupo_id=grupo)
    # Crédito: entra na fatura.
    db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, "Padaria (crédito)",
                        200.0, "saida", "pendente", 1, cartao_id=cartao,
                        forma_pagamento="Crédito", grupo_id=grupo)

    pendentes = db.pendentes_em_caixa(conn, grupo_id=grupo)
    _, vencimento = db.ciclo_fatura(hoje.isoformat(), fecha, vence)

    do_cartao = [p for p in pendentes if p["cartao_id"] == cartao]
    ok = len(do_cartao) == 1 and do_cartao[0]["data_caixa"] == vencimento
    print(f"  crédito sai em {do_cartao[0]['data_caixa'] if do_cartao else '—'} "
          f"(esperado {vencimento})   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("compra no crédito não foi para o vencimento da fatura")

    # O débito não pode aparecer como pendente: ele já saiu.
    ok = not [p for p in pendentes if p["cartao_id"] is None]
    print(f"  débito fora dos pendentes: {ok}   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("compra no débito ficou pendente — ela já saiu da conta")

    # E o saldo de hoje já sentiu só o débito.
    saldo = db.saldo_total(conn, grupo_id=grupo)
    ok = abs(saldo - 4800.0) < 0.01
    print(f"  saldo hoje: {saldo:.2f} (esperado 4800,00)   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append(f"saldo {saldo}, esperado 4800 — o crédito não podia ter saído ainda")

    conn.close()
    return falhas


def foto_vira_anexo():
    """A foto tem de ficar presa ao lançamento certo — inclusive parcelado."""
    import storage
    falhas = []
    caminho = os.path.join(tempfile.mkdtemp(prefix="casacapital-anx-"), "teste.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = lambda cur, row: {c[0]: row[i] for i, c in enumerate(cur.description)}
    db.init_db(conn)

    hoje = date.today()
    grupo = db.criar_grupo(conn, "Família Teste")
    conta = db.criar_conta(conn, "Banco", "banco", 3000.0, grupo_id=grupo)
    despesa = db.listar_categorias(conn, tipo="despesa", grupo_id=grupo)[0]["id"]
    cartao = db.criar_cartao(conn, "Nubank", 25, 5, 9000.0, grupo_id=grupo)

    print("\nFoto anexada ao lançamento:")

    # Compra parcelada em 3: nascem 3 lançamentos, a foto vai no primeiro.
    db.criar_lancamento(conn, hoje.isoformat(), conta, despesa, "Loja",
                        300.0, "saida", "pendente", 1, cartao_id=cartao,
                        parcelas=3, grupo_id=grupo)
    ids = cupom_foto._ultimos_ids(conn, grupo, 3)
    ok = len(ids) == 3
    print(f"  parcelado em 3 gerou {len(ids)} lançamento(s)   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append(f"parcelamento gerou {len(ids)} lançamentos, esperado 3")

    # A foto é da compra: pertence à parcela 1, não à última.
    primeira = conn.execute("SELECT descricao FROM lancamentos WHERE id = ?",
                            (ids[0],)).fetchone()["descricao"]
    ok = primeira.endswith("(1/3)")
    print(f"  o comprovante vai para {primeira!r}   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append(f"a foto iria para {primeira!r} em vez da parcela 1")

    armazenamento = storage.ArmazenamentoLocal(
        raiz=os.path.join(os.path.dirname(caminho), "anexos"))
    dados = b"foto-de-mentira"
    chave = armazenamento.salvar(dados, "cupom.jpg")
    anexo_id = db.criar_anexo(conn, "lancamento", ids[0], "cupom.jpg", chave,
                              armazenamento.nome, "image/jpeg", len(dados),
                              storage.hash_conteudo(dados), 1, grupo_id=grupo)
    presos = db.listar_anexos(conn, "lancamento", ids[0])
    ok = len(presos) == 1 and presos[0]["id"] == anexo_id
    print(f"  anexo ligado ao lançamento: {len(presos)}   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("a foto não ficou ligada ao lançamento")

    ok = armazenamento.ler(chave) == dados
    print(f"  arquivo lido de volta igual: {ok}   {'ok' if ok else 'ERRADO'}")
    if not ok:
        falhas.append("o arquivo salvo não voltou igual")

    conn.close()
    return falhas


if __name__ == "__main__":
    problemas = leitura() + debito_e_credito() + foto_vira_anexo()
    if problemas:
        print("\nFALHOU:\n  " + "\n  ".join(problemas))
    else:
        print("\nOK — leitura conferida, débito e crédito saem em dias diferentes,")
        print("     e a foto fica presa ao lançamento.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
