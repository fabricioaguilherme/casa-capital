"""Textos e vídeos de ajuda de cada tela.

Fica separado da interface de propósito: mexer num texto ou colar o link de um
vídeo novo não deve exigir abrir código de tela. A chave é o título da página,
igual ao que está no menu do `app.py`.

Para acrescentar um vídeo, cole o endereço do YouTube em `video`. Enquanto
estiver vazio, a ajuda mostra só o texto — nada quebra.

Grave os vídeos como **não listados** e com dados de teste: quem tiver o link
assiste, e você não quer o patrimônio real da família num tutorial.
"""

AJUDA = {
    "Dashboard": {
        "texto": """
Visão geral do mês: quanto você tem, o que já entrou e saiu, e o que ainda
vem pela frente.

Os números de saldo contam só o que está **pago**. O que está pendente
aparece separado, como previsão.
""",
        "video": "",
    },

    "Fluxo de Caixa": {
        "texto": """
Quatro perguntas, quatro visões:

**📊 Saldo atual** — onde o dinheiro está parado hoje, separado em Caixa,
Bancos e Aplicações. Aplicações ficam fora do "disponível" porque nem sempre
dá para resgatar na hora.

**📉 Previsto × Realizado** — como os meses se comportaram e o que ainda está
marcado. A barra cheia é o que já aconteceu; a mais clara, o que falta.

**📈 Projeção** — como o saldo termina, e **em que dia ele fura o zero**. É a
informação que muda decisão.

**📋 Lançamentos** — a lista. O lançamento avulso aqui é exceção: o caminho
normal é A Pagar / A Receber, senão a projeção fica cega.

**📥 Importar extrato** — sobe o OFX do banco e concilia com o que você já
lançou.
""",
        "video": "",
    },

    "Contas a Pagar": {
        "texto": """
Tudo que vai sair da conta e ainda não saiu. Cadastre aqui, não no Fluxo de
Caixa — é o que faz a projeção enxergar o compromisso.

**Repetir (meses)** cria a mesma conta pelos próximos meses de uma vez.

Conta vencida e não paga continua contando na previsão: ela ainda vai sair.
""",
        "video": "",
    },

    "Contas a Receber": {
        "texto": """
Tudo que vai entrar e ainda não entrou. Mesma lógica do A Pagar.

Marcar como recebido move o valor para o saldo — antes disso ele é só
previsão.
""",
        "video": "",
    },

    "Cartão de Crédito": {
        "texto": """
Aqui você lança **compras** e vê as **faturas**. O cadastro do cartão fica em
Cadastros.

A compra parcelada vira uma parcela por mês automaticamente, já numerada.

**A parte que confunde:** a compra é despesa no dia em que você comprou, mas o
dinheiro só sai no **vencimento da fatura**. Por isso ela aparece no mês da
compra na análise por categoria, e na data da fatura no fluxo de caixa. São as
duas coisas certas, em lugares diferentes.

Compra feita **no dia** do fechamento já entra na fatura seguinte.
""",
        "video": "",
    },

    "Patrimônio": {
        "texto": """
O que você tem e o que você deve. Bens menos dívidas, mais o saldo em contas e
investimentos, dá o patrimônio líquido.

Atualize os valores de tempos em tempos — imóvel e carro mudam de preço.
""",
        "video": "",
    },

    "Investimentos": {
        "texto": """
Sua carteira: quanto aportou, quanto vale hoje, e a rentabilidade.

O valor atual você atualiza na mão. Não há integração com corretora.
""",
        "video": "",
    },

    "Metas": {
        "texto": """
Objetivos com valor e prazo. A barra mostra quanto falta.

Serve para o que você está juntando dinheiro: viagem, reserva, entrada de
imóvel.
""",
        "video": "",
    },

    "Importar extrato (dentro do Fluxo de Caixa)": {
        "texto": """
Suba o arquivo **OFX** que o banco exporta e o sistema compara com o que você
já lançou.

A regra é **confirmar, não duplicar**:

- linha que bate com uma conta já cadastrada → marca como paga
- linha que é pagamento de fatura → dá as compras daquele cartão por pagas
- linha que não bate com nada → aí sim vira lançamento novo

Nada é gravado sem você confirmar. Pode subir o mesmo extrato de novo: o que
já entrou é reconhecido e ignorado.
""",
        "video": "",
    },

    "Configurações": {
        "texto": """
Reúne o que não é do dia a dia:

**📋 Cadastros** — contas, cartões, categorias e formas de pagamento. É o
único lugar onde se cria coisa; as telas de operação só usam o que existe.

**💾 Backup** — baixe uma cópia de tudo.

**❔ Ajuda** — a explicação de todas as telas, junta.
""",
        "video": "",
    },

    "Backup": {
        "texto": """
Baixe uma cópia de tudo num arquivo `.zip`: uma planilha por tabela para abrir
no Excel, e um JSON que o sistema sabe ler de volta.

Faça de vez em quando. Seus dados moram num serviço gratuito — o backup é o
que garante que eles continuam seus.

O backup guarda a **ficha** dos anexos, não os arquivos.
""",
        "video": "",
    },

    "Cadastros": {
        "texto": """
O único lugar onde se cria coisa: contas, cartões, categorias e formas de
pagamento. As telas do dia a dia só usam o que existe aqui.

**Cartão não é cadastrado junto com conta** porque precisa de fechamento,
vencimento e limite.

Categoria e forma de pagamento **de fábrica** não podem ser apagadas — elas
valem para todo mundo. As que você criar são só suas.

Categoria em uso não é apagada: os lançamentos ficariam apontando para o nada.
""",
        "video": "",
    },

    "Administração": {
        "texto": """
Grupo e membros. Cada família é um grupo, e **um grupo nunca vê os dados do
outro**.

Para liberar alguém: cadastre o e-mail aqui e pronto. A pessoa entra com a
conta Google dela no primeiro acesso — não precisa mexer em configuração nem
reiniciar o sistema.

**Admin** manda no próprio grupo. Criar grupos novos é só para o dono.
""",
        "video": "",
    },
}


def para(titulo):
    """Ajuda de uma tela, ou None se ela ainda não tem texto."""
    return AJUDA.get(titulo)
