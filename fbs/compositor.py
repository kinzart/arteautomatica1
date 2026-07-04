"""Desenha texto e foto novos por cima da base composta do PSD."""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

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
    # O pitch não pode depender dos caracteres de cada linha: Á/É/Ã possuem
    # tinta acima da cap-height e antes faziam a distância entre linhas variar.
    return _altura_glifo("H", fonte) * FATOR_PITCH


def _quebrar_artista_duas_linhas(texto):
    """Divide nomes de artista em no máximo duas linhas visualmente equilibradas."""
    texto = " ".join(texto.upper().split())
    palavras = texto.split()
    if len(palavras) == 1:
        # Caso comum como GREENTÉA: preserva palavras normais, mas permite
        # separar um sufixo iniciado por letra acentuada.
        acentuadas = "ÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ"
        indice_acento = next((i for i, c in enumerate(texto) if c in acentuadas and i >= 3), None)
        corte = max(3, indice_acento - 1) if indice_acento is not None else None
        return [texto[:corte], texto[corte:]] if corte else [texto]
    if len(palavras) == 2:
        return palavras
    if len(palavras) == 3:
        # BEBECO BLUES BAND -> BEBECO / BLUES BAND. Se a primeira palavra é
        # menor que a terceira, favorece duas palavras em cima e uma embaixo.
        if len(palavras[0]) < len(palavras[2]):
            return [" ".join(palavras[:2]), palavras[2]]
        return [palavras[0], " ".join(palavras[1:])]

    melhor = None
    for i in range(1, len(palavras)):
        a, b = " ".join(palavras[:i]), " ".join(palavras[i:])
        score = (max(len(a), len(b)), abs(len(a) - len(b)))
        if melhor is None or score < melhor[0]:
            melhor = (score, [a, b])
    return melhor[1]


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
    layout_artista_auto = slot == "txt_artista" and ajuste.get("layout_artista_auto", True)
    if layout_artista_auto:
        novo_texto = "\n".join(_quebrar_artista_duas_linhas(novo_texto))
    x1, y1, x2, y2 = meta["bbox"]
    x1 = int(ajuste.get("caixa_x", x1))
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
    max_linhas = 2 if layout_artista_auto else (config.MAX_LINHAS_MULTILINHA if slot in config.SLOTS_MULTILINHA else 1)

    tamanho_fixo = None if layout_artista_auto else ajuste.get("tamanho")
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
            tamanho_max=ajuste.get("tamanho", ajuste.get("tamanho_max")) if layout_artista_auto else ajuste.get("tamanho_max"),
            tamanho_min=ajuste.get("tamanho_min", 10),
        )

    # Caixa responsiva: reduz a fonte se ultrapassar o limite e, quando sobra
    # espaço, distribui tracking para manter textos curtos visualmente alinhados.
    if ajuste.get("ajustar_tracking") and len(linhas) == 1 and linhas[0]:
        escala_x_layout = float(ajuste.get("escala_x", 1.0))
        limite = largura_max * float(ajuste.get("preenchimento_largura", 0.92))
        largura = _largura_tracked(fonte, linhas[0], tracking) * escala_x_layout
        if largura > limite:
            tamanho = max(1, int(tamanho * limite / largura))
            fonte = util.carregar_fonte(nome_fonte, tamanho)
        texto = linhas[0]
        largura_glifos = sum(fonte.getlength(c) for c in texto)
        alvo_sem_escala = limite / escala_x_layout
        if len(texto) > 1:
            tracking = ((alvo_sem_escala - largura_glifos) / (len(texto) - 1)) * 1000 / fonte.size

    x = x1 + ajuste.get("offset_x", 0)
    y = y1 + ajuste.get("offset_y", 0)
    espacamento_linhas = ajuste.get("espacamento_linhas", FATOR_PITCH)
    if not isinstance(espacamento_linhas, (int, float)) or isinstance(espacamento_linhas, bool) or espacamento_linhas <= 0:
        raise ValueError(f"{slot}.espacamento_linhas deve ser um número positivo")
    altura_linha = max(_altura_glifo(linha, fonte) for linha in linhas) * espacamento_linhas
    if ajuste.get("textura") and len(linhas) > 1:
        # escala_y deve alongar os glifos, não multiplicar o vazio entre linhas.
        altura_linha /= float(ajuste.get("escala_y", 1.0))
    # draw.text((x,y), ...) não desenha a tinta rente a `y` — sobra um espaço
    # vazio (top bearing) entre `y` e o topo visível do glifo. Sem compensar
    # isso, o texto sai deslocado pra baixo do bbox (e em caixas baixas, como
    # txt_edicao, pode até cortar o texto pra fora da máscara). Compensa pela
    # 1ª linha só, mantendo o pitch entre linhas uniforme.
    bearing_topo = _MEDIDOR.textbbox((0, 0), linhas[0], font=fonte)[1]
    alinhamento = ajuste.get("alinhamento", "esquerda")
    opacidade = int(round(255 * ajuste.get("opacidade", 1.0)))

    def x_da_linha(linha):
        largura = _largura_tracked(fonte, linha, tracking) * float(ajuste.get("escala_x", 1.0))
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
        escala_x = float(ajuste.get("escala_x", 1.0))
        escala_y = float(ajuste.get("escala_y", 1.0))
        if escala_x <= 0 or escala_y <= 0:
            raise ValueError(f"{slot}.escala_x/escala_y devem ser positivas")
        if len(linhas) > 1:
            # Escala cada glifo/linha isoladamente. Assim escala_y não amplia
            # o vazio entre linhas nem separa visualmente os acentos.
            fontes_linhas = []
            for linha in linhas:
                fonte_linha = fonte
                if layout_artista_auto:
                    tamanho_linha = int(ajuste.get("tamanho", fonte.size))
                    fonte_linha = util.carregar_fonte(nome_fonte, tamanho_linha)
                    while (tamanho_linha > ajuste.get("tamanho_min", 10)
                           and _largura_tracked(fonte_linha, linha, tracking) * escala_x > largura_max):
                        tamanho_linha -= 1
                        fonte_linha = util.carregar_fonte(nome_fonte, tamanho_linha)
                fontes_linhas.append(fonte_linha)

            topo_atual = float(y)
            fundo_linha_anterior = None
            gap_linhas_min = float(ajuste.get("gap_linhas_min", 6))
            for indice, linha in enumerate(linhas):
                fonte_linha = fontes_linhas[indice]
                temp = Image.new("L", (max(base.width * 2, largura_max * 3), fonte_linha.size * 3), 0)
                td = ImageDraw.Draw(temp)
                bearing = _MEDIDOR.textbbox((0, 0), linha, font=fonte_linha)[1]
                util.draw_text_tracked(td, (10, 10 - bearing), linha, fonte_linha, opacidade, tracking)
                bbox_tinta = temp.getbbox()
                if not bbox_tinta:
                    continue
                glifo = temp.crop(bbox_tinta).resize((
                    max(1, round((bbox_tinta[2] - bbox_tinta[0]) * escala_x)),
                    max(1, round((bbox_tinta[3] - bbox_tinta[1]) * escala_y)),
                ), Image.LANCZOS)
                if alinhamento == "centro":
                    linha_x = round(x + (largura_max - glifo.width) / 2)
                elif alinhamento == "direita":
                    linha_x = round(x + largura_max - glifo.width)
                else:
                    linha_x = round(x)
                bbox_linha = _MEDIDOR.textbbox((0, 0), linha, font=fonte_linha)
                bbox_cap = _MEDIDOR.textbbox((0, 0), "H", font=fonte_linha)
                # Alinha pela cap-height, não pelo topo do acento. Assim É/Ã
                # não empurram a linha visualmente para baixo.
                offset_acento = max(0, (bbox_cap[1] - bbox_linha[1]) * escala_y)
                linha_y = topo_atual - offset_acento
                if fundo_linha_anterior is not None:
                    linha_y = max(linha_y, fundo_linha_anterior + gap_linhas_min)
                linha_y = round(linha_y)
                mascara.paste(glifo, (linha_x, linha_y))
                fundo_linha_anterior = linha_y + glifo.height
                topo_atual += _altura_glifo("H", fonte_linha) * escala_y * espacamento_linhas
        else:
            draw_mascara = ImageDraw.Draw(mascara)
            linha = linhas[0]
            bearing_linha = _MEDIDOR.textbbox((0, 0), linha, font=fonte)[1]
            util.draw_text_tracked(draw_mascara, (x_da_linha(linha), y - bearing_linha), linha, fonte, opacidade, tracking)
            if (escala_x != 1.0 or escala_y != 1.0) and mascara.getbbox():
                bx1, by1, bx2, by2 = mascara.getbbox()
                trecho = mascara.crop((bx1, by1, bx2, by2)).resize((
                    max(1, round((bx2 - bx1) * escala_x)),
                    max(1, round((by2 - by1) * escala_y)),
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
        topo_linha = y
        for linha in linhas:
            fill = (*cor, opacidade) if base.mode == "RGBA" else cor
            bearing_linha = _MEDIDOR.textbbox((0, 0), linha, font=fonte)[1]
            util.draw_text_tracked(draw, (x_da_linha(linha), topo_linha - bearing_linha), linha, fonte, fill, tracking)
            topo_linha += altura_linha
    return base


def ajustar_foto(foto, ajuste):
    """Aplica controles manuais à foto já enquadrada, antes da máscara/PSD."""
    ajuste = ajuste or {}
    largura, altura = foto.size
    zoom = float(ajuste.get("zoom", 1.0))
    offset_x = float(ajuste.get("offset_x", 0))
    offset_y = float(ajuste.get("offset_y", 0))
    if zoom <= 0:
        raise ValueError("foto_artista.zoom deve ser positivo")
    if zoom > 5:
        raise ValueError(
            "foto_artista.zoom está alto demais. Use 1.0 para tamanho normal, "
            "1.6 para 60% de ampliação e no máximo 5.0"
        )
    # Garante margem suficiente para que todo offset solicitado tenha efeito,
    # sem revelar bordas. Antes, offsets maiores que a margem do zoom eram
    # silenciosamente limitados pelo crop.
    zoom = max(
        zoom,
        1.0 + 2.0 * abs(offset_x) / largura,
        1.0 + 2.0 * abs(offset_y) / altura,
    )
    if zoom != 1.0:
        nw, nh = max(1, round(largura * zoom)), max(1, round(altura * zoom))
        redim = foto.resize((nw, nh), Image.LANCZOS)
        cx = (nw - largura) / 2 - offset_x
        cy = (nh - altura) / 2 - offset_y
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


def ajustar_mascara_foto(mascara, ajuste):
    """Aplica controles não destrutivos à máscara real extraída do PSD."""
    if mascara is None:
        return None
    ajuste = ajuste or {}
    w, h = mascara.size
    escala = float(ajuste.get("mascara_escala", 1.0))
    if escala <= 0 or escala > 5:
        raise ValueError("foto_artista.mascara_escala deve ficar entre 0 e 5")
    ox = int(ajuste.get("mascara_offset_x", 0))
    oy = int(ajuste.get("mascara_offset_y", 0))
    if escala != 1 or ox or oy:
        nw, nh = max(1, round(w * escala)), max(1, round(h * escala))
        redim = mascara.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("L", (w, h), 0)
        canvas.paste(redim, ((w - nw) // 2 + ox, (h - nh) // 2 + oy))
        mascara = canvas
    blur = float(ajuste.get("mascara_blur", 0))
    if blur < 0:
        raise ValueError("foto_artista.mascara_blur não pode ser negativo")
    if blur:
        mascara = mascara.filter(ImageFilter.GaussianBlur(blur))
    mascara = ImageEnhance.Contrast(mascara).enhance(float(ajuste.get("mascara_contraste", 1)))
    if ajuste.get("mascara_inverter", False):
        mascara = ImageOps.invert(mascara)
    opacidade = float(ajuste.get("mascara_opacidade", 1))
    if not 0 <= opacidade <= 1:
        raise ValueError("foto_artista.mascara_opacidade deve ficar entre 0 e 1")
    if opacidade != 1:
        mascara = mascara.point(lambda p: round(p * opacidade))
    return mascara


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
