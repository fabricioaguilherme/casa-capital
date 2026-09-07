# Levantamento — o que preciso saber para programar os agentes

Este é o documento que você preenche **uma vez**. Com ele na mão, dá para escrever
os agentes de `.claude/agents/` e os contratos de `agentes/contratos/` sem chutar
nada.

---

## Como responder

**Descreva o que existe, não o que deveria existir.** Se você responder o ideal,
eu programo agentes para uma empresa que não é a sua — e o erro só aparece na
terceira semana, quando já virou hábito.

- Responda na linha `**R:**` embaixo de cada pergunta. Frase curta serve.
- **"Não sei" e "não existe" são respostas válidas e úteis.** Elas me dizem onde
  o agente vai ter que dizer "não sei" também — e isso é qualidade, não falha.
- **[BLOQUEIA]** = sem isso não dá para escrever o agente.
  **[AFINA]** = dá para começar sem, e a resposta melhora o resultado depois.
- Onde houver *"exemplo de resposta boa"*, é o nível de detalhe que funciona.
  Acima disso é perfumaria; abaixo, eu tenho que adivinhar.

Se você só tiver fôlego para uma parte: responda o **Bloco 0** inteiro e o
**Bloco 2 + 5 de uma área só**. Isso já põe o primeiro agente de pé rodando o
ciclo. O resto entra na segunda rodada — mas entra, não "fica para depois".

---

## Quadro — o que cada bloco alimenta

| Bloco | Responde | Vira o quê |
|---|---|---|
| **0 — A casa** | 1 vez | Base de **todos** os agentes |
| **1 — Diretor** | 1 vez | `.claude/agents/diretor.md` |
| **2 — Especialista** | **1 vez por área** | `.claude/agents/especialista-<area>.md` |
| **3 — Contraditor** | 1 vez | `.claude/agents/contraditor.md` |
| **4 — Cronista** | 1 vez | `.claude/agents/cronista.md` + `agentes/registro/` |
| **5 — Contrato** | **1 vez por área** | `agentes/contratos/<area>.md` |
| **6 — Anexos** | 1 vez | Exemplos dentro dos agentes |

### Respostas que servem para mais de um agente — você responde só uma vez

| Resposta | Além do bloco de origem, alimenta |
|---|---|
| **C7 / C8** onde mora o dado e no que você confia | Fonte da verdade de **todo** especialista + roteiro do contraditor |
| **C11** definições fechadas | **Todos.** É o que impede dois agentes darem números diferentes |
| **C15 / C16** tom e o que fazer sem certeza | **Todos** |
| **D3 / D4** teto de valor e o que é irreversível | Alçada do diretor + teto de ação de **cada** especialista + contrato |
| **D11** metas da empresa | Diretor + todos os contratos de área |
| **E8** armadilhas do domínio | "Regras que nasceram de erro" do especialista + roteiro do contraditor |
| **X1** erros que custaram caro | Contraditor + regras de erro dos especialistas + semente do cronista |
| **C17** ritmo do ciclo | Diretor (ciclo semanal) + todos os contratos |

---

# Bloco 0 — A casa

*Responder uma vez. Vale para todos os agentes.*

## A empresa

**C1. [BLOQUEIA]** O que a empresa faz, para quem, e como entra dinheiro.
*Exemplo de resposta boa: "Consultoria de gestão para PMEs brasileiras. Dois formatos: projeto imersivo de 6 meses (R$ X/mês) e consultoria por conversa (R$ Y/hora). Cliente chega por indicação."*
**R:**

**C2. [BLOQUEIA]** Quantas pessoas, e quem faz o quê hoje — mesmo que seja informal e mesmo que a resposta seja "só eu".
**R:**

**C3. [BLOQUEIA]** Quais áreas **de fato** existem hoje. Não as ideais — as que têm alguém responsável e alguma rotina.
**R:**

**C4. [BLOQUEIA]** Qual é o gargalo hoje: o que, se destravasse, faria a empresa andar. *(O diretor prioriza por isso — sem essa resposta ele prioriza no vazio.)*
**R:**

**C5.** Momento da empresa: sobrevivência / estabilidade / crescimento / arrumação da casa.
**R:**

