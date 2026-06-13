"""
Leitura do globo via OCR.

Captura a região calibrada (números do globo), faz um pré-processamento leve pra
ajudar o OCR e devolve o percentual atual/máx. O RapidOCR carrega o modelo só na
primeira chamada, então a inicialização é preguiçosa.
"""

import mss
import numpy as np

import poe_parser

_ocr = None


def _get_ocr():
    """Carrega o RapidOCR sob demanda (a primeira chamada é mais lenta)."""
    global _ocr
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def _grab(region: dict) -> np.ndarray:
    with mss.mss() as sct:
        shot = sct.grab(region)
    img = np.frombuffer(shot.bgra, dtype=np.uint8).reshape(shot.height, shot.width, 4)
    return img[:, :, :3]  # BGR


def _preprocess(bgr: np.ndarray) -> np.ndarray:
    """
    Aumenta a região ~3x. Testado: o upscale cúbico sozinho dá a leitura mais
    limpa nos dígitos do globo; threshold/binarização atrapalhava o OCR.
    """
    import cv2

    return cv2.resize(bgr, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)


def read_text(region: dict) -> str:
    """Roda o OCR na região e devolve o texto cru concatenado."""
    try:
        img = _preprocess(_grab(region))
        result, _ = _get_ocr()(img)
        if not result:
            return ""
        return " ".join(line[1] for line in result)
    except Exception:
        return ""


def read_percent(region: dict):
    """Percentual do globo (0–100), ou None se a leitura falhar."""
    return poe_parser.percent(read_text(region))
