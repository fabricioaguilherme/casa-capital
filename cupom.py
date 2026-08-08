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

# Dois provedores para a mesma tarefa. O Gemini custa uma fração e é o padrão;
# a Anthropic fica como alternativa. Quem escolhe é `provedor()`, pela chave que
# estiver configurada.
MODELO_GEMINI = "gemini-3.6-flash"
MODELO_ANTHROPIC = "claude-sonnet-5"

# Compatibilidade com quem importava o nome antigo.
MODELO = MODELO_ANTHROPIC

# A API do Gemini é /v1beta/interactions ({model, input}) — não o generateContent
# antigo. Conferido na documentação: escrever de memória daria 404.
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

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


class LeituraIndisponivel(Exception):
    """O serviço de leitura não respondeu — chave, cota, rede.

    Separado de `CupomIlegivel` de propósito: mandar tirar outra foto quando o
    problema é a chave da API faz a pessoa fotografar o cupom cinco vezes até
    desistir. O erro é de configuração, e a mensagem tem que dizer isso.
    """


def explicar_falha(erro):
    """Traduz a exceção da API para uma frase que diga o que fazer.

    Função pura, sem rede e sem tela — é o que permite testar as mensagens.
    """
    tipo = type(erro).__name__
    texto = str(erro)

    if "authentication_error" in texto or "invalid x-api-key" in texto or tipo == "AuthenticationError":
        return ("A chave da API foi recusada (**401 · invalid x-api-key**). Ela chegou "
                "até a Anthropic, então o problema não é a foto nem o app: é a chave em si.\n\n"
                "Confira nos secrets: precisa ser uma chave de **console.anthropic.com → "
                "API keys**, começando com `sk-ant-api03-`, colada inteira, sem espaço "
                "nem aspas sobrando. Chave apagada no console também dá este erro.")

    if "credit balance" in texto or "insufficient" in texto.lower():
        return ("A conta da Anthropic está **sem crédito**. A chave é válida; falta saldo. "
                "Adicione crédito em console.anthropic.com → Billing.")

    if tipo == "PermissionDeniedError" or "permission" in texto.lower():
        return ("A chave é válida mas **não tem permissão** para este modelo. "
                "Confira o workspace da chave no console.")

    if tipo == "RateLimitError" or "rate_limit" in texto:
        return "Muitas leituras em pouco tempo. Espere alguns segundos e tente de novo."

    if tipo in ("APIConnectionError", "APITimeoutError") or "connection" in texto.lower():
        return ("Não consegui falar com a Anthropic — conexão. Tente de novo; "
                "se persistir, é rede.")

    return f"A leitura falhou: {texto}"


def explicar_falha_http(status, corpo):
    """Traduz um erro HTTP do Gemini para uma frase que diga o que fazer.

    Função pura — o `corpo` entra como texto e nada aqui toca a rede, que é o
    que permite testar as mensagens sem gastar uma chamada.
    """
    trecho = (corpo or "")[:300]

    if status in (401, 403):
        return ("A chave do Gemini foi recusada (**HTTP %d**). Ela chegou até o Google, "
                "então o problema não é a foto nem o app: é a chave.\n\n"
                "Confira nos secrets: precisa ser uma chave de **aistudio.google.com → "
                "Get API key**, colada inteira, sem espaço nem aspas sobrando. Chave "
                "apagada no console dá o mesmo erro." % status)

    if status == 429:
        return ("Limite de uso do Gemini atingido (**429**). Na camada gratuita são "
                "cerca de 500 leituras por dia e 10 por minuto. Espere um pouco e "
                "tente de novo, ou ative cobrança no Google AI Studio.")

    if status == 400 and "API key" in trecho:
        return "A chave do Gemini está com formato inválido. Copie de novo, inteira."

    if status >= 500:
        return ("O Gemini está fora do ar ou sobrecarregado (**HTTP %d**). "
                "Tente de novo em alguns minutos." % status)

    return "A leitura falhou (HTTP %d): %s" % (status, trecho)


def _dos_secrets(secao, chaves_soltas, variaveis):
    """Procura uma chave em [secao].api_key, depois solta, depois no ambiente.

    Aceita as duas formas de colar nos secrets porque as duas são naturais, e
    ficar sem leitura por causa de um colchete seria bobagem:

        [gemini]                      GEMINI_API_KEY = "AIza..."
        api_key = "AIza..."
    """
    try:
        import streamlit as st

        bloco = st.secrets.get(secao)
        if bloco and bloco.get("api_key"):
            return bloco["api_key"]
        for nome in chaves_soltas:
            if st.secrets.get(nome):
                return st.secrets[nome]
    except Exception:  # sem Streamlit, ou secrets ausente: cai no ambiente
        pass
    for nome in variaveis:
        if os.environ.get(nome):
            return os.environ[nome]
    return None


