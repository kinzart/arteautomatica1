"""Desenha texto e foto novos por cima da base composta do PSD."""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

from . import config, util

# espaçamento entre linhas, relativo à altura REAL do glifo (medida via
# textbbox) — não ao "size" da fonte. `size` é o tamanho do em-square interno
# da fonte; pra fontes condensadas em caixa alta como Anton, o glifo visível
# ocupa só ~85% disso (sem descendentes de minúscula). Usar `size` direto
# pra estimar altura fazia o autoshrink parar bem antes de preencher o bbox
# de verdade — texto sempre saía menor do que cabia.
FATOR_PITCH = 1.2

_MEDIDOR = ImageDraw.Draw(Image.new("L", (1, 1)))


def _altura_glifo(texto, fonte):
    """Altura real (px) do texto renderizado nessa fonte — cap-height + o que
    de fato desce abaixo da linha de base, não o em-square inteiro."""
    bbox = _MEDIDOR.textbbox((0, 0), texto, font=fonte)
    return bbox[3] - bbox[1]


def _altura_linha(linhas, fonte):
    """Pitch vertical entre linhas (ou altura de uma linha só), a partir da
    altura real do glifo mais alto entre as `linhas`."""
    return max(_altura_glifo(l, fonte) for l in linhas) * FATOR_PITCH


def _largura_tracked(fonte, texto, tracking):
    extra = (tracking / 1000) * fonte.size
    return sum(fonte.getlength(c) for c in texto) + extra * len(texto)


def _quebrar_linhas_tracked(texto, fonte, tracking, largura_max):
    palavras = texto.split()
    if not palavras:
        return [""]
    linhas = []
    atual = palavras[0]
    for palavra in palavras[1:]:
        teste = f"{atual} {palavra}"
        if _largura_tracked(fonte, teste, tracking) <= largura_max:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def _ajustar_texto_ao_bbox(texto, nome_fonte, largura_max, altura_max, tracking,
                            max_linhas=1, tamanho_min=10, tamanho_max=None, passo=4, log=None):
    """Encontra o maior tamanho de fonte (múltiplo de `passo` abaixo de um teto
    generoso derivado da altura do bbox, ou de `tamanho_max` se informado) que
    faz o texto (com tracking) caber em largura_max x altura_max, em no máximo
    `max_linhas` linhas.

    `tamanho_max`/`tamanho_min` explícitos (via ajustes.json — ver
    fbs/ajustes.py) sobrescrevem o teto/piso automático derivado do bbox —
    útil quando o autoshrink escolhe um tamanho tecnicamente "cabe" mas
    visualmente pequeno demais, ou quando se quer forçar um tamanho exato.

    Quebras explícitas (\\r/\\n) do texto original do PSD são respeitadas como
    limites de linha "duros" — o texto novo do job.json normalmente não tem,
    mas nomes de artista digitados com quebra manual são preservados.
    """
    if tamanho_max is None:
        tamanho_max = max(int(altura_max / 0.7), tamanho_min)

    partes = [p.strip() for p in texto.replace("\r", "\n").split("\n") if p.strip()]
    quebra_forcada = len(partes) > 1
    if not partes:
        partes = [texto]

    tamanho = tamanho_max
    melhor = None
    while tamanho >= tamanho_min:
        fonte = util.carregar_fonte(nome_fonte, tamanho)
        if quebra_forcada:
            linhas = []
            for parte in partes:
                linhas.extend(_quebrar_linhas_tracked(parte, fonte, tracking, largura_max))
        else:
            linhas = _quebrar_linhas_tracked(texto, fonte, tracking, largura_max)

        altura_total = _altura_linha(linhas, fonte) * len(linhas)
        largura_ok = all(_largura_tracked(fonte, l, tracking) <= largura_max for l in linhas)
        melhor = (fonte, linhas, tamanho)

        if len(linhas) <= max_linhas and largura_ok and altura_total <= altura_max:
            return fonte, linhas, tamanho
        tamanho -= passo

    if log:
        log.warning(
            "autoshrink: \"%s\" não coube em %dx%d — usando tamanho mínimo %dpt",
            texto, int(largura_max), int(altura_max), tamanho_min,
        )
    fonte, linhas, tamanho = melhor
    if len(linhas) > max_linhas:
        cabeca, resto = linhas[:max_linhas - 1], linhas[max_linhas - 1:]
        linhas = cabeca + [" ".join(resto)]
    return fonte, linhas, tamanho


