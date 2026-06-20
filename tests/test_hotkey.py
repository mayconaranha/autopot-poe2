import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hotkey as hk


def test_parse_function_key():
    assert hk.parse("f6") == (0x75, 0)          # VK_F6 = 0x75
    assert hk.parse("F8") == (0x77, 0)


def test_parse_letter_and_digit():
    assert hk.parse("h") == (ord("H"), 0)
    assert hk.parse("5") == (ord("5"), 0)


def test_parse_combo():
    vk, mods = hk.parse("ctrl+shift+p")
    assert vk == ord("P")
    assert mods == (0x0002 | 0x0004)


def test_parse_extra_keys():
    assert hk.parse("space") == (0x20, 0)
    assert hk.parse("esc") == (0x1B, 0)


def test_parse_invalido():
    assert hk.parse("") is None
    assert hk.parse("naoexiste") is None
    assert hk.parse("ctrl") is None          # só modificador, sem tecla
