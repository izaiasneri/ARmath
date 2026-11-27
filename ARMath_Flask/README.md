# ARMath Web

Versão Flask do ARMath 2.0, aplicativo de realidade aumentada para o ensino de Cálculo III criado pelo Prof. Izaias Neri.

## Executar no Windows

Na pasta do projeto, use o PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run
```

Abra [http://127.0.0.1:5000](http://127.0.0.1:5000). Clique em **Ativar câmera**, conceda permissão no navegador e mostre um marcador ArUco com a margem branca visível. Em **Marcadores**, baixe os PNGs ou clique em **Demonstrar** para explorar uma superfície sem webcam.

## Usar em aula

- Os cartões de 0 a 8 exibem as superfícies do ARMath 2.0. O cartão 9 exibe a função personalizada. Experimente `x^2-y^2`, `exp(x+y)` ou `sqrt(x^2+y^2)` no domínio `[-5, 5] × [-5, 5]`.
- Ative eixos, caixa e grade. Ajuste a escala entre 1× e 3×, gire em X, Y e Z e explore cortes XY, XZ e YZ.
- Congele o quadro para continuar ajustando a superfície e salve a imagem aumentada em PNG. Use **Selecionar câmera** para trocar de dispositivo e **Arquivo → Encerrar sessão** para liberar a webcam.
- O menu **Ajuda** inclui o manual, os marcadores e instruções de uso.

Para gerar novamente os cartões:

```powershell
.\.venv\Scripts\python.exe -m flask --app app gerar-marcadores static/marcadores
```

## Arquitetura

O navegador captura a câmera e envia um quadro JPEG por vez ao Flask. O OpenCV reconhece os marcadores e devolve o quadro com a sobreposição e os dados do corte. O servidor processa os quadros em memória. A expressão personalizada é mantida na página durante a sessão. O navegador exige localhost ou HTTPS para acessar a câmera.
