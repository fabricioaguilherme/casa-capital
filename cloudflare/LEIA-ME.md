# Domínio próprio: casacapital.fabricioguilherme.com

Objetivo: a família acessa pelo seu domínio e o endereço `casa-capital.streamlit.app`
nunca aparece.

## Por que não bastava o CNAME

O CNAME sozinho não funciona — o navegador recusa a conexão:

```
subject: CN=*.streamlitapp.com
subjectAltName does not match host name casacapital.fabricioguilherme.com
```

O plano gratuito do Streamlit Cloud não emite certificado para domínio de
terceiros. Nenhum ajuste de DNS resolve isso; o certificado tem que sair de
outro lugar. O Worker é esse outro lugar.

---

## Já feito

- [x] CNAME antigo (`casacapital` → `casa-capital.streamlit.app`) removido
- [x] Worker `casa-capital` criado
- [x] Domínio `casacapital.fabricioguilherme.com` ligado ao Worker
- [x] Certificado emitido e testado — `HTTP 200`

Enquanto o código do passo 1 abaixo não entrar, o endereço responde
"Hello World!" (o exemplo que vem com o Worker).

## Falta fazer

### 1. Colar o código do proxy

Painel do Worker → **Editar código**. Clique dentro do editor, `⌘A`, `⌘V`
(o conteúdo de [`worker.js`](worker.js)) e **Implantar**.

> Esta é a única etapa que precisa ser feita à mão: o editor do Cloudflare roda
> dentro de um iframe isolado, que não aceita teclado automatizado.

### 2. Autorizar o novo endereço no Google

Google Cloud Console → **APIs e Serviços** → **Credenciais** → seu ID OAuth →
**URIs de redirecionamento autorizados** → adicione:

```
https://casacapital.fabricioguilherme.com/oauth2callback
```

**Não apague o endereço antigo** (`https://casa-capital.streamlit.app/oauth2callback`).
Manter os dois permite voltar atrás na hora se o proxy der problema.

### 3. Apontar o login para o novo endereço

Streamlit Cloud → seu app → **Settings** → **Secrets**, no bloco `[auth]`:

```toml
redirect_uri = "https://casacapital.fabricioguilherme.com/oauth2callback"
```

Sem isto, o login com Google devolve o usuário para o endereço antigo e ele
aparece na barra — exatamente o que se queria evitar.

Aproveite e acrescente no bloco `[acesso]`, se ainda não estiver lá:

```toml
emails_super_admin = ["fabricioaguilherme@gmail.com"]
```

---

## Conferir se funcionou

1. Abra `https://casacapital.fabricioguilherme.com` — o logo tem que aparecer.
2. Entre com o Google. Confira que a barra continua no seu domínio depois do login.
3. **Clique em qualquer menu lateral.** Este é o teste que importa: a navegação
   do Streamlit passa por WebSocket. Se a tela carrega mas não reage a cliques,
   o WebSocket foi barrado — veja abaixo.

## Se a tela carregar mas não responder a cliques

É o Streamlit recusando o WebSocket. O Worker já troca o cabeçalho `Origin` para
contornar isso, mas o Streamlit Cloud pode barrar por outro caminho. Nesse caso
o proxy não tem conserto do nosso lado e a saída é trocar de hospedagem
(Google Cloud Run tem domínio próprio com suporte oficial e não hiberna).

Para voltar ao estado anterior enquanto isso: desfaça o passo 3 e use
`casa-capital.streamlit.app` normalmente. Nada se perde — os dados estão no
Turso, não na hospedagem.
