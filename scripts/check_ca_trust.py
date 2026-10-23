"""Fail (exit 1) if any given CA bundle contains a root affected by the eMudhra intermediate CA compromise.

Usage: python -I check_ca_trust.py <bundle.pem> [<bundle.pem> ...]
"""
import hashlib
import re
import ssl
import sys

AFFECTED_ROOTS = {
    "86A1ECBA089C4A8D3BBE2734C612BA341D813E043CF9E8A862CD5C57A36BBE6B": "emSign ECC Root CA - G3",
    "D7A7A0FB5D7E2731D771E9484EBCDEF71D5F0C3E0A2948782BC83EE0EA699EF4": "AAA Certificate Services",
    "7DD78D5F4F13459A83DFF9ABBBA62EDBAF6F2D102BF257FD712F4D9F2746ED8D": "emSign Root TLS CA - G3",
    "F2EDAAFF3D9B701FB4D14C9F285F8C0BAD90FC3BCC1FA07D47F4718EDABA34A5": "emSign Root CS CA - G3",
}
PEM_RE = re.compile(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", re.S)


def scan(path):
    with open(path) as f:
        certs = PEM_RE.findall(f.read())
    hits = []
    for pem in certs:
        digest = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest().upper()
        if digest in AFFECTED_ROOTS:
            hits.append(AFFECTED_ROOTS[digest])
    status = f"AFFECTED {hits}" if hits else "clean"
    print(f"{path}: {len(certs)} certs -> {status}")
    return bool(hits)


if __name__ == "__main__":
    affected = [scan(p) for p in sys.argv[1:]]
    sys.exit(1 if any(affected) else 0)
