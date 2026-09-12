"""Diagnostic TLS : qui a signe le certificat que CETTE machine recoit ?

Usage :  python src\\diag_ssl.py

Pourquoi ce script existe : quand on desactive la verification, Python renvoie un
dictionnaire VIDE pour getpeercert() -- il ne decode le certificat que s'il le
verifie. Il faut donc recuperer le certificat en binaire (DER), le convertir en
PEM, l'ecrire dans un fichier, puis le faire decoder par le module ssl.
"""

import socket
import ssl
import sys
import tempfile
from pathlib import Path

HOTE, PORT = "bdiff.agriculture.gouv.fr", 443


def lisible(nom):
    if not nom:
        return "?"
    return ", ".join(f"{c}={v}" for groupe in nom for c, v in groupe)


def decoder(der, etiquette):
    """Ecrit le DER en PEM puis le fait decoder par le module ssl."""
    pem = ssl.DER_cert_to_PEM_cert(der)
    f = Path(tempfile.gettempdir()) / f"diag_{etiquette}.pem"
    f.write_text(pem, encoding="ascii")
    try:
        import _ssl

        return _ssl._test_decode_cert(str(f))
    except Exception as e:
        return {"_erreur": f"{type(e).__name__}: {e}"}


print(f"=== Diagnostic TLS : {HOTE}:{PORT} ===\n")

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

try:
    with socket.create_connection((HOTE, PORT), timeout=20) as brut:
        with ctx.wrap_socket(brut, server_hostname=HOTE) as tls:
            print("Version TLS :", tls.version())

            # --- 1. le certificat du serveur ---------------------------------
            info = decoder(tls.getpeercert(binary_form=True), "leaf")
            print("\n1) CERTIFICAT DU SERVEUR")
            print("   Sujet    :", lisible(info.get("subject")))
            print("   EMETTEUR :", lisible(info.get("issuer")))
            print("   Valide   :", info.get("notBefore"), "->", info.get("notAfter"))
            print("   caIssuers:", info.get("caIssuers") or "aucune adresse fournie")

            # --- 2. la chaine complete envoyee par le serveur -----------------
            print("\n2) CHAINE ENVOYEE PAR LE SERVEUR")
            chaine = None
            for methode in ("get_unverified_chain", "get_verified_chain"):
                if hasattr(tls, methode):
                    try:
                        chaine = getattr(tls, methode)()
                        break
                    except Exception as err:
                        print(f"   ({methode} indisponible : {err})")
                        continue
            if not chaine:
                print(
                    "   (Python trop ancien pour lister la chaine :",
                    f"{sys.version_info.major}.{sys.version_info.minor})",
                )
                print("   Seul le certificat du serveur est visible ci-dessus.")
            else:
                for i, c in enumerate(chaine):
                    der = (
                        c.public_bytes(ssl.Purpose.SERVER_AUTH)
                        if hasattr(c, "public_bytes")
                        else bytes(c)
                    )
                    d = decoder(der, f"c{i}")
                    print(f"   [{i}] sujet    : {lisible(d.get('subject'))}")
                    print(f"       emetteur : {lisible(d.get('issuer'))}")
                print(
                    f"   -> {len(chaine)} certificat(s) envoye(s).",
                    "Une chaine complete en contient generalement 2 ou 3.",
                )
except Exception as e:
    print("ECHEC de connexion :", type(e).__name__, e)
    sys.exit(1)

print("\n=== COMMENT LIRE CE RESULTAT ===")
print("A) L'EMETTEUR porte un nom d'antivirus, de pare-feu, de proxy ou de l'ecole")
print("   (Kaspersky, ESET, Bitdefender, Fortinet, Zscaler, Netskope, Sophos...)")
print("   -> le reseau inspecte le HTTPS. Il faut ajouter SON autorite au bundle.")
print("B) L'EMETTEUR est une autorite publique et la chaine ne contient qu'1 seul")
print("   certificat -> chaine incomplete : Chrome telecharge l'intermediaire")
print("   manquant, Python ne le fait pas. On l'ajoutera au bundle.")