def _blend(cor_base, textura_arr, modo):
    """cor_base: (r,g,b) 0-255. textura_arr: array HxW float 0-1 (luminância).
    Retorna array HxWx3 float 0-255 com a cor misturada à textura."""
    base = np.array(cor_base, dtype=np.float32) / 255.0
    if modo == "overlay":
        t = textura_arr[..., None]
        b = base[None, None, :]
        misto = np.where(b < 0.5, 2 * b * t, 1 - 2 * (1 - b) * (1 - t))
    else:  # multiply (default)
        misto = base[None, None, :] * textura_arr[..., None]
    return np.clip(misto * 255.0, 0, 255)


def _textura_para_mascara(textura_path, tamanho):
    textura = Image.open(textura_path).convert("L").resize(tamanho)
    return np.array(textura).astype(np.float32) / 255.0


def desenhar_texto(base, meta, novo_texto, ajuste=None, log=None):
    """Renderiza `novo_texto` no lugar da camada variável descrita em `meta`,
    usando fonte (por slot), cor e tracking herdados do PSD original.

    Alinhamento top-left dentro do bbox — é assim que o texto original do PSD
    está posicionado (paragraph text box do Photoshop). Muda `base` in-place
    e a retorna, pra permitir encadeamento.

    `ajuste` (opcional, de ajustes.json — ver fbs/ajustes.py): overrides pra
    iterar sem tocar no PSD —
      tamanho (int, px): tamanho fixo, sem autoshrink.
      tamanho_max / tamanho_min (int, px): teto/piso do autoshrink.
      tracking (número): espaçamento entre caracteres em milésimos de EM;
        positivo afasta e negativo aproxima.
      espacamento_linhas (número): multiplicador da altura entre linhas.
      offset_x / offset_y (int, px): nudge de posição.
      textura (path): imagem de textura pra misturar dentro do glifo (recria
        o efeito de Pattern Overlay do Photoshop pro texto novo — sem isso, o
        texto usa a cor média sampleada, sólida).
      textura_opacidade (float 0-1, default 0.7) / textura_blend
        ("multiply" [default] | "overlay").
    """
    ajuste = ajuste or {}
    slot = meta["slot"]
    x1, y1, x2, y2 = meta["bbox"]
    largura_max = int(ajuste.get("caixa_largura", x2 - x1))
    altura_max = int(ajuste.get("caixa_altura", y2 - y1))
    nome_fonte = ajuste.get("fonte", config.FONTE_POR_SLOT[slot])
    if nome_fonte not in config.FONTES:
        raise ValueError(f"{slot}.fonte inválida: {nome_fonte}; use {sorted(config.FONTES)}")
    tracking = ajuste.get("tracking", meta.get("tracking", 0))
    cor = ajuste.get("cor", meta.get("cor_rgb", (243, 238, 227)))
    if isinstance(cor, str):
        cor = cor.lstrip("#")
        if len(cor) != 6:
            raise ValueError(f"{slot}.cor deve usar o formato #RRGGBB")
        cor = tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))
    cor = tuple(cor)
    max_linhas = config.MAX_LINHAS_MULTILINHA if slot in config.SLOTS_MULTILINHA else 1

    tamanho_fixo = ajuste.get("tamanho")
    if tamanho_fixo is not None:
        if not isinstance(tamanho_fixo, int) or isinstance(tamanho_fixo, bool) or tamanho_fixo <= 0:
            raise ValueError(f"{slot}.tamanho deve ser um inteiro positivo")
        fonte = util.carregar_fonte(nome_fonte, tamanho_fixo)
        if ajuste.get("quebrar_linhas", False):
            linhas = _quebrar_linhas_tracked(novo_texto, fonte, tracking, largura_max)
        else:
            linhas = novo_texto.replace("\r", "\n").split("\n")
        tamanho = tamanho_fixo
    else:
        fonte, linhas, tamanho = _ajustar_texto_ao_bbox(
            novo_texto, nome_fonte, largura_max, altura_max, tracking,
            max_linhas=max_linhas, log=log,
            tamanho_max=ajuste.get("tamanho_max"),
            tamanho_min=ajuste.get("tamanho_min", 10),
        )

    x = x1 + ajuste.get("offset_x", 0)
    y = y1 + ajuste.get("offset_y", 0)
    espacamento_linhas = ajuste.get("espacamento_linhas", FATOR_PITCH)
    if not isinstance(espacamento_linhas, (int, float)) or isinstance(espacamento_linhas, bool) or espacamento_linhas <= 0:
        raise ValueError(f"{slot}.espacamento_linhas deve ser um número positivo")
    altura_linha = max(_altura_glifo(linha, fonte) for linha in linhas) * espacamento_linhas
    # draw.text((x,y), ...) não desenha a tinta rente a `y` — sobra um espaço
    # vazio (top bearing) entre `y` e o topo visível do glifo. Sem compensar
    # isso, o texto sai deslocado pra baixo do bbox (e em caixas baixas, como
    # txt_edicao, pode até cortar o texto pra fora da máscara). Compensa pela
    # 1ª linha só, mantendo o pitch entre linhas uniforme.
    bearing_topo = _MEDIDOR.textbbox((0, 0), linhas[0], font=fonte)[1]
    alinhamento = ajuste.get("alinhamento", "esquerda")
    opacidade = int(round(255 * ajuste.get("opacidade", 1.0)))

    def x_da_linha(linha):
        largura = _largura_tracked(fonte, linha, tracking)
        if alinhamento == "centro":
            return x + (largura_max - largura) / 2
        if alinhamento == "direita":
            return x + largura_max - largura
        return x

    textura_path = ajuste.get("textura")
    if textura_path:
        # A máscara ocupa o canvas inteiro para permitir tamanho fixo/offset
        # sem recortar o glifo nos limites do bbox original do PSD.
        mascara = Image.new("L", base.size, 0)
        draw_mascara = ImageDraw.Draw(mascara)
        y_local = y - bearing_topo
        for linha in linhas:
            util.draw_text_tracked(draw_mascara, (x_da_linha(linha), y_local), linha, fonte, opacidade, tracking)
            y_local += altura_linha

        escala_x = float(ajuste.get("escala_x", 1.0))
        escala_y = float(ajuste.get("escala_y", 1.0))
        if escala_x <= 0 or escala_y <= 0:
            raise ValueError(f"{slot}.escala_x/escala_y devem ser positivas")
        if (escala_x != 1.0 or escala_y != 1.0) and mascara.getbbox():
            bx1, by1, bx2, by2 = mascara.getbbox()
            trecho = mascara.crop((bx1, by1, bx2, by2))
            trecho = trecho.resize((
                max(1, round(trecho.width * escala_x)),
                max(1, round(trecho.height * escala_y)),
            ), Image.LANCZOS)
            mascara = Image.new("L", base.size, 0)
            mascara.paste(trecho, (bx1, by1))

        desgaste = float(ajuste.get("desgaste", 0))
        if desgaste < 0 or desgaste > 1:
            raise ValueError(f"{slot}.desgaste deve ficar entre 0 e 1")
        if desgaste:
            bordas_path = config.ASSETS + "/textura_bordas.png"
            bordas = np.asarray(Image.open(bordas_path).convert("L").resize(base.size), dtype=np.float32) / 255
            mask_arr = np.asarray(mascara, dtype=np.float32)
            mask_arr *= 1 - desgaste + desgaste * bordas
            mascara = Image.fromarray(np.clip(mask_arr, 0, 255).astype(np.uint8), "L")

        textura_arr = _textura_para_mascara(textura_path, base.size)
        cor_misturada = _blend(cor, textura_arr, ajuste.get("textura_blend", "multiply"))
        textura_opacidade = ajuste.get("textura_opacidade", 0.7)
        cor_final = np.array(cor, dtype=np.float32) * (1 - textura_opacidade) + cor_misturada * textura_opacidade
        rgba = np.dstack([np.clip(cor_final, 0, 255).astype(np.uint8), np.array(mascara)])
        camada = Image.fromarray(rgba, mode="RGBA")
        base.alpha_composite(camada)
    else:
        draw = ImageDraw.Draw(base)
        y_linha = y - bearing_topo
        for linha in linhas:
            fill = (*cor, opacidade) if base.mode == "RGBA" else cor
            util.draw_text_tracked(draw, (x_da_linha(linha), y_linha), linha, fonte, fill, tracking)
            y_linha += altura_linha
    return base