**C6.** Faturamento médio mensal e se tem sazonalidade (que meses sobem e caem).
**R:**

**C7. [BLOQUEIA]** Onde mora o dado de cada área hoje: sistema, planilha, WhatsApp, e-mail, ou a cabeça de alguém. Seja específico por área.
*Exemplo de resposta boa: "Financeiro: app Casa Capital, banco Turso. Comercial: planilha no Drive, atualizada quando lembro. Operação: nada escrito."*
**R:**

**C8. [BLOQUEIA]** Desses dados, em qual você confia de olhos fechados e em qual **não** confia. E por quê não.
**R:**

**C9.** Quem é o dono de cada dado — quem corrige quando está errado.
**R:**

**C10.** Que sistemas existem, e quem tem acesso a cada um.
**R:**

## O vocabulário da casa

**C11. [BLOQUEIA]** Feche estas definições. Se cada agente entender de um jeito, eles vão dar números diferentes para a mesma pergunta — e aí nada mais funciona.

- O que conta como **venda fechada** (assinou? pagou a primeira? entregou?):
- O que é **cliente ativo** (comprou nos últimos quantos meses?):
- O que é **entrega concluída**:
- O que é **mês fechado** (que dia? o que precisa estar conciliado?):
- Você olha o resultado por **caixa** (quando o dinheiro entra) ou por **competência** (quando o serviço é prestado)?
- Outras palavras que vocês usam com significado próprio:

**R:**

**C12.** Dia do fechamento mensal, e dia da semana do ciclo.
**R:**

## Regras que valem para todo agente

**C13. [BLOQUEIA]** Tom: como você quer que o agente fale com você. Direto e seco? Explicando o raciocínio? Com número sempre à frente?
**R:**

**C14. [BLOQUEIA]** Quando o agente não tiver certeza, o que ele faz? *(Padrão que eu recomendo: diz "não sei", aponta o que falta, e não estima. Se você preferir estimativa sinalizada, precisa dizer.)*
**R:**

**C15. [BLOQUEIA]** O que **nunca** pode sair da empresa ou aparecer num texto que você repassa: nome de cliente? valor de contrato? dado de terceiro?
**R:**

**C16. [BLOQUEIA]** Quanto tempo por semana você consegue dar para conferir os agentes. **Real, não ideal.** *(Isso define quantos agentes podem existir. Agente que ninguém confere não deveria existir.)*
**R:**

**C17.** Quem mais além de você vai usar isso, e o que essa pessoa pode ver.
**R:**

**C18. [AFINA]** O que já deu errado quando você tentou delegar ou automatizar antes. *(É a lista dos erros que eu preciso impedir de repetir.)*
**R:**

---

# Bloco 1 — Diretor

*Responder uma vez. Vira `.claude/agents/diretor.md`.*

**D1. [BLOQUEIA]** Ordem de desempate. Numere de 1 a 5 pelo que vem primeiro quando eles brigam entre si:
`( ) caixa` `( ) crescimento` `( ) risco baixo` `( ) qualidade da entrega ao cliente` `( ) sua carga de trabalho`
**R:**

**D2. [BLOQUEIA]** Teto: até quanto (R$) o diretor pode recomendar como decidido, sem passar por você.
**R:**

**D3. [BLOQUEIA]** O que é **irreversível** na sua empresa. Lista concreta.
*Exemplo de resposta boa: "Falar com cliente. Mandar proposta. Demitir. Mudar preço de tabela. Cancelar contrato de fornecedor."*
**R:**

**D4. [BLOQUEIA]** O que nunca pode chegar ao cliente ou ao mercado sem você ver antes.
**R:**

**D5. [BLOQUEIA]** Quantas ações por semana a empresa consegue **executar de verdade**. *(O diretor corta a lista nesse número. Sem isso ele aprova dez e você faz zero.)*
**R:**

**D6.** Como você prioriza hoje. Descreva a última vez que escolheu entre duas coisas e por que escolheu aquela. *(Exemplo real ensina mais do que a regra.)*
**R:**

**D7. [BLOQUEIA]** Com que frequência e em que formato ele te procura: só na exceção? resumo semanal? todo dia de manhã?
**R:**

