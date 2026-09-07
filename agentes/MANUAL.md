# Manual da Estrutura de Agentes

Como montar, ensinar e cobrar uma equipe de agentes que ajuda a tocar a empresa.

Este arquivo é a doutrina. Os agentes que rodam de verdade estão em `.claude/agents/`.
Os contratos de meta de cada área estão em `agentes/contratos/`.
O que o sistema aprendeu está em `agentes/registro/`.

---

## 1. Não copie o organograma

O organograma humano existe por três limitações que o agente não tem:

- um gerente só consegue acompanhar umas 7 pessoas
- reunião custa caro, então a informação sobe e desce em degraus
- as pessoas precisam de cargo, carreira e status

Agente não tem nenhuma das três. Mas tem uma limitação que gente não tem: **ele
só enxerga o que está na frente dele naquele momento.** Contexto demais piora a
resposta tanto quanto contexto de menos.

Então a hierarquia não desaparece — ela muda de função. Ela deixa de existir para
dar permissão e passa a existir para **filtrar o que chega em você e para dizer
de quem é a culpa quando dá errado.**

A unidade da estrutura não é o departamento. É o **ciclo de decisão que se repete**.
Comece perguntando "que decisões eu tomo toda semana?", não "que áreas eu tenho?".

---

## 2. As quatro camadas

```
                    ┌─────────────┐
                    │    VOCÊ     │  decide o irreversível, define a meta,
                    └──────┬──────┘  corrige o manual quando erra
                           │  escalação com recomendação
                    ┌──────┴──────┐
                    │   DIRETOR   │  prioriza, resolve conflito entre áreas,
                    └──────┬──────┘  cobra meta, NÃO executa
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴────┐ ┌─────┴────┐ ┌─────┴────┐
        │ FINANCEI │ │ COMERCIAL│ │ OPERAÇÃO │   especialistas: fundos,
        └─────┬────┘ └─────┬────┘ └─────┬────┘   estreitos, sem autonomia
              │            │            │         de decisão
              └────────────┼────────────┘
                    ┌──────┴──────┐
                    │ CONTRADITOR │  tenta derrubar a conclusão
                    └──────┬──────┘  antes de ela virar decisão
                           │
              ╔════════════╧════════════╗
              ║   FONTE DA VERDADE      ║  banco, planilha, contrato.
              ║   (dado, não agente)    ║  todo mundo lê o mesmo número
              ╚═════════════════════════╝
                           │
                    ┌──────┴──────┐
                    │   CRONISTA  │  registra decisão e erro —
                    └─────────────┘  é assim que o sistema aprende
```

**Camada 1 — Fonte da verdade.** Não é agente, é dado. É a camada que todo mundo
pula e é a que mais quebra o sistema. Se o agente de finanças e o de vendas
respondem com números diferentes para a mesma pergunta, nada mais importa. Aqui
a fonte é o banco (`database.py` / Turso) mais os contratos escritos.

**Camada 2 — Especialistas.** Fazem o trabalho. Escopo estreito, método escrito,
acesso à fonte. **Não decidem.** Entregam análise, evidência e proposta.

**Camada 3 — Diretor.** Enxerga as áreas juntas, segura as metas, resolve
conflito, decide o que é reversível e escala o resto. Não executa — no minuto em
que ele começa a fazer a análise no lugar do especialista, some a rastreabilidade
e a qualidade cai.

**Camada 4 — Transversais.** Duas funções que não existem no organograma
tradicional e que aqui são obrigatórias:

- **Contraditor** — o único trabalho dele é tentar provar que o especialista
  está errado. Substitui o "controle de qualidade".
- **Cronista** — registra decisão tomada, premissa usada e resultado que deu.
  Substitui a "experiência" que num time humano fica na cabeça das pessoas.

---

## 3. Isolado ou tudo misturado?

Nem um nem outro. A regra que resolve isso:

> **Fato circula na horizontal. Decisão sobe na vertical.**

- Qualquer especialista pode **ler** qualquer dado, de qualquer área, sem pedir
  licença. Evidência é barata e esconder evidência gera decisão burra.
- Nenhum especialista **decide ou age** fora do escopo dele. Decisão que atravessa
  duas áreas sobe para o diretor. Sempre.

E mais uma, que é a que evita o erro em cascata:

> **Conclusão que atravessa fronteira anda junto com a evidência e a fonte.**

O agente comercial nunca recebe "a margem está apertada". Recebe "margem de 18%
no fechamento de agosto, apurada em `realizado_por_mes`, considerando fatura de
cartão na data de vencimento". Sem isso, o palpite de um vira premissa do outro,
e três agentes depois virou fato — sem que ninguém consiga apontar onde nasceu.

