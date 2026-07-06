# Review técnico do editor visual — 2026-07-06

## Problemas confirmados e corrigidos

1. **Cor travava o preview durante digitação.** O campo vazio/intermediário era
   enviado ao renderer e gerava traceback `#RRGGBB`. Agora há seletor de cor,
   validação antes do render e erro resumido.
2. **Opacidade falhava em textos sem textura.** O alpha era escrito diretamente
   no RGBA e perdido na conversão final para RGB. Agora o texto é desenhado em
   camada transparente e composto corretamente. Testado em 0%, 50% e 100%.
3. **Sliders exibiam floats arbitrários.** `ttk.Scale` não respeitava o passo
   declarado. Agora cada valor é quantizado: pixels/tamanhos inteiros e fatores
   com uma ou duas casas conforme o campo.
4. **Conteúdo textual não era editável.** Artista, edição, data, hora, local,
   bairro e endereço agora possuem campo de conteúdo no respectivo slot.
5. **Risco de alterar jobs durante experimentos.** Conteúdo usa
   `jobs/job.editor.tmp.json`. O job original só muda no botão explícito
   **Salvar textos no job**, com backup prévio.
6. **Erros exibiam traceback completo.** O editor agora mostra somente a causa
   final relevante.
7. **Temporários antigos podiam guardar `#RGB`.** A abertura agora migra esse
   formato automaticamente para `#RRGGBB`, sem perder os demais ajustes.

## Invariantes preservados

- `ajustes.json` nunca é salvo automaticamente;
- promoção do temporário cria backup;
- preview rápido não abre PSD;
- render PSD continua em background;
- `painel.py` não foi substituído;
- merge de ajustes não remove campos existentes.

## Limitações deliberadas

- `render_fast.py` é aproximado: não reproduz perfeitamente adjustment layers,
  blend modes e textura tipográfica do PSD;
- o eixo X do bloco de data permanece travado em `ENTRADA GRATUITA`;
- elementos fixos sem slot não possuem edição de conteúdo;
- escala/opacidade usam ponto internamente no JSON, mesmo que o sistema use
  vírgula como separador local.

## Validação

- testes de layout, persistência, comparação, render rápido e opacidade;
- smoke test da interface e edição textual temporária;
- geração normal, temporária e rápida;
- hash do `ajustes.json` e do job original preservados durante os testes.
