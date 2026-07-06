# Editor visual FBS

## Objetivo

O editor acelera a calibração do cartaz contra a referência oficial
`assets/referencias/fbs_goldmaster.png`. O PSD continua sendo usado como
estrutura técnica, mas o gold master é a autoridade visual.

O editor nunca sobrescreve `ajustes.json` automaticamente. Experimentos são
gravados em `ajustes.editor.tmp.json`, ignorado pelo Git.

## Como abrir

No Windows, dê duplo clique em `abrir_editor_visual.bat` ou execute:

```powershell
python editor_visual.py
```

O painel original continua disponível em `abrir_painel.bat`.

## Fluxo recomendado

1. Escolha um job, normalmente `jobs/job_gonzalo.json` para calibração.
2. Use **Trocar foto…** quando quiser substituir a imagem do artista.
3. Selecione o slot visual.
4. Mantenha **Manual — recomendado** para ajuste fino.
5. Altere sliders/campos ou arraste o elemento; a guia responde imediatamente.
6. Quando necessário, clique em **Renderizar PSD** para validar no PSD.
7. Compare nos modos Gerado, Referência, Lado a lado, Overlay ou Diff.
8. Continue iterando: somente os arquivos temporários serão alterados.
9. Quando estiver satisfeito, salve ajustes e dados do job explicitamente.

Antes da substituição final, o editor cria automaticamente:

```text
backups/ajustes_YYYY-MM-DD_HHMMSS.json
```

## Preview e comparação

O editor tem três níveis independentes:

- **Guia instantânea:** move a bounding box verde sobre o PNG em memória. Não
  abre arquivo nem inicia processo.
- **Preview rápido sem PSD:** chama `render_fast.py`, usa `cache_preview/` e
  aproxima foto, textos, crop, máscara, cores e rodapé em cerca de 0,6 s.
- **Render PSD fiel:** salva o temporário e chama `gerar.py --ajustes ...` em uma
  thread. Somente após terminar o cache do PNG e as métricas são atualizados.

Políticas disponíveis:

- **Manual — recomendado (padrão):** guia instantânea durante o movimento e
  preview rápido com debounce de 300 ms/ao soltar. Nunca chama o PSD sozinho.
- **Ao soltar — lento:** render PSD uma vez ao soltar drag/slider.
- **Automático leve — muito lento:** render PSD com debounce de 1500 ms e no
  máximo um processo simultâneo.

Se houver mudanças durante uma renderização, o resultado antigo é ignorado. Um
novo render só é enfileirado quando a política escolhida solicitar.

- **Gerado:** resultado do job com o arquivo temporário.
- **Referência:** gold master oficial.
- **Lado a lado:** ambas redimensionadas para comparação visual.
- **Overlay:** mistura ajustável das duas imagens.
- **Diff:** diferença absoluta amplificada.

Diferença média e SSIM são auxiliares. Como o gold master contém elementos
fixos que o gerado atual ainda não reproduz, a decisão visual tem prioridade.

## Drag

Arraste no preview com um slot selecionado para alterar `offset_x` e
`offset_y`. O deslocamento da tela é convertido para o canvas real 1080×1350.
Durante o movimento apenas a guia é redesenhada. No modo Manual, soltar chama
somente o preview rápido. Nos modos Ao soltar/Automático leve ocorre um render
PSD conforme a política selecionada.

O eixo X de mês, dia, semana e hora permanece bloqueado porque esses elementos
são centralizados automaticamente em `ENTRADA GRATUITA`. O drag ainda permite
ajuste vertical desses slots.

## Desfazer, refazer e voltar ao PSD

- **Ctrl+Z** ou o botão **Desfazer** volta uma alteração.
- **Ctrl+Shift+Z** ou o botão **Refazer** avança novamente. **Ctrl+Y** também é
  aceito.
- O histórico guarda até 100 estados desta sessão e inclui, no mesmo estado,
  os ajustes visuais e os textos do job temporário.
- Uma edição ainda não renderizada também entra no histórico ao desfazer.
- Fazer uma nova alteração depois de desfazer elimina a sequência antiga de
  refazer, como em editores gráficos.

