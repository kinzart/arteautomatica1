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
2. Selecione o slot visual.
3. Altere sliders/campos ou arraste o elemento no preview.
4. Clique em **Renderizar preview** ou ligue **Auto preview**.
5. Compare nos modos Gerado, Referência, Lado a lado, Overlay ou Diff.
6. Continue iterando: somente `ajustes.editor.tmp.json` será alterado.
7. Quando estiver satisfeito, clique em **Salvar em ajustes.json**.

Antes da substituição final, o editor cria automaticamente:

```text
backups/ajustes_YYYY-MM-DD_HHMMSS.json
```

## Preview e comparação

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
O render real ocorre ao soltar o mouse.

O eixo X de mês, dia, semana e hora permanece bloqueado porque esses elementos
são centralizados automaticamente em `ENTRADA GRATUITA`. O drag ainda permite
ajuste vertical desses slots.

## Arquivos e segurança

- `ajustes.json`: configuração aprovada e usada na geração final.
- `ajustes.editor.tmp.json`: experimentos do editor.
- `backups/`: cópias automáticas anteriores a cada salvamento final.
- **Restaurar do ajustes.json:** descarta o temporário atual após confirmação.
- **Criar backup agora:** copia o arquivo principal sem alterá-lo.
- **Gerar imagem final:** usa `ajustes.json`, não o temporário.

As alterações de um slot usam merge: campos não exibidos ou não modificados
são preservados.

## Linha de comando

Geração normal:

```powershell
python gerar.py --job jobs/job_gonzalo.json
```

Geração experimental:

```powershell
python gerar.py --job jobs/job_gonzalo.json --ajustes ajustes.editor.tmp.json
```

Comparação automatizada e diff:

```powershell
python comparar_goldmaster.py outputs/fbs27_feed.png
```
