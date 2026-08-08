"""Leitura de cupom / canhoto de cartão por foto.

Isolado de propósito, e sem Streamlit dentro: a parte que **interpreta** a
resposta do modelo é onde mora o risco (valor errado passa despercebido,
porque número errado é plausível), e ela precisa ser testável sem rede e sem
tela — é o que `teste_cupom.py` faz.

O que a foto resolve e o que ela não resolve:

  resolve     digitar valor, data e nome do estabelecimento
  não resolve dizer se foi débito ou crédito quando o canhoto não diz, e
              escolher a categoria — isso a pessoa confirma na tela

**Débito e crédito não são a mesma coisa aqui.** No débito o dinheiro sai da
conta na hora (lançamento pago, sem cartão). No crédito a compra entra
vinculada ao cartão e o dinheiro só sai no vencimento da fatura (lançamento
pendente, com `cartao_id`) — a mesma regra da importação de fatura. Ler isso
errado adianta ou atrasa a saída em até um mês inteiro na projeção, por isso
a tela sempre mostra qual das duas foi entendida e deixa corrigir.
"""

import base64
import json
import os
import re
import unicodedata
from datetime import date, timedelta

# Sonnet dá conta de cupom fiscal e canhoto de maquininha com folga, e é o
# equilíbrio certo de custo para algo que roda a cada compra.
MODELO = "claude-sonnet-5"

MIMES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
    ".heic": "image/jpeg", ".heif": "image/jpeg",
}

INSTRUCAO = """Você está lendo a foto de um comprovante de compra: cupom fiscal,
canhoto de maquininha de cartão, recibo ou nota.

Responda SÓ com um objeto JSON, sem texto antes ou depois, com estas chaves:

  valor           número, o TOTAL pago (não o subtotal, não o troco)
  data            "AAAA-MM-DD"; se o comprovante não trouxer, use null
  estabelecimento nome da loja como aparece, em letras normais
  forma           "credito", "debito", "pix", "dinheiro" ou "desconhecido"
  parcelas        número de parcelas; 1 quando for à vista
  observacao      qualquer coisa que ajude a conferir (bandeira, nº do cartão
                  mascarado, "via do estabelecimento"), ou null
  confianca       "alta", "media" ou "baixa" — o quanto a imagem estava legível

Regras:
- Canhoto de maquininha costuma trazer CRÉDITO ou DÉBITO escrito. Use o que
  estiver escrito. Se não estiver, responda "desconhecido" — não adivinhe.
- "PARCELADO 3X" ou "3/3" significa parcelas=3.
- Valor em reais no formato brasileiro: 1.234,56 são mil duzentos e trinta e
  quatro reais e cinquenta e seis centavos.
- Se a foto não for um comprovante, responda {"erro": "não é um comprovante"}.
"""

FORMAS = {"credito", "debito", "pix", "dinheiro", "desconhecido"}


class CupomIlegivel(Exception):
    """A foto não deu para ler, ou não era um comprovante."""


def chave_api():
    """A chave dos secrets do Streamlit ou do ambiente — o que houver."""
    try:
        import streamlit as st

        if "anthropic" in st.secrets and st.secrets["anthropic"].get("api_key"):
            return st.secrets["anthropic"]["api_key"]
    except Exception:  # sem Streamlit, ou secrets ausente: cai no ambiente
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def configurado():
    return bool(chave_api())


def mime_de(nome_arquivo):
    ext = os.path.splitext(nome_arquivo or "")[1].lower()
    return MIMES.get(ext, "image/jpeg")


