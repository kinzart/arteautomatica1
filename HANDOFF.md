# HANDOFF — Gerador de Artes FBS · PSD-driven (BRIEF_v3 + HANDOFF_v4)

Estado após a implementação da PARTE B (Python) do `BRIEF_v3_PSD_DRIVEN_CODEX.md`
e, em seguida, do `HANDOFF_v4_FIDELIDADE_FOTO.md` (fidelidade da foto +
posicionamento por detecção de rosto). Ver seção **"HANDOFF_v4"** abaixo pro
que mudou na segunda rodada — algumas coisas descritas mais abaixo neste
arquivo (risco #3, principalmente) foram **superadas** pela v4; deixei uma
nota apontando pra lá em vez de reescrever tudo.

## O que está pronto

- **Pipeline PSD-driven completo pro formato `feed`** (1080×1350): abre o PSD,
  extrai as 7 camadas variáveis, oculta-as, compõe a base, redesenha foto +
  6 textos por cima herdando fonte/cor/tracking do PSD original.
- `python gerar.py` gera `outputs/fbs28_feed.png` a partir de `jobs/job.json`.
- Autoshrink + quebra de linha em `txt_artista`: `MARIA APARECIDA DOS SANTOS
  BLUES TRIO` cabe em 3 linhas sem estourar o bbox (testado).
- Data `2026-07-14` → `JUL / 14 / TERÇA` (testado, bate com o critério de aceite).
- 3 caminhos de erro testados (foto ausente, PSD ausente, campo obrigatório
  ausente): log claro em `logs/fbs.log`, `exit code 1`, nenhum PNG gerado.
- PSD template **não é modificado em disco** — hash SHA-256 conferido igual
  antes/depois de rodar (`65339798...9f7`). O código só usa `layer.visible =
  False` em memória e `psd.composite()`; nunca chama `.save()`.

## Ajustes finos sem tocar no PSD — `ajustes.json`

Arquivo opcional na raiz (`fbs-gerador/ajustes.json`). Se não existir, nada
muda (comportamento 100% herdado do PSD, como antes). Estrutura:
`{"<formato>": {"<slot>": {...overrides...}}}`. Overrides disponíveis por
slot de texto (`txt_*`):

- `tamanho_max` / `tamanho_min` (int, px): teto/piso do autoshrink. Por
  padrão o teto é derivado da altura do bbox — use isso pra forçar um
  tamanho maior/menor do que o autoshrink escolheria sozinho.
- `offset_x` / `offset_y` (int, px): nudge de posição a partir do
  topo-esquerda do bbox original.
- `textura` (path, relativo à raiz do projeto): imagem de textura misturada
  dentro do glifo — recria o efeito de *Pattern Overlay* do Photoshop
  (brief §1.2) pro texto novo, que por padrão usa só a cor média sampleada
  (sólida, sem padrão). Texturas disponíveis em `assets/textura_*.png`.
- `textura_opacidade` (float 0-1, default 0.7) e `textura_blend`
  (`"multiply"` default ou `"overlay"`).

Pra `foto_artista`: `fusao_frac` (float 0-1, default 0.15) — largura da
faixa de fusão gradiente no lado que encosta no texto.

O `ajustes.json` atual já vem com textura aplicada em `txt_artista`,
`txt_data_mes`, `txt_data_dia` (opacidade 0.7) e `txt_edicao` (0.3, mais sutil)
— replica o checklist do brief §1.2(a)(b)(c) sem precisar editar o PSD. Edite
os valores e rode `python gerar.py` de novo pra iterar; não precisa reabrir
o Photoshop.

**Fora do escopo desse mecanismo:** grain e vinheta globais continuam vindo
só do PSD (via `compor_base`/`compor_overlay_acima`) — não há override de
código pra intensidade deles nesta rodada, porque duplicar esse efeito por
cima do que o PSD já aplica arrisca ficar mais forte que o pretendido. Se
precisar ajustar isso, o caminho é no Photoshop mesmo.

## HANDOFF_v4 — Fidelidade da foto + posicionamento por detecção de rosto

Implementado em cima do estado do BRIEF_v3 acima. Resolve o problema "a foto
sai crua" (mais clara, saturada, borda dura, comparada à referência).

### Workstream A — fidelidade tonal da foto

**Diagnóstico confirmado:** a foto nova nunca recebia os adjustment layers
(`Brilho/Contraste 2`: contrast=9; `Exposição 1`: exposure=-0.42, gamma=1.07)
nem a máscara real de fusão do PSD (o pipeline v3 colava a foto pronta por
cima da base já achatada — a foto pulava tudo isso).

**A primeira tentativa de correção (fiel ao texto do HANDOFF_v4 §1.1-1.3)
reimplementou os adjustment layers com numpy** (`aplicar_brightness_contrast`,
`aplicar_exposure`) e tentou isolar "o que fica acima da foto" recompondo o
PSD com as camadas de baixo ocultas. **Isso não funcionou:** qualquer camada
acima da foto com `blend_mode` diferente de `NORMAL` — nesse PSD, o grain
(`textura_grain`, Overlay, opacidade 25%) e uma textura de luz (Lighten) —
produz um resultado errado quando isolada sem o fundo real embaixo (o motor
de blend do psd-tools assume um fundo preto implícito, e a camada Overlay
isolada vira uma "lavagem" ~38% preta cobrindo a região inteira). Resultado:
round-trip com SSIM 0.77 — pior que não fazer nada.

**Solução final (bem mais simples e 100% precisa):** em vez de reimplementar
blend modes na mão, `psd_reader.compor_com_foto_nova` **insere a foto nova
como uma camada de pixel de verdade** (`PixelLayer.frompil`) na MESMA posição
da pilha que a `foto_artista` original (oculta), com a máscara real da
camada já embutida como canal alpha. Um único `psd.composite()` depois
resolve tudo — adjustment layers, grain, blend modes — exatamente como o
Photoshop, porque é o mesmo motor de composição, com o fundo real presente.
Substituiu inteiramente `compor_fatia_abaixo`/`extrair_ajustes_tonais`/
`aplicar_brightness_contrast`/`aplicar_exposure`/`compor_overlay_acima` (pra
foto) — removidos do código. `compositor.desenhar_foto` também foi removido;
virou `compositor.preparar_foto_rgba` (só monta o RGBA: fit_cover/posição +
máscara como alpha) + `psd_reader.compor_com_foto_nova` (insere e compõe).

**Validação (round-trip, `testar_roundtrip.py`):** extrai a foto original do
PSD (`foto_layer.topil()`), gera a arte de novo com ela, compara com
`outputs/_debug_original_com_variaveis.png`. Métrica restrita à região da
foto **excluindo onde texto variável se sobrepõe** (GONZALO ARAYA, JUL/07
etc. são desenhados pelo Pillow, não pelo motor nativo do Photoshop — vão
sempre divergir da referência por um motivo à parte da fidelidade
fotográfica, que é o que esse teste quer isolar). Resultado:
**SSIM 0.9561** (mínimo 0.93) e **diff médio 3.55/255** (máximo 6.0) — passa.
`outputs/_diff_roundtrip.png` tem o heatmap; a diferença residual se
concentra em bordas/contornos (sensibilidade normal de antialiasing), não em
tom/cor.

**Efeito colateral bom:** a máscara real da camada (extraída por
`psd_reader.extrair_mascara_camada`, alinhada ao bbox — o bbox da máscara
`(55,0,1080,1350)` não bate com o bbox da camada `(172,45,1003,1181)`, é
preciso realinhar) é um **gradiente diagonal**, não um degradê horizontal
simples como a máscara sintética anterior (`_mascara_fusao_lateral`, mantida
só como fallback caso a camada não tenha máscara própria).

### Workstream B — posicionamento por detecção de rosto

`fbs/face.py`: **OpenCV Haar Cascade** (`haarcascade_frontalface_default.xml`,
já vem com `opencv-python`), não mediapipe — mediapipe puxaria upgrade de
numpy 1.26→2.4 com risco real de quebrar psd-tools/scikit-image, e
`opencv-python` já estava instalado no ambiente. O próprio HANDOFF_v4 §2.1
já aceita isso como fallback.

- `calibrar_ancora`: extrai a foto original da camada, detecta o rosto,
  salva `assets/templates/fbs_{formato}.anchor.json` com a posição do rosto
  **relativa ao bbox** (`ancora_x_rel`, `ancora_y_rel`) + altura do rosto em
  px. Simplificação em relação ao HANDOFF_v4 §2.2: como `layer.topil()` já
  retorna a foto no tamanho exato do bbox da camada, a posição relativa NA
  FOTO já é a posição relativa NO BBOX — não precisa converter pra
  coordenadas de canvas.
- `calibrar_se_necessario`: recalibra sozinho se o PSD for mais novo que o
  `.anchor.json` (ou se não existir ainda). `gerar.py` chama isso a cada
  job — idempotente e rápido quando já calibrado.
- `posicionar_por_rosto`: detecta rosto na foto nova, escala pra bater com a
  altura-alvo, recorta mantendo o rosto na mesma posição relativa da âncora,
  sempre cobrindo o bbox inteiro. Sem rosto detectável (na foto nova, ou sem
  âncora calibrada pro template): cai no `fit_cover` + `foco` do job, com
  aviso no log — testado com `fotos/teste2.jpg` e `fotos/teste3.jpg` (uma
  foto artística sem rosto humano de verdade), funcionou sem quebrar.
- `job.json` ganhou `"enquadramento"`: `"auto"` (default, usa detecção de
  rosto) ou `"manual"` (usa `foco` direto, sem detectar nada).
- `calibrar_template.py`: script standalone pra rodar a calibração
  manualmente/inspecionar o resultado (`gerar.py` já chama sozinho, não é
  obrigatório rodar à parte).

**Limitação real encontrada e não resolvida:** a foto de calibração do
template (`foto_artista` no PSD atual — Gonzalo com o rosto tombado, olhos
fechados, cabelo cobrindo a testa, gaita na frente da boca) é um caso difícil
pra qualquer detector frontal simples. O Haar Cascade detecta uma região
consistentemente **errada** nela — pega a testa/cabelo, não olho-nariz-boca
(testado com `haarcascade_frontalface_default.xml` e `_alt2.xml`, várias
`scaleFactor`, mesmo padrão nas duas fotos-fonte disponíveis dessa mesma
pose). A âncora calibrada a partir dessa foto herda esse erro. Pra fotos de
convidados futuros com pose mais convencional (olhando pra câmera, rosto
visível) a detecção tende a ser melhor — mas **recomendo forte conferir
visualmente o enquadramento das primeiras gerações reais** e, se for
sistematicamente ruim, considerar (a) recalibrar com uma foto de referência
mais "de frente", ou (b) migrar pra mediapipe futuramente (aceitando o
upgrade de numpy, testando o resto do pipeline de novo depois).

### Performance (atualizada)

Removida a etapa mais cara do v3 (`compor_overlay_acima` pra foto, ~4-5s) —
agora é só um `psd.composite()` extra pra inserir a foto (nenhum isolamento).
Medido: **~12-13s por feed** (era ~15-16s). Ainda dominado por
`extrair_variaveis` (~5-6s, amostra de cor renderizando `layer.composite()`
isolado de cada texto) e o `psd.composite()` principal (~5s, parece ser mais
lento com camadas ocultas que 100% visível — não investigado a fundo).
Abaixo do alvo do brief (<5s pros 3 formatos), aceito por ora — corretude
teve prioridade, ver histórico de bugs acima.

### Determinismo

`img.save()` embutia um perfil ICC do `psd.composite(apply_icc=True)` com
bytes que variam a cada geração (mesmo com os pixels 100% idênticos —
confirmado comparando array numpy, diff=0). Corrigido removendo
`img.info["icc_profile"]` antes de salvar em `gerar.py`. Testado: hash
SHA-256 do PNG idêntico em 2 execuções seguidas do mesmo job.

## O que falta

- **`fbs_story.psd` e `fbs_sympla.psd` não existem.** Só há o PSD de feed
  (cópia de `PSD TESTE.psd`, ver "Decisões" abaixo). `formatos: ["story"]` ou
  `["sympla"]` falha com erro claro ("template PSD não encontrado"); o código
  já está pronto pra esses formatos, só falta o arquivo — quando chegarem, a
  calibração de âncora de rosto (`face.calibrar_se_necessario`) roda sozinha
  pra eles também, nenhum código novo necessário (só a ressalva de que a
  máscara de `foto_artista` precisa existir na camada de cada PSD, do
  contrário cai no fallback `_mascara_fusao_lateral` sintética).
- **`foto_artista` ainda não foi renomeada no PSD de origem** (`Downloads\PSD
  TESTE.psd`) — a camada real se chama `artista28 copiar`. O código cobre
  isso via `config.MAPA_CAMADAS_LEGADO`; quando o Ricardo renomear pra
  `foto_artista` no Photoshop, **remova a entrada do mapa** (ou deixe — o
  código tenta o nome direto primeiro, então não quebra se ficar redundante).
  As outras 6 camadas variáveis **já estão** com nome exato da convenção do
  brief (renomeadas durante esta sessão, aparentemente ao vivo no Photoshop).
- Checklist de efeitos do brief §1.2 (textura nas letras, vinheta, grain) —
  pelo visual do PSD atual, os itens (a) textura em `txt_artista`, (b) textura
  em `txt_data_mes`/`txt_data_dia` e (e) grain global **parecem já aplicados**
  (confirmado comparando `_debug_original_com_variaveis.png` com a arte de
  referência). Não testado: (c) textura suave em `txt_edicao`/rodapé — o valor
  amostrado de `txt_edicao` (197,193,192, cinza claro) sugere leve textura
  aplicada. (f) máscara de fusão no `foto_artista` original — não verificado;
  não é crítico porque o script já aplica sua própria máscara de fusão na
  foto nova.

## Decisões tomadas sem confirmação do usuário (retomar quando ele voltar)

O usuário não respondeu a uma pergunta de escopo (AskUserQuestion) antes da
implementação. Segui o caminho pragmático — **peço reconfirmação**:

1. **PSD de origem:** não existiam PSDs em `assets/templates/`. Copiei
   `C:\Users\PC\Downloads\PSD TESTE.psd` → `assets/templates/fbs_feed.psd`
   (hash `65339798...9f7`). Esse é o POC citado no brief. Se o Ricardo estiver
   trabalhando num arquivo diferente/mais novo, recopiar.
2. **Mapeamento de nomes (`config.MAPA_CAMADAS_LEGADO`):** em vez de exigir
   nomes exatos, o código resolve `nome_real → slot` com fallback pro nome
   legado. Só há 1 entrada hoje (`foto_artista`). Alternativa descartada:
   travar até o PSD estar 100% na convenção.
3. **Escopo desta rodada: só `feed`.** Story/Sympla ficam implementados mas
   sem template pra testar.

## Riscos técnicos descobertos (não previstos no brief)

1. **`FontSize` do `engine_dict` não reflete o tamanho renderizado** — todas
   as camadas type retornam `FontSize=38.0` independente do tamanho visual
   real (há uma matriz de transform/escala aplicada à camada via Free
   Transform no Photoshop — confirmado inspecionando `layer.transform`, com
   fatores de escala não uniformes, ex. `txt_artista` ~3.55x/4.92x).
   **Mitigação:** o autoshrink em `compositor.py` nunca lê `FontSize`; ele
   parte de um teto generoso derivado da altura do bbox e encolhe até caber
   (`_ajustar_texto_ao_bbox`). Funciona porque o alvo é sempre o bbox, não o
   tamanho "original".
2. **`FillColor.Values` não reflete a cor visível** — `GONZALO ARAYA` e
   `CONVIDA #28` retornam CMYK `[1,1,1,1]` (viraria preto), mas a cor real é
   creme/âmbar com textura. **Mitigação:** `psd_reader._amostrar_cor` renderiza
   o composite isolado da camada (`layer.composite()`, com layer styles/pattern
   overlay aplicados) e tira a média RGB dos pixels opacos. Isso também
   captura a cor *já misturada com a textura*, que é o efeito visual correto.
3. **Bug de z-order na foto:** colar a foto nova direto por cima da base
   composta tapava elementos fixos que no PSD original ficam *acima* da
   camada `foto_artista` na pilha (`ENTRADA GRATUITA`, `COM BEBECO BLUES
   BAND`, e o tratamento de textura/vinheta/grain — quase toda a pilha visual
   fica acima da foto). **[SUPERADO — ver seção "HANDOFF_v4" acima.]** A
   correção original (`psd_reader.compor_overlay_acima`, isolar as camadas
   acima do índice e colar por cima) funcionava pra conteúdo `blend_mode`
   NORMAL, mas se mostrou **incorreta** pro grain/vinheta (blend Overlay/
   Lighten) quando isolados sem o fundo real — foi substituída por
   `compor_com_foto_nova`, que insere a foto como camada de verdade na pilha
   e deixa o psd-tools compor tudo. `compor_overlay_acima` foi removida do
   código (não é mais chamada). Os 6 slots de texto continuam sem essa
   correção (ficam perto do topo da pilha, visualmente ok sem ela).
4. **Todo texto do PSD é alinhado ao topo-esquerda do bbox**, não centralizado
   — confirmado renderizando `psd.composite()` com as variáveis visíveis
   antes de decidir o alinhamento. `desenhar_texto` desenha a partir de
   `(x1, y1)`, sem centralizar.
5. **`\r` como quebra de linha:** `txt_artista.text` no PSD vem como
   `"GONZALO\rARAYA"` — tratado como quebra de linha forçada em
   `_ajustar_texto_ao_bbox` (não é relevante pro texto novo vindo do
   `job.json`, que normalmente não tem quebra manual, mas o código respeita
   se vier).
6. **Bug de autoshrink + corte de texto (encontrado ao testar `ajustes.json`
   manualmente, corrigido nesta sessão):** duas causas empilhadas —
   - `_ajustar_texto_ao_bbox` estimava a altura necessária como
     `fonte.size * 1.15`, mas o glifo real de fontes caixa-alta condensadas
     (Anton) ocupa só ~85% do `size` (sem descendentes de minúscula). Isso
     fazia o autoshrink parar de crescer bem antes de preencher o bbox de
     verdade — todo texto saía uns 25-30% menor do que cabia (`txt_data_dia`
     "14" só chegava a tamanho 86 quando 96+ cabia perfeitamente). Corrigido
     medindo a altura real do glifo via `draw.textbbox` (`_altura_glifo`) em
     vez de estimar a partir do `size` — ver `compositor.FATOR_PITCH`.
   - `draw.text((x,y), ...)` do Pillow não desenha a tinta rente a `y` — há
     um espaço vazio (top bearing) entre `y` e o topo visível do glifo
     (~12-28px dependendo do tamanho). Em caixas altas (`txt_data_dia`,
     100px) isso só deslocava o texto um pouco pra baixo; em `txt_edicao`
     (24px de altura) o espaço vazio era MAIOR que a própria caixa, cortando
     "CONVIDA #28" quase inteiro (só sobrava uma tira fina do topo dos
     glifos). Corrigido compensando esse bearing antes de desenhar
     (`bearing_topo` em `desenhar_texto`).
   Os dois bugs juntos explicam o "não fez nada" ao tentar aumentar
   `tamanho_max` via `ajustes.json` — o teto artificial baixo (~86) e o corte
   de `txt_edicao` mascaravam o efeito de qualquer override. Testado de novo
   depois da correção: `txt_data_dia` cresce corretamente com o `ajustes.json`
   atual, `txt_edicao` não corta mais, e o teste de regressão do nome longo
   (`MARIA APARECIDA DOS SANTOS BLUES TRIO`, 3 linhas) continua ok.

## Desvio do `requirements.txt` do brief

O brief pedia `aggdraw>=1.3.16` avulso. Na prática, `psd.composite()` e
`layer.composite()` **falham com `ImportError`** em qualquer camada com layer
style de Pattern Overlay (a textura das letras, brief §1.2a/b) sem
`scikit-image` instalado — `aggdraw` sozinho não resolve. Troquei para
`psd-tools[composite]`, que já traz `aggdraw`, `scikit-image` e `scipy`
corretos. Reinstalar com `pip install -r requirements.txt` se o ambiente não
tiver essas libs.

## Performance

Números atualizados na seção "HANDOFF_v4 → Performance" acima (~12-13s por
feed agora, era ~15-16s antes da v4 remover o `compor_overlay_acima` da
foto). Ainda abaixo do alvo do brief (<5s pros 3 formatos) — não otimizado
nesta rodada, corretude teve prioridade.

## Limpeza pendente (bloqueada por política de segurança, não por mim)

`fbs/layout_feed.py`, `layout_story.py`, `layout_sympla.py`, `camadas.py`,
`tratamento.py` e `test_tratamento.py` são da abordagem antiga (desenhar tudo
do zero com Pillow) e **não são mais importados por nada** — confirmado via
grep. Uma tentativa de apagá-los foi bloqueada automaticamente por serem
arquivos pré-existentes (ação irreversível sem pedido explícito do usuário).
Ficaram no lugar, inertes. Apagar manualmente quando confirmar que não
precisa mais deles.

## Estrutura de arquivos novos/alterados

```
fbs-gerador/
├── assets/templates/
│   ├── fbs_feed.psd                 [cópia do PSD TESTE — v3]
│   └── fbs_feed.anchor.json         [novo (v4) — âncora de rosto calibrada, gerado automático]
├── fbs/
│   ├── config.py                    [v3 + v4: DEFAULTS ganhou "enquadramento": "auto"]
│   ├── util.py                      [v3 + v4: validar_job valida "enquadramento"]
│   ├── psd_reader.py                 [v3: extrair_variaveis, compor_base, extrair_mascara_camada.
│   │                                  v4: + compor_com_foto_nova (insere camada de verdade,
│   │                                  substitui compor_overlay_acima pra foto — removida)]
│   ├── compositor.py                 [v3: desenhar_texto, textura-no-glifo.
│   │                                  v4: desenhar_foto virou preparar_foto_rgba (mais simples)]
│   ├── ajustes.py                    [v3 — carrega ajustes.json]
│   └── face.py                       [novo (v4) — detectar_rosto, calibrar_ancora,
│                                       calibrar_se_necessario, posicionar_por_rosto]
├── ajustes.json                      [v3 — overrides opcionais por slot]
├── gerar.py                          [v3 + v4: usa compor_com_foto_nova, enquadramento auto/manual]
├── calibrar_template.py              [novo (v4) — script standalone de calibração de âncora]
├── testar_roundtrip.py               [novo (v4) — validação SSIM/diff da fidelidade da foto]
├── jobs/job.json, job_gonzalo.json   [v3 — formatos: ["feed"] só]
└── requirements.txt                  [v3: psd-tools[composite]. v4: + opencv-python, scikit-image]
```

## Como rodar

```bash
pip install -r requirements.txt
python gerar.py                              # usa jobs/job.json
python gerar.py --job jobs/job_gonzalo.json  # outro job

python calibrar_template.py    # (opcional) força/inspeciona calibração de âncora de rosto
python testar_roundtrip.py     # valida fidelidade da foto contra a referência (SSIM/diff)
```
