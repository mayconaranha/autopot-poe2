# AutoPoE — design

AutoPot para Path of Exile 2. Nasce do AutoPot do Hero Siege (`../autopot-hs`),
mas troca o miolo de detecção: no HS o HP é uma barra horizontal; no PoE2 é um
globo circular que enche de baixo pra cima e tem arte estilizada (reflexos,
borda dourada). Tentar ler o nível do líquido por pixel é frágil por causa disso.

Como os números de vida (`1.317 / 1.513`) ficam sempre na tela, a detecção é por
OCR: leio `atual` e `máx` e calculo `atual / máx × 100`. Vantagem extra: a vida
máxima muda quando você upa de level, e lendo os dois números o percentual se
ajusta sozinho — não precisa recalibrar nada.

## Decisões

- **OCR: RapidOCR (onnxruntime).** Instala por pip, já vem com os modelos, não
  precisa instalar nada no Windows nem configurar PATH. Mantém o build do .exe
  limpo. Tesseract seria mais leve, mas exige instalar o binário e apontar o
  caminho — atrito que não compensa aqui.
- **Modelo de poções simples:** 1 flask de vida (tecla padrão `1`) + 1 flask de
  mana (tecla padrão `2`), cada um com seu threshold. Sem a lógica de 4 slots /
  detecção de vazio do HS, que não se aplica ao PoE2.
- **Reaproveita do HS:** UI Tkinter, overlay de calibração, `config.json`,
  hotkey F6, teclas automáticas (skills no intervalo).

## Fluxo

Loop a cada 0.1s, OCR limitado a ~150ms (não precisa ler mais rápido). Se
`vida% < threshold` e o cooldown passou → aperta a tecla do flask de vida.
Mesma lógica pra mana. Teclas automáticas seguem como no HS.

## Robustez

Se o OCR falhar a leitura (menu aberto, número sumiu, leitura suja), **seguro o
último valor bom e não tomo pot** — melhor perder uma poção do que gastar à toa.
Falhas seguidas aparecem no log da UI.

## Config

`life_region`, `mana_region`, `hp_threshold`, `mana_threshold`, `life_key`,
`mana_key`, `keypresses`.

## Testes

- Parser isolado: `"1.317/1.513"` → `(1317, 1513)`, com variações de formato e
  ruído de OCR. Não depende de imagem nem do jogo.
- Detecção OCR: validação manual em jogo, via botão "Testar Leitura" na UI.
