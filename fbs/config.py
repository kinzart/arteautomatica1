"""Paleta, fontes e dimensões — Design System Blues Session Manual v3, Família B."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
FONTS_DIR = os.path.join(ASSETS, "fonts")
TEMPLATES_DIR = os.path.join(ASSETS, "templates")
OUTPUTS_DIR = os.path.join(ROOT, "outputs")
LOGS_DIR = os.path.join(ROOT, "logs")
LOG_FILE = os.path.join(LOGS_DIR, "fbs.log")

# Um PSD por formato (BRIEF_v3 §1). Enquanto o Ricardo não entrega story/sympla,
# só "feed" existe — os outros geram erro claro em vez de travar o job inteiro.
TEMPLATE_FILES = {
    "feed": os.path.join(TEMPLATES_DIR, "fbs_feed.psd"),
    "story": os.path.join(TEMPLATES_DIR, "fbs_story.psd"),
    "sympla": os.path.join(TEMPLATES_DIR, "fbs_sympla.psd"),
}

# Slots variáveis (BRIEF_v3 §1.1) que o código toca dentro do PSD.
CAMADAS_VARIAVEIS = {
    "foto_artista",
    "txt_artista", "txt_edicao",
    "txt_data_mes", "txt_data_dia", "txt_data_semana", "txt_data_hora",
}

# Nome real da camada no PSD -> slot esperado. Cobre o período de transição
# em que o Ricardo ainda está renomeando camadas no Photoshop pra convenção
# do brief. Camadas já com o nome certo não precisam de entrada aqui (a busca
# em psd_reader tenta o nome direto primeiro, depois este mapa).
MAPA_CAMADAS_LEGADO = {
    "artista28 copiar": "foto_artista",
}

PALETA = {
    "INK": "#0B0907",
    "INK_ALT": "#15110D",
    "CREAM": "#F3EEE3",
    "BS_RED": "#FF0000",
    "BS_AMBER": "#F5A524",
    "PALCO": "#2A2018",
    "WARM_GRAY": "#756B5D",
    "OXBLOOD": "#4E0000",
}

FONTES = {
    "anton": os.path.join(FONTS_DIR, "Anton-Regular.ttf"),
    "archivo": os.path.join(FONTS_DIR, "Archivo-Regular.ttf"),
    "archivo_black": os.path.join(FONTS_DIR, "Archivo-Black.ttf"),
    "mono": os.path.join(FONTS_DIR, "SpaceMono-Regular.ttf"),
}

# Texturas e logo agora vivem dentro do PSD (BRIEF_v3 §2.1) — o código só
# precisa das fontes pra renderizar os 6 textos variáveis.
ASSET_FILES = [
    FONTES["anton"],
    FONTES["archivo"],
    FONTES["archivo_black"],
    FONTES["mono"],
]

DIMENSOES = {
    "feed": (1080, 1350),
    "story": (1080, 1920),
    "sympla": (1920, 1080),
}

# Lado da foto que encosta no texto -> onde aplicar o gradiente de fusão (BRIEF_v3 §2.6).
FUSAO_LADO_POR_FORMATO = {
    "feed": "esquerda",
    "story": "topo",
    "sympla": "esquerda",
}

DEFAULTS = {
    "foco": "topo",
    "enquadramento": "auto",
    "local_nome": "TIO GETHER'S",
    "local_bairro": "MORRO DAS PEDRAS",
    "local_frequencia": "TODA TERÇA",
    "local_cidade": "FLORIANÓPOLIS - SC",
    "local_endereco": "R. MANOEL PEDRO VIEIRA, 1255 — FLORIANÓPOLIS — SC",
    "tagline": "CONEXÕES MUSICAIS E CULTURAIS",
    "banda_ancora": "BEBECO BLUES BAND",
    "formatos": ["feed", "story", "sympla"],
}

CAMPOS_OBRIGATORIOS = ["edicao", "artista", "data", "hora", "foto"]

# Fonte por slot de texto variável (BRIEF_v3 §1.4).
FONTE_POR_SLOT = {
    "txt_artista": "anton",
    "txt_data_mes": "anton",
    "txt_data_dia": "anton",
    "txt_edicao": "mono",
    "txt_data_semana": "mono",
    "txt_data_hora": "mono",
    "txt_local_nome": "anton",
    "txt_local_bairro": "anton",
    "txt_local_endereco": "mono",
}

# Slots que aceitam texto em múltiplas linhas + autoshrink (só o nome do artista
# pode ser longo o bastante pra precisar disso — os outros são curtos e fixos).
SLOTS_MULTILINHA = {"txt_artista"}
MAX_LINHAS_MULTILINHA = 3

# Exceção documentada à regra "vermelho só na logo" (Manual v3, seção 3.4):
# as iniciais da banda âncora na linha "com: Nome Da Banda" também usam BS_RED,
# por decisão de refinamento visual (HANDOFF v2, Ajuste 3) — destaque tipográfico
# equivalente ao peso da logo, não uma nova cor livre no restante da peça.
