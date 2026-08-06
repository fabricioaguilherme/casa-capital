"""teste_rede.py — confere quem entra de onde.

    python3 teste_rede.py

A regra: quem está em `emails_qualquer_rede` entra de qualquer lugar; todo o
resto só entra de uma faixa em `redes_liberadas`. Sem IP legível ou sem faixa
configurada, o usuário restrito NÃO entra — falha fechada, porque liberar por
engano justamente quem se quis limitar é o pior resultado possível.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402

CASA = "189.40.10.7"
VIZINHO = "189.40.10.99"      # mesma faixa /24 da casa
CELULAR = "177.220.55.3"      # 3G, fora de casa

LIVRES = ["fabricio@gmail.com", "esposa@gmail.com"]


def executar():
    falhas = []

    def cenario(titulo, ip, redes, casos):
        """casos: [(email, deve_entrar)]"""
        auth.ip_do_cliente = lambda: ip
        auth._redes_liberadas = lambda: redes
        auth._emails_de_qualquer_rede = lambda: LIVRES
        print(f"\n{titulo}")
        for email, esperado in casos:
            obtido, _ = auth.rede_permitida(email)
            marca = "ok" if obtido == esperado else "ERRADO"
            print(f"   {email:<24} {'entra' if obtido else 'barrado':<8} {marca}")
            if obtido != esperado:
                falhas.append(f"{titulo} / {email}")

    cenario(
        f"Acesso de casa ({CASA}), faixa liberada = IP exato",
        CASA, [CASA],
        [("fabricio@gmail.com", True), ("leonardo@gmail.com", True)],
    )

    cenario(
        f"Acesso do celular ({CELULAR}), faixa liberada = casa",
        CELULAR, [CASA],
        [("fabricio@gmail.com", True),    # lista livre: entra de qualquer lugar
         ("esposa@gmail.com", True),
         ("leonardo@gmail.com", False)],  # restrito: barrado fora de casa
    )

    cenario(
        f"Faixa liberada como bloco /24, acesso de {VIZINHO}",
        VIZINHO, ["189.40.10.0/24"],
        [("leonardo@gmail.com", True)],
    )

    cenario(
        "Nenhuma faixa configurada",
        CASA, [],
        [("fabricio@gmail.com", True), ("leonardo@gmail.com", False)],
    )

    cenario(
        "IP ilegível (cabeçalho ausente)",
        None, [CASA],
        [("fabricio@gmail.com", True), ("leonardo@gmail.com", False)],
    )

    cenario(
        "IP malformado",
        "nao-e-um-ip", [CASA],
        [("leonardo@gmail.com", False)],
    )

    cenario(
        "Faixa configurada errada não libera ninguém por engano",
        CELULAR, ["isso-nao-e-uma-faixa"],
        [("leonardo@gmail.com", False)],
    )

    # A casa sai pelos dois protocolos: o celular costuma pegar IPv6 e o
    # notebook IPv4. Com só um deles na lista, a pessoa é barrada dependendo
    # do aparelho — foi exatamente o que aconteceu na primeira versão.
    casa = ["179.193.98.99", "2804:7f0:6800:8eee::/64"]

    cenario(
        "Casa por IPv6 (celular no Wi-Fi)",
        "2804:7f0:6800:8eee:30d6:a398:c91e:b477", casa,
        [("leonardo@gmail.com", True)],
    )

    cenario(
        "Casa por IPv4 (notebook)",
        "179.193.98.99", casa,
        [("leonardo@gmail.com", True)],
    )

    cenario(
        "IPv6 de outra faixa (3G) continua barrado",
        "2804:9999:1111:2222::5", casa,
        [("leonardo@gmail.com", False), ("fabricio@gmail.com", True)],
    )

    return falhas


if __name__ == "__main__":
    problemas = executar()
    if problemas:
        print("\nFALHOU: " + "; ".join(problemas))
    else:
        print("\nOK — restrito só entra de casa, livre entra de qualquer lugar,")
        print("     e todo caso duvidoso barra em vez de liberar.")
    sys.stdout.flush()
    os._exit(1 if problemas else 0)