**Voltar ao PSD original…** pede confirmação e remove todos os overrides
visuais temporários do `feed`. Assim, o próximo render herda posições, medidas
e estilo-base do PSD. A ação não altera `ajustes.json`, não altera o job
original, preserva os textos temporários e pode ser desfeita com **Ctrl+Z**.

Isso é diferente de **Restaurar do ajustes.json**, que retorna à configuração
aprovada atualmente no projeto, e não ao estado sem overrides do PSD.

## Arquivos e segurança

- `ajustes.json`: configuração aprovada e usada na geração final.
- `ajustes.editor.tmp.json`: experimentos do editor.
- `backups/`: cópias automáticas anteriores a cada salvamento final.
- **Restaurar do ajustes.json:** descarta o temporário atual após confirmação.
- **Voltar ao PSD original:** limpa somente os overrides temporários do feed.
- **Criar backup agora:** copia o arquivo principal sem alterá-lo.
- **Gerar imagem final:** usa `ajustes.json`, não o temporário.
- `jobs/job.editor.tmp.json`: conteúdo textual experimental.
- **Salvar dados/foto no job:** cria backup e promove textos e caminho da foto
  temporários para o job selecionado.

As alterações de um slot usam merge: campos não exibidos ou não modificados
são preservados.

## Edição de conteúdo e controles

Slots de artista, edição, data, hora e rodapé mostram um campo de conteúdo no
topo do painel. A saída do artista continua sendo convertida para caixa alta.

A foto pode ser escolhida pelo botão permanente **Trocar foto…** ou dentro do
slot `foto_artista`. A escolha atualiza `jobs/job.editor.tmp.json`, entra no
histórico de desfazer/refazer e dispara somente o preview permitido pela
política selecionada. O arquivo da imagem não é duplicado: o job guarda seu
caminho relativo ao projeto sempre que possível.

No slot `foto_artista`, **espelhar_horizontal** troca esquerda e direita da
imagem. `offset_x` e `offset_y` agora fazem somente pan: nunca modificam o zoom.
Ao atingir a margem disponível, o movimento para; aumente o controle `zoom`
para liberar mais deslocamento. Isso impede o antigo efeito de ampliar ou
reduzir a foto enquanto ela era arrastada.

O painel antigo `painel.py` continua disponível por compatibilidade, mas deixa
de ser necessário no fluxo normal porque os dados principais e a foto podem ser
alterados diretamente no editor visual.

Campos numéricos são quantizados: offsets, tamanhos, tracking e dimensões usam
pixels inteiros; escalas e opacidades mostram somente as casas previstas pelo
controle. Valores digitados aceitam ponto ou vírgula, mas o JSON usa ponto.

Campos de cor aceitam `#RRGGBB` ou a forma curta `#RGB`, normalizada
automaticamente, e possuem botão **Escolher…**. Um valor parcial não dispara
render; confirme com Enter ou saia do campo.

`opacidade` controla o elemento inteiro. `textura_opacidade` controla apenas a
mistura da textura dentro do texto, e `mascara_opacidade` controla a máscara da
foto. Grain e bordas globais são fiéis no **Renderizar PSD**; o preview rápido
reutiliza a base cacheada e, portanto, apenas os aproxima.

## Linha de comando

Geração normal:

```powershell
python gerar.py --job jobs/job_gonzalo.json
```

Geração experimental:

```powershell
python gerar.py --job jobs/job_gonzalo.json --ajustes ajustes.editor.tmp.json
```

Preview rápido sem PSD:

```powershell
python render_fast.py --job jobs/job_gonzalo.json --ajustes ajustes.editor.tmp.json --out outputs/_fast_preview.png
```

Se o cache não existir ou o PSD for atualizado:

```powershell
python preparar_cache_preview.py
```

Comparação automatizada e diff:

```powershell
python comparar_goldmaster.py outputs/fbs27_feed.png
```

Photopea não foi integrado nesta etapa: navegador/iframe/API externa criariam
dependências e latência desnecessárias para o fluxo local.
