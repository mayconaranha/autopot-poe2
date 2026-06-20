# AutoPoE — auto flask pro Path of Exile 2

Toma o flask de vida (e de mana) sozinho quando a barra cai abaixo do limite que
você escolher. Diferente de jogos com barra de vida reta, no PoE2 a vida é um
globo redondo, então aqui a leitura é feita por OCR em cima dos números do globo
(`1.317 / 1.513`). Como ele lê os dois números, o percentual continua certo mesmo
quando você upa e a vida máxima muda — não precisa recalibrar nada.

> **Aviso:** a GGG proíbe automação no PoE2 e isso pode dar ban. Use por sua conta
> e risco.

---

## O que baixar

**Não precisa instalar nada.** Vá em **[Releases](../../releases)** e baixe o
`AutoPoE.exe`. Ele já vem com tudo dentro (o motor de OCR inclusive). É só Windows.

> Na primeira vez o Windows SmartScreen pode avisar que é de "editor
> desconhecido" (o .exe não é assinado). Clique em **Mais informações → Executar
> assim mesmo**.

A primeira leitura demora alguns segundos porque o programa carrega o modelo de
OCR uma vez.

---

## Como usar

1. Abra o PoE2, de preferência em **janela sem bordas** (borderless).
2. Abra o `AutoPoE.exe`.
3. Em **Calibração**, clique em **Números Vida** e arraste um retângulo por cima
   do texto da vida no globo (`1.317/1.513`). Faça o mesmo em **Números Mana** se
   quiser flask de mana automático.
4. Clique em **Testar Leitura** — o log embaixo mostra o que o OCR leu e o
   percentual. Se bateu com o jogo, está pronto.
5. Ajuste:
   - **Vida pot abaixo de** / **Mana pot abaixo de** — o limite que dispara o flask.
   - **Tecla flask vida / mana** — a tecla de cada flask (padrão `1` e `2`).
   - Botão **ON/OFF** em cada globo (VIDA e MANA) — liga ou desliga aquele flask
     sem precisar apagar a calibração.
6. Aperte **F6** pra ligar/desligar o auto flask a qualquer momento. Quer outra
   tecla? Clique no botão ao lado de **Tecla liga/desliga** e aperte a que quiser.

### Teclas automáticas

Embaixo das configurações dá pra cadastrar teclas que são apertadas num intervalo
fixo — útil pra skills de buff que você quer reaplicar de tempos em tempos.

---

## Rodar pelo código (em vez do .exe)

Precisa de Python 3.10+.

```
pip install -r requirements.txt
python autopoe.py
```

## Gerar o .exe você mesmo

```
build.bat
```

Esse script cria um ambiente isolado, instala só o necessário (com
`opencv-python-headless` pra deixar o arquivo leve) e gera o `AutoPoE.exe` na
pasta do projeto.

## Testes

```
python -m pytest tests/ -q
```