def ajustar_foto(foto, ajuste):
    """Aplica controles manuais à foto já enquadrada, antes da máscara/PSD."""
    ajuste = ajuste or {}
    largura, altura = foto.size
    zoom = float(ajuste.get("zoom", 1.0))
    if zoom <= 0:
        raise ValueError("foto_artista.zoom deve ser positivo")
    if zoom != 1.0:
        nw, nh = max(1, round(largura * zoom)), max(1, round(altura * zoom))
        redim = foto.resize((nw, nh), Image.LANCZOS)
        cx = (nw - largura) / 2 - float(ajuste.get("offset_x", 0))
        cy = (nh - altura) / 2 - float(ajuste.get("offset_y", 0))
        # zoom >= 1 sempre cobre o viewport; recorta diretamente, sem criar
        # canvas preto intermediário.
        left, top = round(cx), round(cy)
        left = min(max(left, 0), nw - largura)
        top = min(max(top, 0), nh - altura)
        foto = redim.crop((left, top, left + largura, top + altura))
    # Sem zoom não há margem para deslocar sem expor borda; mantenha o cover
    # intacto. Para pan manual, use zoom > 1.

    foto = ImageEnhance.Brightness(foto).enhance(float(ajuste.get("brilho", 1.0)))
    foto = ImageEnhance.Contrast(foto).enhance(float(ajuste.get("contraste", 1.0)))
    foto = ImageEnhance.Color(foto).enhance(float(ajuste.get("saturacao", 1.0)))
    foto = ImageEnhance.Sharpness(foto).enhance(float(ajuste.get("nitidez", 1.0)))
    temperatura = float(ajuste.get("temperatura", 0))
    if temperatura:
        arr = np.asarray(foto).astype(np.float32)
        arr[..., 0] *= 1 + temperatura / 100
        arr[..., 2] *= 1 - temperatura / 100
        foto = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    return foto


