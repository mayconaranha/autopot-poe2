"""
Parsing dos números do globo (vida ou mana).

A detecção lê via OCR um texto tipo "1.317/1.513" e isso aqui transforma em
(atual, máximo). Fica separado do OCR de propósito: é lógica pura, dá pra testar
sem imagem nem o jogo aberto.
"""

import re

# Dois grupos de número separados por "/". Cada número pode ter ponto ou vírgula
# como separador de milhar. Aceita lixo antes/depois (ex.: "Life 1.317/1.513").
_PAIR_RE = re.compile(r"(\d[\d.,]*)\s*/\s*(\d[\d.,]*)")


def parse_pair(text: str):
    """
    Extrai (atual, máximo) de um texto de OCR. Retorna None se não der pra ler
    um par válido (sem "/", número faltando, ou máximo <= 0).
    """
    if not text:
        return None
    m = _PAIR_RE.search(text.replace(" ", ""))
    if not m:
        return None
    cur = _to_int(m.group(1))
    mx = _to_int(m.group(2))
    if cur is None or mx is None or mx <= 0 or cur < 0:
        return None
    return cur, mx


def percent(text: str):
    """Percentual atual/máx (0–100), ou None se não der pra ler."""
    pair = parse_pair(text)
    if pair is None:
        return None
    cur, mx = pair
    return min(100.0, cur / mx * 100.0)


def _to_int(raw: str):
    """Remove separadores de milhar e converte. None se sobrar vazio."""
    digits = re.sub(r"[.,]", "", raw)
    if not digits:
        return None
    return int(digits)
