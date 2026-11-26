# ARMath 2.0

O ARMath 2.0 usa marcadores ArUco para projetar superfícies matemáticas sobre o vídeo da câmera. Os nove marcadores da versão 1.0 também funcionam nesta edição.

## O que mudou na versão 2.0

A câmera e a equação ficam à esquerda. Na coluna lateral, o painel **Visualização** reúne **Eixos 3D** e **Caixa**. O painel **Transformação** reúne escala, rotação e redefinição dos ajustes. Em **Plano de corte**, é possível deslocar um plano vermelho com malha amarela e observar a interseção em branco.

O seletor de tema fica ao lado da marca **ARMath**, no canto superior direito. O menu **Ajuda** reúne o guia rápido, a pasta de marcadores, o [manual em PDF](docs/Manual_ARMath.pdf), o GitHub do projeto e a janela **Sobre o ARMath**.

## Telas do aplicativo

As capturas mostram a interface do ARMath 2.0 com quadros simulados da câmera.

**Painel Visualização com a caixa ativada**

![Elipsoide delimitado por uma caixa de arestas brancas no ARMath 2.0](docs/imagens/armath-2-caixa.png)

**Modo escuro com plano de corte e interseção em branco**

![ARMath 2.0 no modo escuro, com a sela cortada por um plano vermelho e os controles à direita](docs/imagens/armath-2-escuro.png)

**Modo claro com os eixos 3D ativados**

![ARMath 2.0 no modo claro, com um toro rotacionado e seus eixos 3D](docs/imagens/armath-2-claro.png)

**Janela Sobre**

![Janela Sobre do ARMath 2.0 com o logotipo verde, a descrição e os créditos](docs/imagens/armath-2-sobre.png)

## Como executar

Na pasta `ARMAth_2.0`, instale as dependências, caso ainda não estejam instaladas, e execute o aplicativo.

```powershell
python -m pip install -r requirements.txt
python armath.py
```

Os PNGs para imprimir estão na pasta `marcadores`. Para gerar mais cópias, execute `python armath.py --gerar-marcadores marcadores`.

## Controles

- **Escala** ajusta o tamanho da superfície de **1× a 3×**, com valor inicial de **1×**.
- **Rotação X, Y e Z** gira a malha em torno do centro do marcador. Cada controle vai de **−180° a 180°**.
- **Eixos 3D** mostra os eixos X, Y e Z, que giram junto com a superfície.
- **Caixa** mostra as arestas brancas de uma caixa retangular que delimita a superfície. A caixa acompanha a escala e a rotação da figura.
- **Redefinir** volta à escala **1×** e às três rotações em **0°**.
- O **ícone de seta circular** ao lado de cada valor restaura apenas aquele controle.
- **Mostrar plano** exibe um plano vermelho preenchido com malha amarela. Escolha um único plano entre **XY**, **XZ** e **YZ**. O contorno branco destaca a interseção quando houver corte.
- O **deslocamento do plano** começa na origem, no centro do deslizador. As duas pontas do controle levam o plano ao menor e ao maior valor da superfície no eixo perpendicular ao corte. O alcance acompanha a escala da figura. Use a seta circular para voltar à origem.
- **Modo claro** ativa o tema claro. Com ele ativo, o seletor passa a exibir **Modo escuro**. O aplicativo abre no tema escuro.
- **Salvar foto** captura o quadro com a superfície no tamanho e na orientação atuais.

A malha 3D aparece em verde neon sobre o vídeo. O nome e a equação são exibidos abaixo da prévia.
