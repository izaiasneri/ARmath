# ARMath 2.0

O **ARMath 2.0** é um aplicativo de realidade aumentada para o ensino de **Cálculo III**, criado pelo Prof. Izaias Neri. Ao reconhecer um cartão ArUco na webcam, o aplicativo projeta uma superfície tridimensional sobre o vídeo. Use os controles para girar a figura, relacioná-la à equação e observar sua interseção com planos.

## Como começar

Na pasta `ARMAth_2.0`, instale as dependências e abra o aplicativo:

```powershell
python -m pip install -r requirements.txt
python armath.py
```

Mostre um [marcador ArUco](marcadores) inteiro à webcam, com a margem branca visível. Você pode imprimir o PNG ou exibi-lo em outro dispositivo. Os marcadores **0 a 8** da versão 1.0 continuam funcionando. O [marcador 9](marcadores/marcador_9.png) é reservado para a função personalizada.

Para gerar os arquivos PNG novamente, execute `python armath.py --gerar-marcadores marcadores`.

## Interface e recursos

As imagens abaixo são capturas da interface do aplicativo com quadros simulados da câmera.

À esquerda, a prévia mostra o vídeo e a superfície projetada. O **ID do cartão** ativo fica alinhado à direita, entre o vídeo e a área que mostra o nome e a equação da superfície. Enquanto não há um marcador reconhecido, o campo do ID exibe um traço. À direita, os painéis **Função personalizada**, **Visualização**, **Transformação** e **Plano de corte** ficam na mesma coluna. O status da webcam aparece à direita do título **Câmera**.

### Função personalizada

1. Digite a expressão à direita do rótulo matemático **f(x,y) =**.
2. Clique em **Plotar** ou pressione **Enter**. Use o **marcador 9** para visualizar a superfície e a fórmula renderizada em LaTeX.
3. Clique em **Limpar**, identificado pelo ícone de vassoura, para apagar o campo e voltar a digitar. O gráfico e a fórmula exibidos permanecem até a próxima plotagem válida.

A expressão inicial é `x+y`. A função personalizada vale durante a sessão, e uma expressão inválida preserva a última superfície válida.

Experimente `exp(x+y)`, `x^2-y^2` ou `sqrt(x^2+y^2)`. Use `*` para multiplicar e `^` ou `**` para potências. O marcador 9 avalia a função em uma malha no domínio **[−5, 5] × [−5, 5]**. O aplicativo reduz a malha para a exibição, enquanto a grade e os cortes indicam as coordenadas matemáticas.

![Marcador 9 com função exponencial, equação renderizada e botões Plotar e Limpar](docs/imagens/armath-2-funcao-personalizada.png)

### Visualização e transformação

| Controle | Como funciona |
| --- | --- |
| **Eixos** | Mostra os eixos coloridos com as letras X, Y e Z em branco. |
| **Caixa** | Desenha as arestas brancas da caixa que delimita a superfície. |
| **Grade** | Mostra três planos de referência translúcidos: XY amarelo, XZ azul e YZ vermelho. As linhas são brancas e tracejadas, e os números indicam coordenadas da superfície. |
| **Escala** | Ajusta a ampliação de **1× a 3×**. |
| **Rotação X, Y e Z** | Gira a superfície ao redor do marcador, de **−180° a 180°** em cada eixo. Os elementos de visualização acompanham a rotação. |
| **Redefinir** | Restaura a escala para **1×** e as rotações para **0°**. As setas circulares dos seletores redefinem cada valor individualmente. |

**Grade e eixos ativados**

![Elipsoide com eixos rotulados e três planos de grade coloridos](docs/imagens/armath-2-grade.png)

**Caixa ativada**

![Elipsoide dentro da caixa de arestas brancas](docs/imagens/armath-2-caixa.png)

### Plano de corte

Ative **Mostrar plano** e selecione **XY**, **XZ** ou **YZ**. As opções e o controle de **Deslocamento** ficam visíveis e desativados enquanto o plano está desligado. Quando ativo, o painel exibe a coordenada do corte no eixo perpendicular, como **x = 0** para YZ. A interseção aparece em branco quando o plano corta a superfície.

![Corte da sela com o plano XY e a coordenada Z indicada no painel](docs/imagens/armath-2-escuro.png)

### Congelar imagem e salvar foto

**Congelar imagem** conserva o quadro atual para que você possa girar a superfície, ajustar a escala e explorar os cortes sem segurar o marcador na frente da webcam. Clique em **Retomar vídeo** para voltar à transmissão. **Salvar foto** exporta em PNG o quadro exibido com a sobreposição.

![Imagem congelada com plano de corte visível e botão Retomar vídeo](docs/imagens/armath-2-congelado.png)

### Estado da câmera e recuperação

| Estado | O que aparece |
| --- | --- |
| **Conectando** | A câmera está em inicialização. [Ver captura](docs/imagens/armath-2-conectando.png). |
| **Ao vivo · Aguardando marcador** | A transmissão está ativa. Mostre um marcador com os quatro cantos visíveis. [Ver captura](docs/imagens/armath-2-aguardando-marcador.png). |
| **Ao vivo · Marcador reconhecido** | A superfície e a equação estão disponíveis para exploração. |
| **Imagem congelada** | O quadro exibido fica fixo, com os ajustes de visualização disponíveis. |
| **Indisponível** | Verifique a webcam e as permissões do Windows. Use o botão amarelo **Reiniciar câmera** para tentar novamente. |

![Câmera indisponível com botão amarelo Reiniciar câmera](docs/imagens/armath-2-camera-indisponivel.png)

### Temas claro e escuro

O seletor ao lado da marca ARMath indica o tema que será ativado. O aplicativo abre no tema escuro. Ao mudar para o tema claro, o seletor passa a mostrar **Modo escuro**.

![Tema claro com o toro e seus eixos](docs/imagens/armath-2-claro.png)

## Menus

### Arquivo

![Menu Arquivo aberto com a opção Selecionar câmera](docs/imagens/armath-2-menu-arquivo.png)

| Item | O que faz |
| --- | --- |
| **Salvar foto** (`Ctrl+S`) | Salva o quadro exibido em PNG. |
| **Eixos 3D** (`Ctrl+E`) | Alterna o controle **Eixos** do painel **Visualização**. |
| **Reiniciar câmera** | Tenta reconectar a webcam. A opção aparece quando a câmera está indisponível. |
| **Selecionar câmera** | Permite escolher outra webcam pelo índice. **0** é o índice padrão. |
| **Sair** (`Ctrl+Q`) | Fecha o aplicativo. |

![Janela para escolher o índice da câmera](docs/imagens/armath-2-selecionar-camera.png)

### Ajuda

![Menu Ajuda aberto com os ícones de cada item](docs/imagens/armath-2-menu-ajuda.png)

| Item | O que faz |
| --- | --- |
| **Como começar** | Mostra três passos para usar a webcam e reconhecer o primeiro marcador. |
| **Abrir pasta de marcadores** | Abre a pasta com os PNGs originais. |
| **Manual do usuário** | Abre o [manual em PDF](docs/Manual_ARMath.pdf), com instruções e marcadores para impressão. |
| **GitHub do projeto** | Abre a [página do ARMath 2.0 no GitHub](https://github.com/izaiasneri/ARmath/tree/main/ARMAth_2.0). |
| **Sobre o ARMath** | Exibe a versão e os créditos do aplicativo. |

![Janela Sobre o ARMath 2.0](docs/imagens/armath-2-sobre.png)
