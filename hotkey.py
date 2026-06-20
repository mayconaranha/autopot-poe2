"""
Atalho global liga/desliga via RegisterHotKey (API nativa do Windows).

Diferente de um hook de baixo nível (WH_KEYBOARD_LL, usado pela lib `keyboard`),
o RegisterHotKey NÃO roda código a cada tecla — então o Windows não o derruba sob
carga, que era a causa do atalho "parar de funcionar" no meio do jogo. É o jeito
correto de ter um atalho global estável, inclusive com jogo em foco.

O RegisterHotKey precisa ser chamado na mesma thread que roda o loop de mensagens
(o WM_HOTKEY vai pra fila daquela thread). Por isso tudo acontece numa thread
dedicada, e a troca de tecla é pedida via PostThreadMessage.
"""

import ctypes
import threading
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.UnregisterHotKey.restype = wintypes.BOOL
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_user32.GetMessageW.restype = ctypes.c_int
_user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
_user32.PeekMessageW.restype = wintypes.BOOL
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostThreadMessageW.restype = wintypes.BOOL

WM_HOTKEY      = 0x0312
_WM_REREGISTER = 0x8000   # WM_APP: troca de tecla (wParam=vk, lParam=modificadores)
_WM_QUIT_LOOP  = 0x8001   # WM_APP+1: encerra o loop
_HOTKEY_ID     = 1
MOD_NOREPEAT   = 0x4000

_MODS = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001,
         "shift": 0x0004, "win": 0x0008, "windows": 0x0008, "super": 0x0008}

_EXTRA_VK = {"space": 0x20, "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
             "enter": 0x0D, "return": 0x0D, "insert": 0x2D, "delete": 0x2E,
             "home": 0x24, "end": 0x23, "pageup": 0x21, "prior": 0x21,
             "pagedown": 0x22, "next": 0x22}


def parse(key: str):
    """'f6' / 'ctrl+shift+p' -> (vk, modificadores). None se não der pra mapear."""
    if not key:
        return None
    parts = [p.strip().lower() for p in key.split("+") if p.strip()]
    if not parts:
        return None
    mods, main = 0, None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        else:
            main = p  # última tecla "de verdade" vence
    if main is None:
        return None
    vk = _vk(main)
    if vk is None:
        return None
    return vk, mods


def _vk(name: str):
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit():
        n = int(name[1:])
        if 1 <= n <= 24:
            return 0x70 + (n - 1)
    return _EXTRA_VK.get(name)


class HotkeyManager:
    """Registra um atalho global e chama on_trigger quando ele é apertado."""

    def __init__(self, on_trigger):
        self._on_trigger = on_trigger
        self._thread_id = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def set_hotkey(self, key: str) -> bool:
        """Troca a tecla. Retorna False se a tecla não puder ser mapeada."""
        parsed = parse(key)
        if parsed is None or self._thread_id is None:
            return False
        vk, mods = parsed
        return bool(_user32.PostThreadMessageW(
            self._thread_id, _WM_REREGISTER, vk, mods | MOD_NOREPEAT))

    def stop(self):
        if self._thread_id is not None:
            _user32.PostThreadMessageW(self._thread_id, _WM_QUIT_LOOP, 0, 0)

    def _run(self):
        self._thread_id = _kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        # força a criação da fila de mensagens desta thread
        _user32.PeekMessageW(ctypes.byref(msg), None, 0x0400, 0x0400, 0)
        self._ready.set()

        registered = False
        while True:
            ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                try:
                    self._on_trigger()
                except Exception:
                    pass
            elif msg.message == _WM_REREGISTER:
                if registered:
                    _user32.UnregisterHotKey(None, _HOTKEY_ID)
                    registered = False
                # wParam = vk, lParam = modificadores
                if _user32.RegisterHotKey(None, _HOTKEY_ID, msg.lParam, msg.wParam):
                    registered = True
            elif msg.message == _WM_QUIT_LOOP:
                if registered:
                    _user32.UnregisterHotKey(None, _HOTKEY_ID)
                break