**D8.** O que você considera "me incomodar à toa". Seja específico — é o filtro dele.
**R:**

**D9.** Quando duas áreas discordam e a evidência não resolve, quem ganha por padrão.
**R:**

**D10. [BLOQUEIA]** Metas da empresa (não de área) para os próximos 90 dias e para 12 meses. Com número.
**R:**

**D11. [AFINA]** Que decisão você adiou nos últimos 3 meses, e por quê. *(Mostra onde o processo trava de verdade.)*
**R:**

---

# Bloco 2 — Especialista

> **Responder uma vez POR ÁREA.** Copie este bloco inteiro para cada área do C3.
> Comece pela área onde o número existe e você consegue conferir.

### Área: ________________

**E1. [BLOQUEIA]** O que essa área entrega, em uma frase.
**R:**

**E2. [BLOQUEIA]** Quem faz esse trabalho hoje, e quanto disso é você.
**R:**

**E3. [BLOQUEIA]** As perguntas que você faz para essa área toda semana. Liste de 3 a 5, com as suas palavras.
*Exemplo de resposta boa: "Quanto entrou? O que vence essa semana? Tem cliente atrasado? O caixa aguenta o mês?"*
**R:**

**E4. [BLOQUEIA]** As tarefas recorrentes dessa área e a frequência de cada uma.
**R:**

**E5. [BLOQUEIA]** De onde sai o dado dessa área. Nome exato do sistema, da planilha, da aba, do arquivo.
**R:**

**E6. [BLOQUEIA]** Como se apura o número principal dessa área — o passo a passo, do jeito que **você** faria na mão.
*Exemplo de resposta boa: "Abro o extrato, confiro se toda compra de cartão foi lançada, jogo a fatura na data de vencimento e não na da compra, aí comparo com os 3 meses anteriores."*
**R:**

**E7. [BLOQUEIA]** O que essa área **não** faz e **não** decide. *(É o que impede o agente de inventar quando a pergunta foge do assunto.)*
**R:**

**E8. [BLOQUEIA]** As armadilhas do domínio: o que parece certo e está errado. Onde alguém novo erraria.
*Exemplo de resposta boa: "Compra no cartão não sai do caixa no mês da compra. Comissão só conta quando o cliente paga, não quando assina."*
**R:**

**E9. [BLOQUEIA]** Três exemplos reais: uma pergunta que você fez, e a resposta que **você aceitaria** como boa. Pode ser copiada de um relatório antigo.
**R:**

**E10. [BLOQUEIA]** Um exemplo de resposta **ruim** que você já recebeu nessa área — e por que é ruim. *(Exemplo ruim ensina mais que exemplo bom.)*
**R:**

**E11.** Vocabulário próprio dessa área que não está no C11.
**R:**

**E12. [BLOQUEIA]** Essa área só **lê e propõe**, ou pode **executar** alguma coisa? Se executa, a lista fechada do que pode fazer.
**R:**

**E13. [BLOQUEIA]** Teto de valor dessa área, e as ações proibidas sem você.
**R:**

**E14. [BLOQUEIA]** O que obriga essa área a te chamar na hora, sem esperar o ciclo.
*Exemplo de resposta boa: "Projeção furando o zero. Cliente reclamando. Despesa 20% acima da média."*
**R:**

**E15.** Que planilha, modelo ou documento já existe hoje que serve de padrão de saída. Anote o nome — vou pedir o arquivo no Bloco 6.
**R:**

**E16. [BLOQUEIA]** Quem confere a saída dessa área, e como sabe que está certa.
**R:**

---

# Bloco 3 — Contraditor

*Responder uma vez. Vira `.claude/agents/contraditor.md`.*

**X1. [BLOQUEIA]** Três erros que já te custaram caro — dinheiro, cliente ou tempo. O que aconteceu e o que você não viu na hora.
*(Esta é a pergunta mais valiosa do documento inteiro. É o que ensina o contraditor onde cavar, e vira regra de erro nos especialistas.)*
**R:**

**X2. [BLOQUEIA]** Em que número da sua empresa você mais desconfia — aquele que você olha e pensa "será?".
**R:**

