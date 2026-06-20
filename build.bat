@echo off
cd /d "%~dp0"
REM Build limpo: cria um venv dedicado so com o necessario e usa opencv-python-headless.
REM Isso deixa o .exe bem mais leve (~93MB em vez de ~230MB) e o build mais rapido.

echo Criando venv de build...
python -m venv .venv-build
call .venv-build\Scripts\activate.bat

echo Instalando dependencias (headless)...
python -m pip install --upgrade pip
REM RapidOCR exige opencv-python (full); instalamos sem deps e pomos o headless na mao.
pip install numpy opencv-python-headless pyclipper shapely six pyyaml onnxruntime Pillow mss pydirectinput
pip install rapidocr_onnxruntime --no-deps
pip install pyinstaller

echo.
echo Gerando AutoPoE.exe...
pyinstaller --onefile --noconsole --name AutoPoE ^
  --collect-all rapidocr_onnxruntime ^
  --collect-all onnxruntime ^
  --hidden-import pydirectinput ^
  --hidden-import mss ^
  --hidden-import numpy ^
  --hidden-import cv2 ^
  autopoe.py

echo.
if exist dist\AutoPoE.exe (
    copy /Y dist\AutoPoE.exe AutoPoE.exe >nul
    echo Pronto! AutoPoE.exe gerado na pasta do projeto.
) else (
    echo ERRO: build falhou. Verifique o log acima.
)
pause
