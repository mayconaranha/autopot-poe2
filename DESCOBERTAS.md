# Descobertas — AutoPoE

## OCR do globo: upscale puro bate threshold

Testei três pré-processamentos pra ler os números do globo com RapidOCR:

- imagem crua → leitura suja (`'1.317/ 7/1.513'`)
- resize 3x cúbico → leitura limpa (`'1.317/1.513'`)
- resize 3x + threshold Otsu → quebrou (`'51 13'`)

Conclusão: pra esses dígitos claros sobre fundo escuro, **só o upscale cúbico 3x**
dá o melhor resultado. Binarizar atrapalha o RapidOCR. O `detect._preprocess`
ficou só com o resize.

## Tamanho do .exe

Build inicial deu **397MB** porque o `.venv` é compartilhado e o PyInstaller
arrastou torch, pandas, scipy, PyQt6, pyarrow etc. Excluindo essas libs com
`--exclude-module` no `build.bat`, caiu pra **230MB**. O piso é o onnxruntime +
opencv, que são o necessário pro OCR rodar self-contained.

## Validação do exe congelado

OCR só carrega o modelo na primeira leitura, então rodar a GUI não prova que
funciona empacotado. Adicionei `AutoPoE.exe --selftest`: roda o OCR numa imagem
sintética e grava o resultado. No exe final leu `1.317/1.513` → 87%, confirmando
que onnxruntime/RapidOCR sobrevivem aos excludes do build.
