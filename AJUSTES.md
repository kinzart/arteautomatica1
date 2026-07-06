# Referência de `ajustes.json`

Os comandos abaixo são próprios deste gerador. Eles não fazem parte de um
padrão oficial de JSON ou do Photoshop.

Cada ajuste fica dentro de `formato -> slot`, por exemplo:

```json
{
  "feed": {
    "txt_data_dia": {
      "tamanho": 120,
      "tracking": -20,
      "offset_x": 0,
      "offset_y": 0
    }
  }
}
```

## Campos de texto

- `fonte`: `"anton"`, `"archivo"`, `"archivo_black"` ou `"mono"`.
- `tamanho`: tamanho fixo da fonte em pixels; desativa o autoshrink.
- `tamanho_max`: teto do autoshrink, não um tamanho fixo.
- `tamanho_min`: piso do autoshrink.
- `tracking`: espaçamento entre caracteres em milésimos de EM. Valores
  positivos afastam; negativos aproximam. Exemplos úteis: `-50`, `0`, `50`.
- `espacamento_linhas`: multiplicador do espaço vertical entre linhas.
  O padrão é `1.2`; exemplos: `0.9` aproxima e `1.5` afasta.
- `escala_y`: estica visualmente a altura do texto texturizado; `1` mantém.
- `escala_x`: estica visualmente a largura do texto texturizado; `1` mantém.
- `caixa_x`: posição horizontal absoluta da caixa.
- `ajustar_tracking`: ajusta tamanho/tracking automaticamente para preencher a caixa.
- `preenchimento_largura`: fração da caixa ocupada, normalmente entre `0.85` e `1`.
- `layout_artista_auto`: no `txt_artista`, força caixa alta e distribui nomes
  compostos em no máximo duas linhas equilibradas. O padrão é `true`.
- `gap_linhas_min`: distância mínima em pixels entre a tinta real de duas
  linhas; impede que acentos invadam ou encubram a linha anterior.
- `desgaste`: erosão da tinta pela textura, entre `0` e `1`.
- `offset_x`: move o texto; positivo para a direita, negativo para a esquerda.
- `offset_y`: move o texto; positivo para baixo, negativo para cima.
- `caixa_largura`: substitui a largura da caixa herdada do PSD.
- `caixa_altura`: substitui a altura da caixa herdada do PSD.
- `alinhamento`: `"esquerda"`, `"centro"` ou `"direita"` dentro da caixa.
- `cor`: cor sólida em `"#RRGGBB"`, por exemplo `"#C77822"`.
- `opacidade`: opacidade total do texto entre `0` e `1`.
- `textura`: caminho da imagem de textura relativo à raiz do projeto.
- `textura_opacidade`: intensidade da textura, entre `0` e `1`.
- `textura_blend`: `"multiply"` ou `"overlay"`.

`tracking` participa do cálculo do autoshrink. Se o texto precisar permanecer
em um tamanho exato, combine-o com `tamanho`; se precisar sempre caber na caixa,
use `tamanho_max` no lugar de `tamanho`.

## Campos de `foto_artista`

- `zoom`: escala manual; `1` mantém, `1.15` amplia 15% e `1.6` amplia 60%.
  O limite de segurança é `5`; não use porcentagens como `60`. Como a foto já
  chega em `fit_cover`, valores abaixo de `1` não revelam área adicional.
- `offset_x`: move a foto em pixels; positivo para a direita.
- `offset_y`: move a foto em pixels; positivo para baixo.
- O pan nunca altera o zoom. Quando o offset atinge a margem disponível para o
  zoom atual, ele para na borda. Aumente `zoom` explicitamente para ganhar mais
  espaço de movimento sem revelar bordas vazias.
- `espelhar_horizontal`: `true` troca esquerda e direita da foto; `false`
  mantém sua orientação original. A máscara do PSD não é espelhada.
- `brilho`: multiplicador; `1` mantém, `0.9` escurece, `1.1` clareia.
- `contraste`: multiplicador; `1` mantém.
- `saturacao`: multiplicador; `1` mantém e `0` remove a cor.
- `nitidez`: multiplicador; `1` mantém.
- `temperatura`: de aproximadamente `-100` (frio) a `100` (quente); `0` mantém.
- `fusao_frac`: largura proporcional da fusão sintética, usada somente quando
  o PSD não possui máscara própria para a foto.
- `mascara_offset_x` / `mascara_offset_y`: deslocam a máscara real em pixels.
- `mascara_escala`: escala da máscara em torno do centro; `1` mantém.
- `mascara_blur`: suavidade da borda em pixels; `0` mantém.
- `mascara_contraste`: dureza da transição; `1` mantém, valores maiores endurecem.
- `mascara_opacidade`: intensidade geral entre `0` e `1`.
- `mascara_inverter`: `true` inverte áreas visíveis e ocultas.

Exemplo:

```json
"foto_artista": {
  "zoom": 1.12,
  "offset_x": 20,
  "offset_y": -35,
  "espelhar_horizontal": true,
  "brilho": 0.95,
  "contraste": 1.15,
  "saturacao": 0.9,
  "temperatura": 8
}
```

Comandos desconhecidos geram erro. Isso evita que um erro de digitação seja
silenciosamente ignorado.

## Rodapé variável

`txt_local_nome`, `txt_local_bairro` e `txt_local_endereco` aceitam todos os
campos de texto acima e recebem seus conteúdos do `job.json`. `linhas_rodape`
aceita `offset_x`, `offset_y`, `largura_1`, `largura_2`, `espessura` e `cor`.