def chave_gemini():
    return _dos_secrets("gemini", ("GEMINI_API_KEY", "GOOGLE_API_KEY", "gemini_api_key"),
                        ("GEMINI_API_KEY", "GOOGLE_API_KEY"))


def chave_anthropic():
    return _dos_secrets("anthropic", ("ANTHROPIC_API_KEY", "anthropic_api_key",
                                      "api_key_anthropic"),
                        ("ANTHROPIC_API_KEY",))


# Compatibilidade: o nome antigo continua valendo para a Anthropic.
chave_api = chave_anthropic


def provedor():
    """Quem vai ler a foto: "gemini", "anthropic", ou None se não há chave.

    O Gemini vem primeiro quando os dois estão configurados — é a opção barata,
    e quem colar a chave da Anthropic depois provavelmente quer justamente
    trocar. Para fixar um dos dois, ponha nos secrets:

        [cupom]
        provedor = "anthropic"
    """
    escolhido = None
    try:
        import streamlit as st

        bloco = st.secrets.get("cupom")
        if bloco and bloco.get("provedor"):
            escolhido = str(bloco["provedor"]).strip().lower()
    except Exception:
        pass
    escolhido = escolhido or os.environ.get("CUPOM_PROVEDOR", "").strip().lower() or None

    disponiveis = {"gemini": chave_gemini(), "anthropic": chave_anthropic()}
    if escolhido in disponiveis and disponiveis[escolhido]:
        return escolhido
    for nome in ("gemini", "anthropic"):   # ordem de preferência: o mais barato
        if disponiveis[nome]:
            return nome
    return None


def configurado():
    return provedor() is not None


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


def texto_da_resposta_gemini(dados):
    """Extrai o texto da resposta do Gemini.

    Função pura, para ser testada sem rede — e tolerante de propósito: usa o
    atalho `output_text` quando existe e, se ele sumir numa versão futura da
    API, cai para os blocos de `steps`. Formato que muda em silêncio é o tipo
    de coisa que só aparece no caixa da loja.
    """
    if not isinstance(dados, dict):
        return ""
    atalho = dados.get("output_text")
    if isinstance(atalho, str) and atalho.strip():
        return atalho

    pedacos = []
    for passo in dados.get("steps") or []:
        if not isinstance(passo, dict):
            continue
        for bloco in passo.get("content") or []:
            if isinstance(bloco, dict) and isinstance(bloco.get("text"), str):
                pedacos.append(bloco["text"])
    return "".join(pedacos)


def _ler_gemini(imagem, nome_arquivo, chave):
    import httpx

    corpo = {
        "model": MODELO_GEMINI,
        "input": [
            {"type": "text", "text": INSTRUCAO},
            {"type": "image",
             "mime_type": mime_de(nome_arquivo),
             "data": base64.standard_b64encode(imagem).decode("ascii")},
        ],
    }
    resposta = httpx.post(
        GEMINI_URL, json=corpo, timeout=90.0,
        headers={"x-goog-api-key": chave, "Content-Type": "application/json"},
    )
    if resposta.status_code >= 400:
        raise LeituraIndisponivel(explicar_falha_http(resposta.status_code, resposta.text))
    return texto_da_resposta_gemini(resposta.json())


def _ler_anthropic(imagem, nome_arquivo, chave):
    import anthropic

    cliente = anthropic.Anthropic(api_key=chave)
    try:
        resposta = cliente.messages.create(
            model=MODELO_ANTHROPIC,
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
    except Exception as erro:  # chave, cota, permissão, rede
        raise LeituraIndisponivel(explicar_falha(erro)) from erro

    return "".join(bloco.text for bloco in resposta.content
                   if getattr(bloco, "type", "") == "text")


def ler(imagem, nome_arquivo="foto.jpg", hoje=None):
    """Manda a foto para o modelo e devolve o que ele leu, já conferido.

    Qual modelo é detalhe de infraestrutura: os dois devolvem texto, e quem
    transforma texto em lançamento é `interpretar()` — a mesma função, com os
    mesmos testes, valha qual valer o provedor.
    """
    quem = provedor()
    if not quem:
        raise LeituraIndisponivel(
            "A leitura por foto precisa de uma chave de API configurada nos "
            "secrets do app — `[gemini] api_key` ou `[anthropic] api_key`."
        )

    if quem == "gemini":
        texto = _ler_gemini(imagem, nome_arquivo, chave_gemini())
    else:
        texto = _ler_anthropic(imagem, nome_arquivo, chave_anthropic())

    if not texto.strip():
        raise LeituraIndisponivel(
            "O serviço respondeu, mas sem texto. Tente de novo; se persistir, "
            "pode ser mudança no formato da resposta."
        )
    return interpretar(texto, hoje)