def _mascara_fusao_lateral(largura, altura, lado="esquerda", frac=0.15):
    """Gradiente alpha 0 (borda externa) -> 255, ocupando `frac` da largura no
    lado indicado — pra foto "emergir" do preto onde encosta no texto
    (BRIEF_v3 §2.6). Fallback só usado quando a camada `foto_artista` não
    tem máscara própria no PSD — o normal é usar a máscara real, extraída
    por `psd_reader.extrair_mascara_camada`, que reproduz exatamente o
    gradiente (diagonal, não um degradê linear simples) desenhado no
    Photoshop."""
    faixa = max(1, int(largura * frac))
    alpha = np.full((altura, largura), 255, dtype=np.uint8)
    rampa = np.linspace(0, 255, faixa, dtype=np.uint8)
    if lado == "esquerda":
        alpha[:, :faixa] = rampa[np.newaxis, :]
    elif lado == "direita":
        alpha[:, -faixa:] = rampa[::-1][np.newaxis, :]
    elif lado == "topo":
        alpha[:faixa, :] = rampa[:, np.newaxis]
    return Image.fromarray(alpha, mode="L")


def preparar_foto_rgba(foto_path, largura, altura, foco="topo", mascara=None,
                        fusao_lado="esquerda", fusao_frac=0.15, foto_posicionada=None):
    """Carrega a foto, posiciona no tamanho do bbox de `foto_artista`, e
    devolve RGBA com a máscara de fusão já embutida como canal alpha —
    pronta pra virar uma camada de pixel de verdade via
    `psd_reader.compor_com_foto_nova` (que deixa o psd-tools recompor tudo
    com blend modes/adjustment layers corretos — ver docstring de lá pro
    porquê disso importa).

    `mascara` (opcional): PIL "L" do tamanho do bbox — normalmente a máscara
    real extraída da camada original. Sem ela, cai na sintética
    (`_mascara_fusao_lateral`).

    `foto_posicionada` (opcional): imagem já do tamanho certo (largura x
    altura), pronta pra usar — ex. resultado de `face.posicionar_por_rosto`
    (HANDOFF_v4 §2). Sem ela, faz `fit_cover` simples com `foco`.
    """
    if foto_posicionada is not None:
        foto = foto_posicionada
    else:
        foto = Image.open(foto_path).convert("RGB")
        foto = util.fit_cover(foto, largura, altura, foco=foco)

    if mascara is None:
        mascara = _mascara_fusao_lateral(largura, altura, lado=fusao_lado, frac=fusao_frac)
    rgba = foto.convert("RGBA")
    rgba.putalpha(mascara)
    return rgba
