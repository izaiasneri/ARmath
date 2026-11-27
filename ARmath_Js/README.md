# ARMath Web

Versão em HTML, CSS e JavaScript do ARMath 2.0, criado pelo Prof. Izaias Neri para o ensino de Cálculo III. A aplicação é estática e não depende de Node.js, Python ou bibliotecas externas.

## Abrir e usar

- Abra `index.html` no navegador. **Marcadores** abre a página dos cartões em outra aba. Cada cartão pode ser impresso ou baixado em PNG.
- Para uso com câmera, abra pelo endereço `localhost` de um servidor estático ou publique a pasta em uma hospedagem HTTPS. A disponibilidade da câmera ao abrir o arquivo diretamente varia conforme o navegador. Clique em **Ativar câmera**, conceda a permissão e mostre o marcador inteiro, com a margem branca visível.
- Use **Selecionar câmera** para trocar de dispositivo, **Congelar imagem** para ajustar a superfície sobre um quadro fixo e **Salvar foto** para exportar um PNG. Em **Arquivo → Encerrar sessão**, a webcam é liberada.
- Os controles permitem ajustar a escala e as rotações X, Y e Z, mostrar eixos, caixa e grade e explorar cortes XY, XZ e YZ.

## Cartões ArUco

Os PNGs em `static/marcadores` são os mesmos da versão Flask, do dicionário ArUco `DICT_4X4_50`.

| Cartão | Superfície |
| --- | --- |
| 0 | Paraboloide elíptico |
| 1 | Paraboloide hiperbólico (sela) |
| 2 | Ondas senoidais |
| 3 | Elipsoide |
| 4 | Toro |
| 5 | Hiperboloide de uma folha |
| 6 | Cone duplo |
| 7 | Superfície gaussiana |
| 8 | Ondulações concêntricas |
| 9 | Função personalizada (inicialmente `x+y`) |

O cartão 9 aceita expressões em `x` e `y` no domínio [−5, 5] × [−5, 5]. Experimente `x^2-y^2`, `exp(x+y)` ou `sqrt(x^2+y^2)`. Também estão disponíveis `pi`, `e`, `sin`, `cos`, `tan`, `log` e `abs`. Use `*` para multiplicação e `^` ou `**` para potência.

## Implementação

`static/vision.js` reconhece os cartões originais e projeta a geometria a partir dos seus cantos. `static/surfaces.js` calcula malhas, valida expressões e renderiza as superfícies e os cortes com Canvas. Os quadros da câmera são processados no próprio navegador.
