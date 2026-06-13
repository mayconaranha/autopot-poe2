import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import poe_parser as p


def test_formato_padrao_com_ponto_de_milhar():
    assert p.parse_pair("1.317/1.513") == (1317, 1513)


def test_com_espacos_em_volta_da_barra():
    assert p.parse_pair("1.317 / 1.513") == (1317, 1513)


def test_sem_separador_de_milhar():
    assert p.parse_pair("523/1513") == (523, 1513)


def test_separador_virgula():
    assert p.parse_pair("1,317/1,513") == (1317, 1513)


def test_prefixo_de_lixo_do_ocr():
    assert p.parse_pair("Life 1.317/1.513") == (1317, 1513)


def test_atual_menor_que_mil():
    assert p.parse_pair("87/1.513") == (87, 1513)


def test_vida_cheia():
    assert p.percent("1.513/1.513") == 100.0


def test_percentual_aproximado():
    pct = p.percent("1.317/1.513")
    assert abs(pct - 87.0) < 0.5


def test_percentual_nunca_passa_de_100():
    # OCR pode ler o atual maior que o máx por ruído; trava em 100
    assert p.percent("1.600/1.513") == 100.0


def test_texto_vazio_retorna_none():
    assert p.parse_pair("") is None
    assert p.percent("") is None


def test_sem_barra_retorna_none():
    assert p.parse_pair("1.317 1.513") is None


def test_maximo_zero_retorna_none():
    assert p.parse_pair("0/0") is None
    assert p.percent("0/0") is None
