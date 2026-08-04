/**
 * Casa Capital — proxy do domínio próprio.
 *
 * Por que isto existe
 * -------------------
 * O plano gratuito do Streamlit Cloud não emite certificado para domínio de
 * terceiros: apontar o CNAME direto para lá derruba a conexão no TLS
 * ("subjectAltName does not match"). Este Worker resolve atendendo em
 * casacapital.fabricioguilherme.com com o certificado do Cloudflare e
 * repassando tudo para o Streamlit por baixo.
 *
 * Ele também reescreve os redirecionamentos e os cookies, senão o endereço
 * antigo reaparece na barra do navegador — que é justamente o que se quer
 * evitar.
 *
 * Como publicar: ver LEIA-ME.md nesta pasta.
 */

const UPSTREAM = "casa-capital.streamlit.app";
const BOOTSTRAP = "share.streamlit.io";

/**
 * O Streamlit Cloud abre a sessão mandando o navegador ao share.streamlit.io,
 * que assina um token amarrado ao domínio do app e devolve para /-/login.
 * Esse endereço só aceita domínios .streamlit.app — com o nosso ele responde
 * HTTP 500 (testado). A saída é fazer esse vaivém aqui dentro, usando o
 * domínio que ele aceita, e entregar ao navegador só o cookie do fim da linha.
 */
async function abrirSessao(destino) {
  const boot = new URL(destino);
  boot.searchParams.set("redirect_uri", `https://${UPSTREAM}/`);

  const r1 = await fetch(boot.toString(), { redirect: "manual" });
  const paraLogin = r1.headers.get("Location");
  if (!paraLogin) return null;

  const r2 = await fetch(paraLogin, { redirect: "manual" });
  const cookies =
    typeof r2.headers.getSetCookie === "function" ? r2.headers.getSetCookie() : [];
  return cookies.length ? cookies : null;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const dominioPublico = url.hostname;

    url.hostname = UPSTREAM;
    url.protocol = "https:";
    url.port = "";

    // Construir a partir do request original preserva método, corpo e — o que
    // mais importa aqui — o handshake de WebSocket.
    const pedido = new Request(url.toString(), request);
    pedido.headers.set("Host", UPSTREAM);

    // O Streamlit confere a Origin no handshake do WebSocket e recusa quem não
    // for do domínio dele. Sem esta troca, a tela carrega mas nada responde.
    if (pedido.headers.has("Origin")) {
      pedido.headers.set("Origin", `https://${UPSTREAM}`);
    }
    const referer = pedido.headers.get("Referer");
    if (referer) {
      pedido.headers.set("Referer", referer.split(dominioPublico).join(UPSTREAM));
    }

    const resposta = await fetch(pedido, { redirect: "manual" });

    // WebSocket: devolver a resposta como veio. Reconstruí-la perde a conexão.
    if (resposta.webSocket) {
      return resposta;
    }

    // Sessão ainda não aberta: resolver aqui e recarregar já com o cookie.
    const destino = resposta.headers.get("Location");
    if (destino && destino.includes(BOOTSTRAP)) {
      const cookies = await abrirSessao(destino);
      if (cookies) {
        const saida = new Headers();
        for (const cookie of cookies) {
          saida.append("Set-Cookie", cookie.replace(/;\s*Domain=[^;]+/i, ""));
        }
        saida.set("Location", url.pathname + url.search);
        saida.set("Cache-Control", "no-store");
        return new Response(null, { status: 302, headers: saida });
      }
    }

    const cabecalhos = new Headers(resposta.headers);

    // Redirecionamento apontando para o endereço do Streamlit vazaria o link.
    const local = cabecalhos.get("Location");
    if (local) {
      cabecalhos.set("Location", local.split(UPSTREAM).join(dominioPublico));
    }

    // Cookie marcado com Domain=...streamlit.app não é devolvido pelo navegador
    // no pedido seguinte, e a sessão se perde a cada clique. Tirar o Domain faz
    // o cookie valer para o domínio que o usuário está vendo.
    const cookies =
      typeof cabecalhos.getSetCookie === "function" ? cabecalhos.getSetCookie() : [];
    if (cookies.length) {
      cabecalhos.delete("Set-Cookie");
      for (const cookie of cookies) {
        cabecalhos.append("Set-Cookie", cookie.replace(/;\s*Domain=[^;]+/i, ""));
      }
    }

    return new Response(resposta.body, {
      status: resposta.status,
      statusText: resposta.statusText,
      headers: cabecalhos,
    });
  },
};
