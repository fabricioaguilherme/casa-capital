# Modelo de referência — Landing page IAE Cap E

Pasta de **estudo e inspiração**. Guarda a análise de uma landing page de venda
de terceiros (`rafaelgaldino.com/iae-cap-e/`) para servir de referência
estrutural em projetos próprios.

> **Uso:** material privado de consulta. O texto, a marca e as imagens da página
> original são de terceiros — o que se reaproveita daqui é a **estrutura** e as
> **decisões de layout e copy** documentadas em `ANATOMIA.md`, nunca o conteúdo
> literal.

## Status

Aguardando o código-fonte da página original.

O ambiente remoto do Claude Code não tem saída de rede para `rafaelgaldino.com`
(bloqueio da política de egress), então a captura precisa ser feita da máquina
local.

## Como subir o fonte

Coloque o arquivo capturado em `original/` — o nome não importa, qualquer
`.html` serve.

Formas de capturar, da mais fiel para a mais rápida:

| # | Método | O que gera |
|---|---|---|
| 1 | Extensão **SingleFile** (Chrome/Firefox) | Um único `.html` com CSS, imagens e fontes embutidos. Abre offline idêntico ao original. |
| 2 | `Ctrl+S` → "Página da Web, completa" | Um `.html` + pasta `_files` com os assets. |
| 3 | `F12` → Elements → botão direito em `<html>` → Copy → **Copy outerHTML** | O DOM já renderizado (pega o que o JavaScript montou). |
| 4 | `Ctrl+U` → `Ctrl+A` → `Ctrl+C` | Só o HTML entregue pelo servidor. |

## O que será gerado a partir do fonte

| Arquivo | Conteúdo |
|---|---|
| `index.html` | Réplica limpa e autocontida, funcionando offline. |
| `ANATOMIA.md` | Ordem das seções, lógica de copy de cada bloco (objeção atacada, gatilho usado), headline e sub, estrutura da oferta, ancoragem de preço, garantia, prova social, posicionamento e repetição dos CTAs. |
| `DESIGN.md` | Paleta em hex, tipografia, escala de espaçamentos, breakpoints, estilo dos botões. |

O `ANATOMIA.md` é a parte que dá valor de longo prazo: o HTML sozinho mostra
*o quê*, mas não *por quê*.
