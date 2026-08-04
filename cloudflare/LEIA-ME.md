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

## Estado: no ar

- [x] CNAME antigo removido
- [x] Worker `casa-capital` criado e código do proxy implantado
- [x] Domínio ligado ao Worker, certificado emitido
- [x] `redirect_uri` do Google apontando para o domínio próprio
- [x] Testado de fora: `302 → / → 200`, e zero ocorrências do endereço antigo
      no HTML servido

## A pedra do caminho: o bootstrap de sessão

O Streamlit Cloud abre a sessão mandando o navegador ao `share.streamlit.io`,
que assina um token **amarrado ao domínio do app**. Esse endereço recusa
domínio de fora:

| `redirect_uri` enviado | resposta |
|---|---|
| `casa-capital.streamlit.app` | 303 (segue) |
| `casacapital.fabricioguilherme.com` | **500** |

Por isso o Worker faz esse vaivém no servidor (`abrirSessao`), usando o domínio
que o Streamlit aceita, e entrega ao navegador só o cookie do fim da linha. O
navegador nunca sai do domínio próprio.

Se um dia o proxy parar de funcionar, é aqui que se olha primeiro — essa parte
depende de um comportamento do Streamlit Cloud que eles podem mudar sem aviso.

## Manutenção

O editor do Cloudflare roda dentro de um iframe isolado que não aceita teclado
automatizado: para atualizar o Worker é `⌘A` / `⌘V` à mão no painel, colando o
conteúdo de [`worker.js`](worker.js).

Mantenha `https://casa-capital.streamlit.app/oauth2callback` na lista de URIs
autorizados do Google. É o que permite voltar ao endereço antigo na hora, se o
proxy quebrar.

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