def _numero(valor):
    """Aceita 1234.56, "1.234,56", "R$ 1.234,56" e devolve float."""
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        return None
    limpo = re.sub(r"[^\d,.-]", "", valor)
    if not limpo:
        return None
    # Formato brasileiro: o último separador é a vírgula decimal.
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def _data(valor, hoje=None):
    """Só aceita data plausível: nem no futuro, nem de outra década.

    Comprovante amassado vira leitura torta com facilidade — 2020 no lugar de
    2026 passaria despercebido e jogaria o lançamento para um mês que ninguém
    mais olha.
    """
    hoje = hoje or date.today()
    if not isinstance(valor, str):
        return None
    achado = re.search(r"(\d{4})-(\d{2})-(\d{2})", valor)
    if not achado:
        return None
    try:
        lida = date(*(int(p) for p in achado.groups()))
    except ValueError:
        return None
    if lida > hoje + timedelta(days=1) or lida < hoje - timedelta(days=400):
        return None
    return lida


def _forma(valor):
    """"CRÉDITO", "Crédito" e "credito" são a mesma palavra.

    Tirar acento e caixa é reconhecer, não adivinhar — o canhoto imprime em
    maiúsculas e o modelo copia o que está escrito. O que **não** se adivinha
    é quando o comprovante não diz: aí volta "desconhecido" e a tela pergunta,
    porque errar entre os dois muda o dia da saída em até um mês.
    """
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).strip().lower()
    if texto in FORMAS:
        return texto
    # "cartão de crédito", "débito à vista", "crédito parcelado"...
    for conhecida in ("credito", "debito", "pix", "dinheiro"):
        if conhecida in texto:
            return conhecida
    return "desconhecido"


def interpretar(resposta, hoje=None):
    """Transforma a resposta do modelo no que a tela precisa.

    Função pura: é aqui que o teste entra. Nada de rede, nada de tela.
    """
    if isinstance(resposta, bytes):
        resposta = resposta.decode("utf-8", errors="replace")
    texto = (resposta or "").strip()

    # O modelo às vezes embrulha em ```json — e às vezes escreve uma frase antes.
    cerca = re.search(r"```(?:json)?\s*(.*?)```", texto, re.S)
    if cerca:
        texto = cerca.group(1).strip()
    else:
        chaves = re.search(r"\{.*\}", texto, re.S)
        if chaves:
            texto = chaves.group(0)

    try:
        dados = json.loads(texto)
    except (ValueError, TypeError):
        raise CupomIlegivel("Não consegui entender a resposta da leitura.")

    if not isinstance(dados, dict) or dados.get("erro"):
        raise CupomIlegivel(str(dados.get("erro") if isinstance(dados, dict)
                                else "Resposta inesperada."))

    valor = _numero(dados.get("valor"))
    if valor is None or valor <= 0:
        raise CupomIlegivel("Não achei o valor total nesta foto.")

    forma = _forma(dados.get("forma"))

    parcelas = dados.get("parcelas")
    try:
        parcelas = max(1, int(parcelas))
    except (TypeError, ValueError):
        parcelas = 1

    confianca = str(dados.get("confianca") or "media").strip().lower()

    return {
        "valor": round(valor, 2),
        "data": _data(dados.get("data"), hoje),  # None = a tela usa hoje
        "estabelecimento": (str(dados.get("estabelecimento") or "").strip()[:120]
                            or "Compra"),
        "forma": forma,
        "parcelas": parcelas,
        "observacao": (str(dados.get("observacao")).strip()[:200]
                       if dados.get("observacao") else None),
        "confianca": confianca if confianca in {"alta", "media", "baixa"} else "media",
    }


def ler(imagem, nome_arquivo="foto.jpg", hoje=None):
    """Manda a foto para o modelo e devolve o que ele leu, já conferido."""
    chave = chave_api()
    if not chave:
        raise CupomIlegivel(
            "A leitura por foto precisa de uma chave da API da Anthropic "
            "configurada em `anthropic.api_key` nos secrets do app."
        )

    import anthropic

    cliente = anthropic.Anthropic(api_key=chave)
    resposta = cliente.messages.create(
        model=MODELO,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": mime_de(nome_arquivo),
                    "data": base64.standard_b64encode(imagem).decode("ascii"),
                }},
                {"type": "text", "text": INSTRUCAO},
            ],
        }],
    )
    texto = "".join(bloco.text for bloco in resposta.content
                    if getattr(bloco, "type", "") == "text")
    return interpretar(texto, hoje)
