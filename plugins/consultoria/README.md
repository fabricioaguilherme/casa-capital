# Plugin Hermes — Resumos de Consultoria

Plugin do [Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
que transforma a transcrição de uma reunião de consultoria em dois documentos
prontos no Google Docs e, depois da sua aprovação pelo Telegram, manda o PDF
para o cliente por e-mail.

Não é um bot próprio: quem fala com o Telegram é o Hermes. O plugin só registra
ferramentas, e o modelo do Hermes decide quando chamar cada uma.

## O que acontece quando você manda a palavra-chave

| Você manda no Telegram | O que o agente faz |
|---|---|
| `Sebrae` | Gera **os dois** documentos (curto do Sebrae + detalhado do cliente) |
| `Consultoria` | Gera **apenas** o resumo detalhado do cliente |
| um texto de correção | Reajusta o resumo detalhado e devolve o link atualizado |
| `ok` (ou *aprovado*, *pode enviar*, *manda*, *confirmado*, *sim*…) | Exporta o PDF, envia ao cliente e marca a planilha |

Passo a passo do `gerar_resumo`:

1. Pega a transcrição **mais recente** da pasta de transcrições no Drive
   (Google Doc, `.docx` ou `.txt` — Tactiq, CraftNote ou upload manual).
2. Identifica o cliente pelo nome do arquivo, casando com a coluna *Nome* da
   planilha de cadastro (match parcial: `Padaria do Ze` acha `Padaria do Zé Ltda`).
3. **Duplo-check:** compara a palavra-chave que você mandou com a coluna *Tipo*
   do cadastro. Se não bater, **a sua palavra-chave manda** — o agente gera do
   mesmo jeito e te avisa do conflito.
4. Gera o conteúdo de cada área com GPT e passa por um **segundo agente revisor**
   (gramática, clareza, tom e coerência, sem inventar o que não foi dito).
5. Copia os templates para a pasta do cliente e substitui os marcadores.
6. Escreve `OK` na coluna *Resumo Gerado*.
7. Devolve o link do Google Doc detalhado para você revisar.

## Instalação na VPS

```bash
# 1. copiar o plugin para a pasta de plugins do Hermes
cp -r plugins/consultoria ~/.hermes/plugins/consultoria

# 2. dependências
pip install -r ~/.hermes/plugins/consultoria/requirements.txt

# 3. configuração (fica fora do git)
cp ~/.hermes/plugins/consultoria/config.example.yaml \
   ~/.hermes/plugins/consultoria/config.local.yaml
$EDITOR ~/.hermes/plugins/consultoria/config.local.yaml

# 4. conferir
hermes plugins doctor ~/.hermes/plugins/consultoria --ci
hermes plugins list
```

Habilite o plugin em `plugins.enabled` no `config.yaml` do Hermes, conforme a
documentação, e reinicie o agente.

Para ver o que ainda falta configurar, pergunte no Telegram: *"o que falta
configurar na consultoria?"* — o agente chama a ferramenta `status_consultoria`.

## Configuração

Tudo fica em `config.local.yaml` (modelo em `config.example.yaml`). Qualquer
campo também aceita variável de ambiente, que tem prioridade:
`GOOGLE_SERVICE_ACCOUNT_FILE`, `GOOGLE_SERVICE_ACCOUNT_JSON`,
`CONSULTORIA_PASTA_TRANSCRICOES`, `CONSULTORIA_PLANILHA_ID`, `OPENAI_API_KEY`,
`OPENAI_MODEL`, `CONSULTORIA_CONSULTOR_NOME`, `CONSULTORIA_EMAIL_REMETENTE`,
`CONSULTORIA_EMAIL_SENHA_APP`.

### Autenticação Google

Uma **Service Account**. Compartilhe como **Editor** com o e-mail dela:

- a pasta de transcrições;
- a pasta raiz de clientes (ou cada pasta de cliente);
- a planilha de cadastro;
- os dois Google Docs de template.

### Planilha de cadastro

| Coluna | Uso |
|---|---|
| Nome | casa com o nome do arquivo da transcrição |
| Pasta Drive | ID ou link da pasta do cliente (aceita os dois) |
| Email | destino do PDF |
| Tipo | `Sebrae` ou `Consultoria` — usado no duplo-check |
| Resumo Gerado | escrito pelo agente: `OK` |
| Email Enviado | escrito pelo agente: `Enviado` |

Os títulos são comparados sem acento e sem diferenciar maiúsculas. Se a sua
planilha usa outros nomes, troque em `planilha.colunas`. A linha é sempre
encontrada pelo nome do cliente — você nunca precisa informar número de linha.

### Templates

Converta os dois `.docx` para Google Docs (*Arquivo → Salvar como Documentos
Google*) e escreva um marcador `{{NOME_DA_AREA}}` no lugar exato de cada área:

```
DIAGNÓSTICO
{{DIAGNOSTICO}}
```

**Você não precisa listar as áreas em lugar nenhum:** o plugin lê o Google Doc
do template e descobre sozinho quais marcadores existem — mudar as áreas do
template é só editar o Doc. O bloco `templates.*.areas` do config é opcional e
serve apenas para explicar ao GPT o que entra em cada área.

Marcadores preenchidos automaticamente: `{{CLIENTE}}`, `{{DATA_REUNIAO}}`
(lida do nome do arquivo, ou da data do arquivo) e `{{DATA_HOJE}}`.

### Quem fala na reunião

Preencha `consultor.nome` com o nome/apelido que aparece nas transcrições que
separam falantes. Com ele, tudo o que for atribuído a esse nome é tratado como
fala do consultor. Deixando vazio — ou numa transcrição sem separação de
falantes —, o GPT infere pelo conteúdo: quem faz perguntas de diagnóstico e dá
orientação é o consultor; quem descreve a operação e recebe as orientações é o
cliente.

### E-mail

SMTP do Gmail com **senha de app** (não é a senha da conta; gere em
*Conta Google → Segurança → Senhas de app*). O assunto e o corpo aceitam
`{cliente}`.

## Ferramentas registradas

| Ferramenta | O que faz |
|---|---|
| `gerar_resumo` | Passos 3 a 10: acha a transcrição, confere o cadastro, gera, revisa, preenche os templates, marca a planilha, devolve o link |
| `ajustar_resumo` | Aplica seu feedback, regera o Doc e devolve o link novo |
| `aprovar_e_enviar` | PDF → e-mail ao cliente → `Enviado` na planilha → lembrete do WhatsApp |
| `status_consultoria` | O que falta configurar e qual resumo está em revisão |

O WhatsApp é apenas um **lembrete em texto** — nada é enviado automaticamente.

## Testes

```bash
python3 teste_consultoria.py     # na raiz do repositório
```

Roda o fluxo inteiro com Google, OpenAI e SMTP substituídos por dublês.

## Detalhes de implementação que valem saber

- **Correção regera o documento.** Depois de substituídos, os marcadores não
  existem mais no Doc; então cada ajuste sai de uma cópia limpa do template e a
  versão anterior vai para a lixeira do Drive (mesmo nome de arquivo).
- **Nada de exceção crua.** Todo handler devolve JSON; erro previsível (pasta
  vazia, cliente não cadastrado, config faltando) vira um recado explicando o
  que fazer.
- **Estado entre as mensagens** (transcrição, resumo atual, documento) fica no
  `ctx.state` do Hermes, com fallback para arquivo local em
  `~/.hermes/plugins/consultoria/state/`.
- **Transcrição longa** é cortada pelo meio, preservando abertura e fechamento.