**Por que não isolar de tudo:** cada área bate a própria meta destruindo a do
vizinho. Marketing entrega o volume de leads comprando lead barato que o comercial
não fecha. Clássico, e o isolamento garante que ninguém vê.

**Por que não misturar tudo:** contexto poluído piora a resposta, o erro se
propaga sem freio, custa caro e fica impossível auditar quem errou.

**A terceira forma — força-tarefa.** Para um problema específico ("a margem caiu
4 pontos e eu não sei por quê"), o diretor junta 2 ou 3 especialistas num contexto
só, com **uma pergunta e um prazo**. Responde e dissolve. Não vira comitê
permanente — comitê permanente é reunião, e reunião é o que você está tentando
eliminar.

---

## 4. Qualidade — o que dá para prometer

Erro zero não existe. O que dá para construir é: **erro barato, visível e pego
antes de virar ação.** Sete mecanismos, em ordem de retorno:

1. **Separe ler de agir.** Uns 90% do que você quer é ler, analisar e propor.
   O agente que *age* precisa de lista fechada de ações permitidas, teto de valor
   e proibição explícita do que é irreversível.

2. **Número sem origem não é número, é opinião.** Todo valor sai com a fonte
   junto: a consulta, o arquivo, a data de apuração. Só essa regra resolve a
   maior parte dos erros que você veria.

3. **O sistema calcula, o agente interpreta.** Nunca peça para o agente somar,
   dividir ou projetar de cabeça em cima de uma tabela. Ele roda a função do
   `database.py` e lê o resultado. Conta feita "no olho" pelo modelo é a origem
   mais comum de erro grave, e é a mais fácil de eliminar.

4. **Contraditor obrigatório em decisão relevante.** E a pergunta dele não é
   "está bom?" — revisão que pergunta se está bom sempre responde que sim.
   A pergunta é: **"o que precisaria ser verdade para essa conclusão estar errada,
   e isso é verdade?"**

5. **Checklist de saída por papel.** O especialista não decide quando terminou.
   O formato decide. Faltou um campo, não entregou.

6. **Amostragem sua.** Você não confere tudo — confere uma fatia por semana, e
   100% do que for irreversível ou acima do teto de valor.

7. **Todo erro encontrado vira uma linha no manual do agente.** Se não virar
   linha escrita, vai acontecer de novo na semana seguinte. Isso mora em
   `agentes/registro/erros.md`.

---

## 5. Bater meta — de área e financeira

Meta não se cumpre com prompt. Se cumpre com ciclo.

**Cada área tem um contrato escrito** (`agentes/contratos/`): meta, indicador,
período, fonte do dado, teto de ação, e o que obriga a escalar. Sem contrato, o
agente vira um gerador de texto simpático.

**Ciclo semanal fixo:**

| Quando | Quem | O quê |
|---|---|---|
| Segunda | Especialista | Lê meta × realizado **na fonte**, declara o gap, propõe 1 a 3 ações |
| Segunda | Diretor | Corta a lista, prioriza, define dono e prazo |
| Sexta | Especialista | O que foi feito, e quanto o número andou |
| Sexta | Cronista | Registra decisão, premissa e resultado |

**Meta não batida não é bronca — é diagnóstico.** Três causas possíveis e a
resposta muda em cada uma: falhou a **execução**, falhou a **premissa** (o
caminho não leva ao número), ou a **meta** estava errada desde o começo. É o
método das dimensões da consultoria aplicado ao agente.

**Duas regras que fazem a meta funcionar de verdade:**

- **Indicador de meio, não só de fim.** Faturamento e margem são resultado — o
  agente não consegue agir neles na segunda-feira. Cada meta precisa de 1 ou 2
  indicadores que a área consiga mexer dentro da semana.
- **Pelo menos uma meta cruzada por área.** Um número que só melhora se outra
  área também ganhar. É o que impede a área de bater a própria meta empurrando o
  problema para o vizinho. Marketing não é medido em leads — é medido em lead
  qualificado que fechou.

---

## 6. Como ensinar o especialista

A virada de chave: **você não ensina descrevendo o cargo. Você ensina entregando
o manual da tarefa.** "Você é um especialista financeiro sênior" não ensina nada.
Cinco blocos ensinam:

1. **Escopo e fronteira.** O que ele faz e — principalmente — **o que ele não
   faz**. A fronteira escrita é o que impede o agente de inventar quando a
   pergunta foge do assunto dele.

2. **Fonte da verdade e permissão de não saber.** De onde vem cada dado, e a
   ordem explícita: *não está na fonte, a resposta é "não sei" com o que falta.*
   Autorizar o "não sei" é conteúdo de treinamento, não é detalhe.

3. **Método, na ordem.** Os passos que o bom humano dá, numerados. "Primeiro
   confira se o mês fechou; depois compare com os três anteriores; depois separe
   o que é sazonal." Método bem escrito vale mais que qualquer adjetivo de persona.

4. **Exemplos reais.** De 3 a 5 casos com a entrada e a saída que **você
   aceitaria**. Inclua um exemplo ruim com o motivo de ser ruim. Exemplo ensina
   mais que instrução — e exemplo ruim ensina mais que exemplo bom.

5. **Regras nascidas de erro.** A lista que cresce. Específica, nunca genérica:
   "nunca somar compra no cartão no caixa do mês da compra — a saída acontece no
   vencimento da fatura". Cada erro real vira uma linha aqui.

---

## 7. Como ensinar o gestor

Diferente, e a diferença importa. O diretor não é melhor que o especialista em
nada — ele é **o responsável pela decisão**. Cinco blocos também:

1. **Critério de decisão, com desempate.** O que ele otimiza — caixa? crescimento?
   risco? — e **em que ordem quando os três brigam**. Sem ordem de desempate
   escrita, o diretor vira um resumidor de relatório.

2. **Alçada.** O que ele decide sozinho e o que sobe para você. Por valor, por
   reversibilidade, e por exposição ao cliente e ao mercado.

3. **Como ler o especialista.** Não aceitar conclusão sem evidência, como
   confrontar, e quando acionar o contraditor.

4. **Como priorizar.** Regra fixa — impacto no gargalo × esforço × reversibilidade
   — não intuição.

5. **Formato da escalação.** Situação, opções, **recomendação**, e o que ele
   precisa de você. Pergunta aberta sem recomendação não sobe: se ele não
   consegue recomendar, ele ainda não estudou o suficiente.

E a regra dura: **o gestor não executa.**

---

## 8. Como o sistema aprende de verdade

Agente não aprende conversando com você. Ele aprende quando **você edita o
arquivo de instrução dele**. Esse é o ponto que quase todo mundo entende errado:
corrigir o agente no chat funciona por uma conversa e evapora na seguinte.

O ciclo real, uns 20 minutos por semana:

```
erro aparece → você escreve a regra em agentes/registro/erros.md
             → a regra entra no arquivo do agente em .claude/agents/
             → o caso vira exemplo no arquivo do agente
             → próxima semana o erro não repete
```

Se o mesmo erro apareceu duas vezes, o problema não é o agente — é que a regra
não foi escrita.

---

## 9. Por onde começar

**Não comece com doze agentes.** Você monta um organograma bonito que produz
doze relatórios plausíveis e errados, e não tem como conferir nenhum.

1. **Uma área só, com dado real e conferível.** Aqui é finanças, porque o número
   está no banco e você sabe olhar e dizer se está certo.
2. **Quatro semanas rodando o ciclo.** Toda semana você confere, acha erro,
   escreve a regra.
3. **Só então a segunda área.** E aí sim o diretor passa a ter o que coordenar —
   com uma área só, ele não serve para nada.
4. **O contraditor entra junto com a segunda área**, quando começa a existir
   conclusão que atravessa fronteira.

Regra de bolso: **agente que você não consegue conferir não deveria existir ainda.**

O passo zero disso tudo é `agentes/LEVANTAMENTO.md`: sem as respostas de lá, o
agente sai com método genérico — e método genérico é exatamente o que não
resolve o problema da sua empresa.

---

## 10. Arquivos

| Arquivo | O que é |
|---|---|
| `agentes/LEVANTAMENTO.md` | As perguntas que você responde para os agentes serem escritos com o seu método, e não com teoria genérica |
| `.claude/agents/diretor.md` | O gestor — prioriza, cobra, escala |
| `.claude/agents/especialista-financeiro.md` | Especialista com acesso ao banco |
| `.claude/agents/contraditor.md` | Tenta derrubar a conclusão |
| `.claude/agents/cronista.md` | Registra decisão e erro |
| `agentes/modelo-especialista.md` | Molde para criar a próxima área |
| `agentes/contratos/_MODELO.md` | Molde de contrato de meta |
| `agentes/contratos/financeiro.md` | Contrato preenchido, de exemplo |
| `agentes/registro/decisoes.md` | Histórico de decisão e resultado |
| `agentes/registro/erros.md` | Erros e as regras que nasceram deles |
