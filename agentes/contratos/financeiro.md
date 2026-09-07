# Contrato — Financeiro

> Exemplo preenchido, para servir de referência. **Ajuste os números para a sua
> realidade antes de usar** — os valores aqui são ilustrativos.

## Responsável
Agente: `especialista-financeiro` · Dono humano: Fabrício

## Meta do período
| | |
|---|---|
| **Meta** | Saldo projetado nunca fura o zero em 90 dias |
| **Período** | Mensal, com leitura semanal |
| **Fonte** | `database.projecao_saldo(conn, 90, grupo_id=...)` |
| **Apurado em** | Toda segunda-feira |

## Indicadores de meio
| Indicador | Alvo semanal | Fonte |
|---|---|---|
| Lançamentos pendentes com data vencida | zero | `listar_lancamentos(status="pendente")` |
| Dias entre a compra e o lançamento no sistema | até 2 | `lancamentos.criado_em` |
| Fatura de cartão conciliada antes do vencimento | 100% | `fatura_cartao` + conciliação |

*Por que estes:* saldo e margem são resultado — não dá para agir neles na
segunda. Dado atrasado e fatura não conciliada, sim: são a causa direta de
projeção errada, e dá para corrigir dentro da semana.

## Meta cruzada
| Indicador | Área parceira | Alvo |
|---|---|---|
| Recebimento realizado ÷ recebimento previsto | Comercial | ≥ 90% |

*Por que:* o financeiro não controla quem paga. Se vendas fecha com prazo longo
ou cliente ruim, a projeção do financeiro quebra sem que ele tenha errado nada.
Este número só melhora se as duas áreas ganharem.

## Teto de ação
- Valor máximo sem aprovação: **R$ 0** — o financeiro é somente leitura
- Ações permitidas: consultar, analisar, projetar, propor
- Proibido sem o dono: criar, alterar ou apagar lançamento; qualquer pagamento;
  qualquer compromisso

## O que obriga a escalar
- Projeção fura o zero em qualquer dia dos próximos 90
- Despesa da categoria acima de 20% da média dos 3 meses anteriores
- Divergência entre extrato e sistema acima de R$ 100
- Mês fechando com pendência não conciliada
