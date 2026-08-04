# Domínio próprio: casacapital.fabricioguilherme.com

Objetivo: a família acessa pelo seu domínio e o endereço `casa-capital.streamlit.app`
nunca aparece.

## Por que não basta o CNAME

O CNAME já existe e mesmo assim o navegador recusa a conexão:

```
subject: CN=*.streamlitapp.com
subjectAltName does not match host name casacapital.fabricioguilherme.com
```

O plano gratuito do Streamlit Cloud não emite certificado para domínio de
terceiros. Nenhum ajuste de DNS resolve isso — o certificado tem que sair de
outro lugar. O Worker é esse outro lugar.

---

## Passo 1 — Apagar o CNAME antigo

No Cloudflare → **DNS** → **Records**, apague o registro `casacapital`
(o CNAME que aponta para `casa-capital.streamlit.app`).

Ele precisa sair antes: o Worker cria o próprio registro no passo 3 e o
Cloudflare recusa se já houver outro com o mesmo nome.

## Passo 2 — Criar o Worker

Cloudflare → **Workers & Pages** → **Create** → **Start with Hello World** →
**Deploy**. Depois **Edit code**, apague o exemplo, cole o conteúdo de
[`worker.js`](worker.js) e **Deploy** de novo.

## Passo 3 — Ligar o domínio ao Worker

No Worker → **Settings** → **Domains & Routes** → **Add** → **Custom Domain** →
`casacapital.fabricioguilherme.com`.

O Cloudflare cria o DNS e emite o certificado sozinho (leva de 1 a 5 minutos).

## Passo 4 — Autorizar o novo endereço no Google

Google Cloud Console → **APIs e Serviços** → **Credenciais** → seu ID OAuth →
**URIs de redirecionamento autorizados** → adicione:

```
https://casacapital.fabricioguilherme.com/oauth2callback
```

**Não apague o endereço antigo** (`https://casa-capital.streamlit.app/oauth2callback`).
Manter os dois permite voltar atrás na hora se o proxy der problema.

## Passo 5 — Apontar o login para o novo endereço

Streamlit Cloud → seu app → **Settings** → **Secrets**, no bloco `[auth]`:

```toml
redirect_uri = "https://casacapital.fabricioguilherme.com/oauth2callback"
```

Sem isto, o login com Google devolve o usuário para o endereço antigo e ele
aparece na barra — exatamente o que se queria evitar.

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

Para voltar ao estado anterior enquanto isso: desfaça o passo 5 e use
`casa-capital.streamlit.app` normalmente. Nada se perde — os dados estão no
Turso, não na hospedagem.