**X3.** Alguma conclusão bonita que já te enganou. Parecia óbvia e estava errada.
**R:**

**X4. [BLOQUEIA]** O que caracteriza **decisão relevante** aqui — a que precisa passar pelo contraditor. Por valor? Por chegar no cliente? Por não dar para desfazer?
**R:**

**X5.** Que premissas a empresa repete sem checar.
*Exemplo de resposta boa: "Que esse cliente sempre paga em dia. Que dezembro é fraco. Que indicação não custa nada."*
**R:**

**X6.** Você quer o contraditor em toda análise, ou só acima do limite do X4?
**R:**

---

# Bloco 4 — Cronista

*Responder uma vez. Vira `.claude/agents/cronista.md` e semeia `agentes/registro/`.*

**R1. [BLOQUEIA]** Onde o registro vai morar: neste repositório, Notion, Drive, outro?
**R:**

**R2. [BLOQUEIA]** Que decisões merecem registro: todas as do diretor? só acima de um valor? só as que envolvem cliente?
**R:**

**R3.** Prazo padrão para revisar se a decisão deu certo. Pode variar por tipo — diga qual para qual.
**R:**

**R4. [AFINA]** Três a cinco decisões importantes dos últimos 12 meses, com o que você esperava e o que deu. *(Semeia o registro para o sistema já começar com memória em vez de folha em branco.)*
**R:**

**R5.** Quem mais lê esse registro, e se tem coisa que só você pode ver.
**R:**

---

# Bloco 5 — Contrato de meta

> **Responder uma vez POR ÁREA.** Vira `agentes/contratos/<area>.md`.

### Área: ________________

**M1. [BLOQUEIA]** A meta do período, com número e unidade.
**R:**

**M2. [BLOQUEIA]** Como esse número é apurado hoje, por quem, e em que dia.
**R:**

**M3. [BLOQUEIA]** Qual foi o resultado real nos últimos 3 períodos. *(Sem a base, "meta" é desejo — e o agente não consegue dizer se o gap é grande ou normal.)*
**R:**

**M4. [BLOQUEIA]** Um ou dois indicadores que essa área consegue **mexer dentro da semana**. Não vale faturamento nem margem — esses são resultado, ninguém age neles na segunda-feira.
*Exemplo de resposta boa: "Propostas enviadas na semana. Retorno de cliente em até 24h."*
**R:**

**M5. [BLOQUEIA]** A meta cruzada: que número dessa área só melhora se **outra** área também ganhar. E qual é a outra área.
*Exemplo de resposta boa: "Recebido ÷ previsto — só melhora se o comercial fechar com prazo e cliente decentes."*
**R:**

**M6.** O que acontece de verdade se a meta não bater. *(Se a resposta for "nada", tudo bem — mas eu preciso saber, senão programo uma cobrança que não existe.)*
**R:**

**M7. [BLOQUEIA]** Quem é o dono humano dessa meta.
**R:**

---

# Bloco 6 — Anexos

Junte o que existir. **Arquivo real vale mais que descrição** — é do arquivo que
saem os exemplos que ensinam o agente.

- [ ] Último DRE ou fechamento mensal
- [ ] Planilha de metas / acompanhamento, como está hoje
- [ ] Um relatório seu que você considera **bom** (o padrão de saída que eu quero imitar)
- [ ] Um relatório ou resposta que você considera **ruim** (o que eu preciso evitar)
- [ ] Qualquer POP, checklist ou playbook que já exista, mesmo pela metade
- [ ] Modelo de proposta / contrato, se o comercial entrar
- [ ] Print ou export das telas de sistema que os agentes vão ler

---

## Quando você terminar

Me devolva este arquivo preenchido. Do que eu faço com ele:

1. Os agentes de `.claude/agents/` escritos com **o seu** método, o seu
   vocabulário e as suas armadilhas — não com teoria genérica.
2. Os contratos de `agentes/contratos/` com meta, indicador de meio e meta cruzada.
3. `agentes/registro/` semeado com o que já aconteceu, em vez de folha em branco.
4. A lista do que ficou **"não sei"** — que não é falha do preenchimento: é a
   agenda do que precisa virar dado antes de virar agente.

O item 4 costuma ser o mais útil dos quatro.
