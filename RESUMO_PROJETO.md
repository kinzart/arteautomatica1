# Resumo técnico — Gerador FBS

## Objetivo e estado atual

Aplicação local em Python para gerar cartazes feed 1080×1350. O PSD ainda é a
fonte dos elementos visuais fixos, máscaras e ordem de composição. Foto e
tipografia variável são substituídas pelo pipeline. O painel `painel.py` edita
os quatro inputs principais (`artista`, `foto`, `data`, `edicao`) preservando
os demais dados do job e mostra uma prévia.

Comando principal: `python gerar.py --job jobs/job.json`. Painel Windows:
`abrir_painel.bat`. Configuração visual: `ajustes.json`.

## Arquitetura e fluxo

1. `painel.py` valida os inputs, atualiza `jobs/job.json` e chama `gerar.py`.
2. `fbs/util.py` valida o job, resolve caminhos, data em português e fontes.
3. `fbs/psd_reader.py` abre o PSD, reconhece slots e extrai bbox, cor, tracking
   e máscara da foto. Camadas de foto cujo nome começa com `artista` são aceitas.
4. `fbs/face.py` usa OpenCV Haar Cascade e a âncora
   `assets/templates/fbs_feed.anchor.json` para o enquadramento automático.
5. `fbs/compositor.py` enquadra/trata a foto, ajusta sua máscara e renderiza os
   textos com Pillow, textura, tracking, escala e autoshrink.
6. `psd_reader.compor_com_foto_nova` insere a foto como PixelLayer temporária
   na pilha para preservar adjustment layers e blend modes do PSD.
7. `gerar.py` redesenha textos/rodapé, aplica textura global e salva o PNG sem
   perfil ICC variável, mantendo determinismo.

## Entradas e controles importantes

`jobs/job.json` contém artista, foto, data ISO, edição, hora, local, banda e
formatos. O nome do artista é sempre convertido para caixa alta na saída.

`ajustes.json` contém overrides por formato/slot. A referência completa está em
`AJUSTES.md`. Destaques:

- texto: fonte, tamanho, autoshrink, tracking, offsets, caixa, alinhamento,
  escala X/Y, textura, desgaste, cor e opacidade;
- artista: `layout_artista_auto` (padrão ligado) cria no máximo duas linhas,
  equilibra nomes compostos e mantém pitch independente de acentos;
- foto: zoom, pan, brilho, contraste, saturação, nitidez e temperatura;
- máscara: offset, escala, blur, contraste, opacidade e inversão;
- data: mês/dia/semana/hora compartilham o eixo de `ENTRADA GRATUITA`, reduzem
  ao atingir o limite e expandem tracking quando curtos;
- rodapé: nome, bairro, endereço e duas linhas já são renderizados pelo pipeline.

## Regra de composição do artista

- duas palavras: uma por linha;
- três palavras: escolhe `A / B C` ou `A B / C` conforme equilíbrio das partes;
- quatro ou mais: testa todos os pontos de corte e minimiza a maior linha;
- nomes com acento usam cap-height estável, evitando que É/Ã aumentem o pitch;
- o tamanho configurado funciona como teto no modo automático e diminui para
  caber na caixa; cada linha pode diminuir independentemente, preservando a
  maior tipografia possível na linha curta; a saída é sempre maiúscula.

Casos cobertos por `test_layout_artista.py`: `GREEN TÉA`,
`BEBECO BLUES BAND`, `ANA CLARA NASCIMENTO` e nomes longos.

## Limitações e próximos passos

- Somente `feed` possui PSD real; story/sympla continuam sem template validado.
- `FLORIPA`, `ENTRADA GRATUITA`, chamada da banda, logo e efeitos globais ainda
  vêm do PSD. Não remover o PSD sem exportar os ativos e criar testes golden.
- Para eliminar o PSD com fidelidade: congelar PNGs de referência, exportar
  máscara/overlays/logo, reproduzir blend modes e ajustes em Python, e exigir
  SSIM global ≥0,95 e diferença média ≤5/255 antes da troca.
- O arquivo PSD excede 100 MB e deve permanecer sob Git LFS no GitHub.

## Validação recomendada

Executar `python -m unittest -v test_layout_artista.py`, gerar ao menos um nome
com acento, um nome de três partes e um nome longo, e inspecionar foto, data,
rodapé e sobreposição com a chamada `COM:`. Não sobrescrever ajustes manuais sem
comparação visual.
