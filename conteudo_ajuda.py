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
        "topicos": [
            {"titulo": "Ler a projeção e achar o dia do aperto",
             "texto": "A projeção parte do saldo de hoje e vai somando o que está marcado. "
                      "O aviso vermelho mostra **o dia em que o saldo fura o zero** — é o que "
                      "dá tempo de antecipar recebimento, adiar saída ou resgatar aplicação.\n\n"
                      "Conta vencida e não paga pesa no primeiro dia: ela ainda vai sair.",
             "video": ""},
            {"titulo": "Por que Aplicações não entram no disponível",
             "texto": "Disponível é o que paga a conta desta semana: Caixa + Bancos. "
                      "Aplicação nem sempre resgata no mesmo dia, e somar as duas coisas faz "
                      "você achar que tem dinheiro que não está à mão.",
             "video": ""},
            {"titulo": "Importar o extrato sem duplicar",
             "texto": "O extrato **confirma**, não lança de novo. Linha que bate com uma conta "
                      "já cadastrada vira baixa; linha que é pagamento de fatura dá as compras "
                      "daquele cartão por pagas; só o que não bate com nada vira lançamento novo.\n\n"
                      "Pode subir o mesmo arquivo quantas vezes quiser.",
             "video": ""},
        ],
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
        "topicos": [
            {"titulo": "Compra parcelada",
             "texto": "Informe o **valor total** e o número de parcelas. O sistema cria uma "
                      "parcela por mês, já numerada (1/6, 2/6…). Não divida na mão.",
             "video": ""},
            {"titulo": "Por que a data no fluxo de caixa é outra",
             "texto": "A compra é **despesa** no dia em que você comprou — é assim que ela conta "
                      "na análise por categoria. Mas o **dinheiro** só sai no vencimento da "
                      "fatura, e é essa data que aparece na projeção.\n\n"
                      "Compra feita **no dia** do fechamento já entra na fatura seguinte: um dia "
                      "de diferença, um mês de diferença no caixa.",
             "video": ""},
        ],
    },

    "Patrimônio": {
        "texto": """
O longo prazo, em três seções.

**💼 Bens e dívidas** — o que você tem e o que deve. Bens menos dívidas, mais
o saldo em contas e investimentos, dá o **patrimônio líquido**.

**💹 Investimentos** — a carteira: quanto aportou, quanto vale hoje, e a
rentabilidade. O valor atual você atualiza na mão; não há integração com
corretora.

**🎯 Metas** — objetivos com valor e prazo, com a barra de quanto falta.

Estão juntos porque são o mesmo dinheiro em três tempos: o que já é seu, o que
está rendendo, e o que você quer que seja.

Enquanto o Fluxo de Caixa cuida do mês, aqui é o acúmulo.
""",
        "video": "",
        "topicos": [
            {"titulo": "Como o patrimônio líquido é calculado",
             "texto": "Bens + investimentos + saldo em contas − dívidas.\n\n"
                      "Cartão de crédito não entra como conta: ele é dívida, e o que você "
                      "deve nele aparece pelas compras lançadas.",
             "video": ""},
            {"titulo": "Atualizar valor de bem e de investimento",
             "texto": "Imóvel, carro e carteira mudam de preço. Atualize de tempos em tempos, "
                      "senão o patrimônio líquido congela num valor antigo e as decisões saem "
                      "de uma foto vencida.",
             "video": ""},
            {"titulo": "Usar metas de verdade",
             "texto": "Meta é patrimônio futuro. Cadastre valor e prazo, e acompanhe a barra.\n\n"
                      "Guardar dinheiro para a meta é lançamento normal — o sistema não separa "
                      "o dinheiro numa conta à parte.",
             "video": ""},
        ],
    },

    "Foto do Cupom": {
        "texto": """
Fotografe o **cupom fiscal** ou o **canhoto da maquininha** e o sistema lê o
valor, a data e o estabelecimento. Pelo celular a câmera abre direto; pelo
computador dá para enviar a imagem.

**Confira antes de lançar.** Valor lido errado não dá erro — dá um número
parecido, que entra no caixa sem ninguém notar. Por isso os campos vêm
preenchidos, mas editáveis, com a foto do lado.

**Débito e crédito não são a mesma coisa:**

- **débito** (e Pix, e dinheiro) — o dinheiro sai da conta na data da compra
- **crédito** — a compra entra na fatura do cartão e o dinheiro só sai no
  vencimento; a despesa conta hoje, o caixa sente depois

Se o canhoto não disser qual dos dois foi, a tela pergunta em vez de chutar:
errar entre eles desloca a saída em até um mês na projeção.

E se já existir uma conta a pagar do mesmo valor por perto, ela oferece dar
baixa nela em vez de criar outra — a mesma regra do extrato.

A foto fica anexada ao lançamento, como comprovante.
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
        "topicos": [
            {"titulo": "Cadastrar um cartão",
             "texto": "Cartão precisa de **fechamento**, **vencimento** e **limite** — por isso "
                      "não é cadastrado junto com conta comum. Esses dois dias são o que "
                      "determina em que fatura cada compra cai.",
             "video": ""},
            {"titulo": "Criar categoria própria",
             "texto": "As de fábrica valem para todo mundo e não podem ser apagadas. As que "
                      "você criar são só do seu grupo.\n\n"
                      "Categoria em uso não é apagada: os lançamentos ficariam apontando para "
                      "o nada e o total pararia de somar sem avisar.",
             "video": ""},
            {"titulo": "Fazer e restaurar backup",
             "texto": "O `.zip` traz uma planilha por tabela (abre no Excel) e um JSON que o "
                      "sistema lê de volta. Baixe de vez em quando: seus dados moram num "
                      "serviço gratuito.",
             "video": ""},
        ],
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
        "topicos": [
            {"titulo": "Liberar acesso para alguém",
             "texto": "Cadastre o e-mail em **Adicionar membro** e pronto. A pessoa entra com a "
                      "conta Google dela no primeiro acesso — sem mexer em configuração nem "
                      "reiniciar o sistema.\n\n"
                      "Quem não está vinculado a nenhum grupo não vê tela nenhuma.",
             "video": ""},
        ],
    },
}


def para(titulo):
    """Ajuda de uma tela, ou None se ela ainda não tem texto."""
    return AJUDA.get(titulo)


def topicos(titulo):
    """Assuntos da tela. Cada um pode ter vídeo próprio — é o que permite ligar
    um vídeo a uma dica específica em vez de um só para a tela inteira."""
    return (AJUDA.get(titulo) or {}).get("topicos", [])


def chave_video(titulo, topico=None):
    """Identificador do vídeo no banco. Tela sozinha, ou tela + assunto."""
    return f"{titulo} :: {topico}" if topico else titulo


def tudo_que_aceita_video(titulo):
    """[(rótulo, chave)] de tudo que pode ter vídeo nesta tela."""
    itens = [("Visão geral da tela", chave_video(titulo))]
    itens += [(t["titulo"], chave_video(titulo, t["titulo"])) for t in topicos(titulo)]
    return itens
