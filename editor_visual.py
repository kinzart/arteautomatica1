#!/usr/bin/env python
"""Editor visual seguro para calibrar ajustes contra o gold master."""
from __future__ import annotations

import json
import datetime as dt
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageTk
import numpy as np

from fbs import editor_history, editor_state

ROOT = os.path.dirname(os.path.abspath(__file__))
GOLDMASTER = os.path.join(ROOT, "assets", "referencias", "fbs_goldmaster.png")
CANVAS_W, CANVAS_H = 1080, 1350
POLICY_MANUAL = "Manual — recomendado"
POLICY_RELEASE = "Ao soltar — lento"
POLICY_AUTO = "Automático leve — muito lento"
FAST_PREVIEW_PATH = os.path.join(ROOT, "outputs", "_fast_preview.png")
JOB_TEMP_PATH = os.path.join(ROOT, "jobs", "job.editor.tmp.json")

SLOT_JOB_FIELDS = {
    "txt_artista": ("artista", "Nome do artista"),
    "txt_edicao": ("edicao", "Edição"),
    "txt_data_mes": ("data", "Data (AAAA-MM-DD)"),
    "txt_data_dia": ("data", "Data (AAAA-MM-DD)"),
    "txt_data_semana": ("data", "Data (AAAA-MM-DD)"),
    "txt_data_hora": ("hora", "Hora"),
    "txt_local_nome": ("local_nome", "Nome do local"),
    "txt_local_bairro": ("local_bairro", "Bairro"),
    "txt_local_endereco": ("local_endereco", "Endereço"),
}

SLOT_BBOXES = {
    "foto_artista": (172, 45, 1003, 1181),
    "txt_artista": (56, 288, 502, 633),
    "txt_edicao": (57, 248, 263, 272),
    "txt_data_mes": (897, 70, 1039, 127),
    "txt_data_dia": (897, 133, 1039, 233),
    "txt_data_semana": (897, 252, 1039, 294),
    "txt_data_hora": (897, 299, 1039, 340),
    "txt_local_nome": (53, 1194, 345, 1251),
    "txt_local_bairro": (418, 1198, 784, 1251),
    "txt_local_endereco": (54, 1267, 663, 1289),
    "linhas_rodape": (53, 1166, 787, 1171),
    "global": (0, 0, CANVAS_W, CANVAS_H),
}

SLOTS = [
    "foto_artista", "txt_artista", "txt_edicao", "txt_data_mes",
    "txt_data_dia", "txt_data_semana", "txt_data_hora", "txt_local_nome",
    "txt_local_bairro", "txt_local_endereco", "linhas_rodape", "global",
]

TEXT_FIELDS = [
    ("offset_x", -500, 500, 1), ("offset_y", -500, 500, 1),
    ("tamanho", 8, 300, 1), ("tracking", -300, 500, 1),
    ("caixa_largura", 20, 1080, 1), ("caixa_altura", 20, 1350, 1),
    ("escala_x", 0.2, 3, .01), ("escala_y", 0.2, 3, .01),
    ("opacidade", 0, 1, .01), ("textura_opacidade", 0, 1, .01),
    ("espacamento_linhas", .3, 3, .01), ("gap_linhas_min", 0, 100, 1),
    ("cor", None, None, None),
]
PHOTO_FIELDS = [
    ("zoom", 1, 5, .01), ("offset_x", -600, 600, 1),
    ("offset_y", -700, 700, 1), ("brilho", 0, 2, .01),
    ("contraste", 0, 2, .01), ("saturacao", 0, 2, .01),
    ("nitidez", 0, 3, .01), ("temperatura", -100, 100, 1),
    ("mascara_opacidade", 0, 1, .01), ("mascara_blur", 0, 100, .5),
    ("mascara_offset_x", -600, 600, 1), ("mascara_offset_y", -700, 700, 1),
    ("mascara_escala", .1, 5, .01), ("mascara_contraste", 0, 4, .01),
    ("mascara_inverter", None, None, None),
    ("espelhar_horizontal", None, None, None),
]
LINE_FIELDS = [
    ("offset_x", -500, 500, 1), ("offset_y", -500, 500, 1),
    ("largura_1", 0, 1080, 1), ("largura_2", 0, 1080, 1),
    ("espessura", 1, 30, 1), ("cor", None, None, None),
]
GLOBAL_FIELDS = [
    ("grain_opacidade", 0, 1, .01), ("bordas_opacidade", 0, 1, .01),
    ("brilho", 0, 2, .01), ("contraste", 0, 2, .01),
    ("saturacao", 0, 2, .01),
]

DEFAULTS = {
    "offset_x": 0, "offset_y": 0, "tamanho": 100, "tracking": 0,
    "caixa_largura": 400, "caixa_altura": 300, "escala_x": 1,
    "escala_y": 1, "opacidade": 1, "textura_opacidade": .7,
    "espacamento_linhas": 1.2, "gap_linhas_min": 6, "cor": "#FFFFFF",
    "zoom": 1, "brilho": 1, "contraste": 1, "saturacao": 1,
    "nitidez": 1, "temperatura": 0, "mascara_opacidade": 1,
    "mascara_blur": 0, "mascara_offset_x": 0, "mascara_offset_y": 0,
    "mascara_escala": 1, "mascara_contraste": 1, "mascara_inverter": False,
    "espelhar_horizontal": False,
    "largura_1": 316, "largura_2": 379, "espessura": 2,
    "grain_opacidade": 0, "bordas_opacidade": 0,
}


class EditorVisual(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Editor visual FBS — Gold Master")
        self.geometry("1320x860")
        self.minsize(1050, 700)
        editor_state.inicializar_temporario()
        self.estado = editor_state.carregar_temporario()
        self.job_path = tk.StringVar(value=os.path.join("jobs", "job_gonzalo.json"))
        self._preparar_job_temporario(force=False)
        self.historico = editor_history.HistoricoEditor(self._capturar_snapshot())
        self.photo_var = tk.StringVar(value=str(self._carregar_job_temporario().get("foto", "")))
        self.photo_dirty = False
        self.slot = tk.StringVar(value="txt_artista")
        self.modo = tk.StringVar(value="Gerado")
        self.overlay_alpha = tk.DoubleVar(value=.5)
        self.politica_render = tk.StringVar(value=POLICY_MANUAL)
        self.status = tk.StringVar(value="Pronto. Ajustes são gravados apenas no arquivo temporário.")
        self.metricas = tk.StringVar(value="")
        self.vars = {}
        self.widgets = {}
        self.scale_vars = {}
        self.field_steps = {}
        self.dirty_fields = set()
        self.content_var = None
        self.content_key = None
        self.content_dirty = False
        self.current_slot = self.slot.get()
        self.preview_photo = None
        self.preview_scale = 1.0
        self.preview_origin = (0, 0)
        self.drag_start = None
        self.drag_values = None
        self.debounce_id = None
        self.render_running = False
        self.render_pending = False
        self.render_version = 0
        self.fast_running = False
        self.fast_pending = False
        self.fast_version = 0
        self.preview_epoch = 0
        self.change_version = 0
        self._cached_reference = Image.open(GOLDMASTER).convert("RGB").copy() if os.path.isfile(GOLDMASTER) else None
        self._cached_generated = None
        self._cached_ref_resized = None
        self._cached_output_path = None
        self._cached_metrics = ""
        self._render_queue = queue.Queue()
        self._fast_queue = queue.Queue()
        self.undo_button = None
        self.redo_button = None
        self._montar()
        self._reconstruir_controles()
        self._recarregar_gerado(force=True)
        self._mostrar_preview()
        self.after(100, self._poll_render_queue)

    def _montar(self):
        topo = ttk.Frame(self, padding=(10, 8))
        topo.pack(fill="x")
        ttk.Label(topo, text="Job:").pack(side="left")
        ttk.Entry(topo, textvariable=self.job_path, width=42).pack(side="left", padx=6)
        ttk.Button(topo, text="Escolher…", command=self._escolher_job).pack(side="left")
        ttk.Label(topo, text="Slot:").pack(side="left", padx=(16, 4))
        combo = ttk.Combobox(topo, textvariable=self.slot, values=SLOTS, state="readonly", width=23)
        combo.pack(side="left")
        combo.bind("<<ComboboxSelected>>", self._trocar_slot)
        ttk.Label(topo, text="Render:").pack(side="left", padx=(14, 4))
        ttk.Combobox(topo, textvariable=self.politica_render,
                     values=(POLICY_MANUAL, POLICY_RELEASE, POLICY_AUTO),
                     state="readonly", width=29).pack(side="left")
        ttk.Button(topo, text="Preview rápido", command=self.render_preview_fast).pack(side="left", padx=(8, 0))
        ttk.Button(topo, text="Renderizar PSD", command=self.render_preview_real).pack(side="left", padx=(5, 0))

        historico_bar = ttk.Frame(self, padding=(10, 0, 10, 7))
        historico_bar.pack(fill="x")
        self.undo_button = ttk.Button(historico_bar, text="↶ Desfazer  Ctrl+Z", command=self._desfazer)
        self.undo_button.pack(side="left")
        self.redo_button = ttk.Button(historico_bar, text="↷ Refazer  Ctrl+Shift+Z", command=self._refazer)
        self.redo_button.pack(side="left", padx=(5, 0))
        ttk.Button(historico_bar, text="Trocar foto…",
                   command=self._escolher_foto).pack(side="left", padx=(16, 0))
        ttk.Button(historico_bar, text="Voltar ao PSD original…",
                   command=self._voltar_psd_original).pack(side="left", padx=(5, 0))
        ttk.Label(historico_bar, text="Histórico desta sessão: ajustes + textos temporários.",
                  foreground="#606060").pack(side="left", padx=(12, 0))
        self.bind_all("<Control-z>", self._desfazer)
        self.bind_all("<Control-Shift-Z>", self._refazer)
        self.bind_all("<Control-y>", self._refazer)
        self._atualizar_botoes_historico()

        corpo = ttk.Panedwindow(self, orient="horizontal")
        corpo.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        esquerda = ttk.Frame(corpo)
        direita = ttk.Frame(corpo, width=370)
        corpo.add(esquerda, weight=4)
        corpo.add(direita, weight=2)

        modos = ttk.Frame(esquerda)
        modos.pack(fill="x", pady=(0, 5))
        for nome in ("Gerado", "Referência", "Lado a lado", "Overlay", "Diff"):
            ttk.Radiobutton(modos, text=nome, value=nome, variable=self.modo,
                            command=self._mostrar_preview).pack(side="left", padx=4)
        ttk.Label(modos, text="Opacidade overlay").pack(side="left", padx=(20, 4))
        ttk.Scale(modos, from_=0, to=1, variable=self.overlay_alpha,
                  command=lambda _v: self._mostrar_preview()).pack(side="left", fill="x", expand=True)
        ttk.Label(esquerda, textvariable=self.metricas).pack(fill="x", pady=(0, 4))

        self.canvas = tk.Canvas(esquerda, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._mostrar_preview())
        self.canvas.bind("<ButtonPress-1>", self._drag_inicio)
        self.canvas.bind("<B1-Motion>", self._drag_movimento)
        self.canvas.bind("<ButtonRelease-1>", self._drag_fim)
        ttk.Label(esquerda, text="Render PSD leva ~15s. Use Manual para calibrar rápido.",
                  foreground="#a06000").pack(fill="x", pady=(4, 0))

        self.controls_canvas = tk.Canvas(direita, highlightthickness=0)
        scroll = ttk.Scrollbar(direita, orient="vertical", command=self.controls_canvas.yview)
        self.controls_frame = ttk.Frame(self.controls_canvas, padding=8)
        self.controls_frame.bind("<Configure>", lambda _e: self.controls_canvas.configure(
            scrollregion=self.controls_canvas.bbox("all")))
        self.controls_canvas.create_window((0, 0), window=self.controls_frame, anchor="nw")
        self.controls_canvas.configure(yscrollcommand=scroll.set)
        self.controls_canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        botoes = ttk.Frame(self, padding=(10, 0, 10, 8))
        botoes.pack(fill="x")
        for texto, comando in (
            ("Salvar temporários", self._salvar_campos),
            ("Salvar em ajustes.json", self._salvar_principal),
            ("Salvar dados/foto no job", self._salvar_job_original),
            ("Restaurar do ajustes.json", self._restaurar),
            ("Criar backup agora", self._backup),
            ("Abrir outputs", lambda: os.startfile(os.path.join(ROOT, "outputs"))),
            ("Gerar imagem final", self._gerar_final),
        ):
            ttk.Button(botoes, text=texto, command=comando).pack(side="left", padx=3)
        ttk.Label(botoes, textvariable=self.status).pack(side="left", padx=12)

    def _campos_slot(self):
        slot = self.slot.get()
        if slot == "foto_artista":
            return PHOTO_FIELDS
        if slot == "linhas_rodape":
            return LINE_FIELDS
        if slot == "global":
            return GLOBAL_FIELDS
        return TEXT_FIELDS

    def _reconstruir_controles(self):
        for filho in self.controls_frame.winfo_children():
            filho.destroy()
        self.vars.clear()
        self.widgets.clear()
        self.scale_vars.clear()
        self.field_steps.clear()
        self.dirty_fields.clear()
        self.content_var = None
        self.content_key = None
        self.content_dirty = False
        self.photo_dirty = False
        ttk.Label(self.controls_frame, text=self.slot.get(), font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
        if self.slot.get() == "foto_artista":
            job = self._carregar_job_temporario()
            self.photo_var.set(str(job.get("foto", "")))
            foto = ttk.LabelFrame(self.controls_frame, text="Foto do artista", padding=6)
            foto.pack(fill="x", pady=(0, 10))
            entrada_foto = ttk.Entry(foto, textvariable=self.photo_var)
            entrada_foto.pack(side="left", fill="x", expand=True)
            entrada_foto.bind("<KeyRelease>", self._foto_digitada)
            entrada_foto.bind("<Return>", self._foto_confirmada)
            entrada_foto.bind("<FocusOut>", self._foto_confirmada)
            ttk.Button(foto, text="Escolher…", command=self._escolher_foto).pack(side="left", padx=(5, 0))
        if self.slot.get() in SLOT_JOB_FIELDS:
            self.content_key, rotulo = SLOT_JOB_FIELDS[self.slot.get()]
            job = self._carregar_job_temporario()
            self.content_var = tk.StringVar(value=str(job.get(self.content_key, "")))
            conteudo = ttk.LabelFrame(self.controls_frame, text=rotulo, padding=6)
            conteudo.pack(fill="x", pady=(0, 10))
            entrada_conteudo = ttk.Entry(conteudo, textvariable=self.content_var)
            entrada_conteudo.pack(fill="x")
            entrada_conteudo.bind("<KeyRelease>", self._conteudo_digitado)
            entrada_conteudo.bind("<Return>", self._conteudo_confirmado)
            entrada_conteudo.bind("<FocusOut>", self._conteudo_confirmado)
        dados = self.estado.get("feed", {}).get(self.slot.get(), {})
        for chave, minimo, maximo, resolucao in self._campos_slot():
            linha = ttk.Frame(self.controls_frame)
            linha.pack(fill="x", pady=3)
            ttk.Label(linha, text=chave, width=22).pack(side="left")
            valor = dados.get(chave, DEFAULTS.get(chave, 0))
            if isinstance(valor, bool) or chave == "mascara_inverter":
                var = tk.BooleanVar(value=bool(valor))
                widget = ttk.Checkbutton(linha, variable=var,
                                         command=lambda c=chave: self._controle_solto(c))
                widget.pack(side="left")
            elif minimo is None:
                var = tk.StringVar(value=str(valor))
                widget = ttk.Entry(linha, textvariable=var, width=16)
                widget.pack(side="left", fill="x", expand=True)
                widget.bind("<KeyRelease>", lambda _e, c=chave: self._entrada_digitada(c))
                widget.bind("<Return>", lambda _e, c=chave: self._controle_solto(c))
                widget.bind("<FocusOut>", lambda _e, c=chave: self._controle_solto(c))
                if chave == "cor":
                    ttk.Button(linha, text="Escolher…", command=lambda c=chave: self._escolher_cor(c)).pack(side="left", padx=(5, 0))
            else:
                passo = float(resolucao)
                numero = self._quantizar(float(valor), passo)
                if self.current_slot == "foto_artista" and chave == "zoom":
                    numero = max(1.0, numero)
                numero = self._limitar_numero_foto(chave, numero)
                var = tk.StringVar(value=self._formatar_numero(numero, passo))
                scale_var = tk.DoubleVar(value=numero)
                widget = ttk.Scale(linha, from_=minimo, to=maximo, variable=scale_var,
                                   command=lambda v, c=chave, p=passo: self._slider_alterado(c, v, p))
                widget.pack(side="left", fill="x", expand=True)
                widget.bind("<ButtonRelease-1>", lambda _e, c=chave: self._controle_solto(c))
                entrada = ttk.Entry(linha, textvariable=var, width=8)
                entrada.pack(side="left", padx=(5, 0))
                entrada.bind("<KeyRelease>", lambda _e, c=chave: self._entrada_digitada(c))
                entrada.bind("<Return>", lambda _e, c=chave: self._controle_solto(c))
                entrada.bind("<FocusOut>", lambda _e, c=chave: self._controle_solto(c))
                self.scale_vars[chave] = scale_var
                self.field_steps[chave] = passo
            self.vars[chave] = var
            self.widgets[chave] = widget
        self.after_idle(self.update_fast_overlay)

    def _valor(self, chave, var):
        valor = var.get()
        if isinstance(var, tk.BooleanVar):
            return bool(valor)
        if chave == "cor":
            cor = str(valor).strip().upper()
            if len(cor) == 4 and cor.startswith("#"):
                cor = "#" + "".join(c * 2 for c in cor[1:])
            if len(cor) != 7 or not cor.startswith("#") or any(c not in "0123456789ABCDEF" for c in cor[1:]):
                raise ValueError(f"{chave} deve usar o formato #RRGGBB")
            return cor
        if chave in self.field_steps:
            numero = float(str(valor).strip().replace(",", "."))
            numero = self._quantizar(numero, self.field_steps[chave])
            if self.current_slot == "foto_artista" and chave == "zoom":
                numero = max(1.0, numero)
            numero = self._limitar_numero_foto(chave, numero)
            return int(numero) if self.field_steps[chave] >= 1 else numero
        return valor

    @staticmethod
    def _quantizar(valor, passo):
        return round(round(float(valor) / passo) * passo, 6)

    @staticmethod
    def _formatar_numero(valor, passo):
        if passo >= 1:
            return str(int(round(valor)))
        casas = max(1, len(str(passo).rstrip("0").split(".")[-1]))
        return f"{valor:.{casas}f}".rstrip("0").rstrip(".")

    def _limite_offset_foto(self, chave):
        if self.current_slot != "foto_artista" or chave not in {"offset_x", "offset_y"}:
            return None
        try:
            zoom = max(1.0, float(str(self.vars["zoom"].get()).replace(",", ".")))
        except (KeyError, ValueError, tk.TclError):
            zoom = 1.0
        x1, y1, x2, y2 = SLOT_BBOXES["foto_artista"]
        dimensao = (x2 - x1) if chave == "offset_x" else (y2 - y1)
        # Offsets do editor são pixels inteiros; arredondar para baixo impede
        # que o número exibido ultrapasse a margem física por uma fração.
        return float(int(dimensao * (zoom - 1.0) / 2.0))

    def _limitar_numero_foto(self, chave, numero):
        limite = self._limite_offset_foto(chave)
        if limite is None:
            return numero
        return min(max(numero, -limite), limite)

    def _restringir_offsets_foto(self):
        if self.current_slot != "foto_artista":
            return
        for chave in ("offset_x", "offset_y"):
            if chave not in self.vars:
                continue
            try:
                anterior = float(str(self.vars[chave].get()).replace(",", "."))
            except ValueError:
                continue
            limitado = self._quantizar(self._limitar_numero_foto(chave, anterior), self.field_steps[chave])
            if limitado != anterior:
                self.vars[chave].set(self._formatar_numero(limitado, self.field_steps[chave]))
                self.scale_vars[chave].set(limitado)
                self.dirty_fields.add(chave)

    def _slider_alterado(self, chave, valor, passo):
        numero = self._quantizar(float(valor), passo)
        numero = self._limitar_numero_foto(chave, numero)
        self.vars[chave].set(self._formatar_numero(numero, passo))
        if abs(self.scale_vars[chave].get() - numero) > passo / 100:
            self.scale_vars[chave].set(numero)
        self._campo_alterado(chave)

    def _entrada_digitada(self, chave):
        self.dirty_fields.add(chave)
        self.change_version += 1
        self.status.set("Valor editado — confirme com Enter ou saia do campo.")
        try:
            valor = self._valor(chave, self.vars[chave])
            if chave in self.scale_vars:
                self.scale_vars[chave].set(float(valor))
            self.update_fast_overlay()
        except (ValueError, tk.TclError):
            pass

    def _escolher_cor(self, chave):
        atual = self.vars[chave].get()
        _rgb, hexadecimal = colorchooser.askcolor(color=atual if str(atual).startswith("#") else "#FFFFFF", parent=self)
        if hexadecimal:
            self.vars[chave].set(hexadecimal.upper())
            self._controle_solto(chave)

    def _salvar_campos(self, slot=None):
        slot = slot or self.current_slot
        alteracoes = {chave: self._valor(chave, self.vars[chave]) for chave in self.dirty_fields}
        if alteracoes:
            editor_state.atualizar_slot("feed", slot, alteracoes)
        if self.content_dirty:
            self._salvar_conteudo_temporario(registrar=False)
        if self.photo_dirty:
            self._salvar_foto_temporaria(registrar=False)
        self.estado = editor_state.carregar_temporario()
        self.dirty_fields.clear()
        self._registrar_historico()
        self.status.set("Ajustes temporários salvos.")
        return True

    def _campo_alterado(self, chave):
        self.dirty_fields.add(chave)
        self.change_version += 1
        self.status.set("Preview rápido — render real pendente.")
        self.update_fast_overlay()
        politica = self.politica_render.get()
        if politica == POLICY_AUTO:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(1500, self.render_preview_real)
        elif politica == POLICY_MANUAL:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(300, self.render_preview_fast)

    def _controle_solto(self, chave):
        try:
            valor = self._valor(chave, self.vars[chave])
            if chave in self.field_steps:
                self.vars[chave].set(self._formatar_numero(float(valor), self.field_steps[chave]))
                self.scale_vars[chave].set(float(valor))
            if chave == "zoom":
                self._restringir_offsets_foto()
        except (ValueError, tk.TclError) as exc:
            self.status.set(f"Valor inválido: {exc}")
            return
        self._campo_alterado(chave)
        politica = self.politica_render.get()
        if politica == POLICY_RELEASE:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(50, self.render_preview_real)
        elif politica == POLICY_MANUAL:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(50, self.render_preview_fast)

    def _trocar_slot(self, _evento=None):
        try:
            self._salvar_campos(self.current_slot)
        except ValueError as exc:
            self.slot.set(self.current_slot)
            self.status.set(f"Conteúdo inválido: {exc}")
            return
        self.current_slot = self.slot.get()
        self._reconstruir_controles()

    def _escolher_job(self):
        caminho = filedialog.askopenfilename(initialdir=os.path.join(ROOT, "jobs"), filetypes=(("JSON", "*.json"),))
        if caminho:
            self.job_path.set(os.path.relpath(caminho, ROOT))
            self._preparar_job_temporario(force=True)
            self.photo_var.set(str(self._carregar_job_temporario().get("foto", "")))
            self._reiniciar_historico()
            self._reconstruir_controles()
            self._recarregar_gerado(force=True)
            self._mostrar_preview()

    def _source_job_absoluto(self):
        caminho = self.job_path.get().strip()
        return caminho if os.path.isabs(caminho) else os.path.join(ROOT, caminho)

    def _job_absoluto(self):
        return JOB_TEMP_PATH

    def _foto_absoluta(self, caminho=None):
        caminho = (caminho if caminho is not None else self.photo_var.get()).strip()
        return caminho if os.path.isabs(caminho) else os.path.join(ROOT, caminho)

    def _validar_foto(self):
        caminho = self.photo_var.get().strip()
        if not caminho:
            raise ValueError("selecione uma foto")
        absoluto = self._foto_absoluta(caminho)
        if not os.path.isfile(absoluto):
            raise ValueError(f"foto não encontrada: {caminho}")
        try:
            with Image.open(absoluto) as imagem:
                imagem.verify()
        except Exception as exc:
            raise ValueError(f"arquivo de foto inválido: {caminho}") from exc
        return caminho.replace("\\", "/")

    def _salvar_foto_temporaria(self, registrar=True):
        caminho = self._validar_foto()
        dados = self._carregar_job_temporario()
        dados["foto"] = caminho
        self._salvar_json_atomico(JOB_TEMP_PATH, dados)
        self.photo_dirty = False
        if registrar:
            self._registrar_historico()

    def _foto_digitada(self, _evento=None):
        self.photo_dirty = True
        self.change_version += 1
        self.status.set("Foto editada — confirme com Enter ou escolha um arquivo.")

    def _foto_confirmada(self, _evento=None):
        if not self.photo_dirty:
            return
        try:
            self._salvar_foto_temporaria()
        except ValueError as exc:
            self.status.set(f"Foto inválida: {exc}")
            return
        self._render_apos_dado_alterado()

    def _escolher_foto(self):
        atual = self._foto_absoluta()
        inicial = os.path.dirname(atual) if os.path.isfile(atual) else os.path.join(ROOT, "fotos")
        if not os.path.isdir(inicial):
            inicial = ROOT
        caminho = filedialog.askopenfilename(
            title="Escolha a foto do artista",
            initialdir=inicial,
            filetypes=(("Imagens", "*.jpg *.jpeg *.png *.webp"), ("Todos os arquivos", "*.*")),
        )
        if not caminho:
            return
        try:
            relativo = os.path.relpath(caminho, ROOT).replace("\\", "/")
            self.photo_var.set(relativo)
            self.photo_dirty = True
            self.change_version += 1
            self._salvar_campos()
        except ValueError as exc:
            messagebox.showerror("Dados inválidos", str(exc))
            return
        self._render_apos_dado_alterado()

    def _render_apos_dado_alterado(self):
        politica = self.politica_render.get()
        if politica == POLICY_MANUAL:
            self.render_preview_fast()
        elif politica == POLICY_RELEASE:
            self.render_preview_real()
        else:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(1500, self.render_preview_real)

    def _capturar_snapshot(self):
        return {
            "ajustes": editor_state.carregar_temporario(),
            "job": self._carregar_job_temporario(),
        }

    def _reiniciar_historico(self):
        self.historico = editor_history.HistoricoEditor(self._capturar_snapshot())
        self._atualizar_botoes_historico()

    def _registrar_historico(self):
        alterou = self.historico.registrar(self._capturar_snapshot())
        self._atualizar_botoes_historico()
        return alterou

    def _atualizar_botoes_historico(self):
        if self.undo_button is not None:
            self.undo_button.configure(state="normal" if self.historico.pode_desfazer else "disabled")
        if self.redo_button is not None:
            self.redo_button.configure(state="normal" if self.historico.pode_refazer else "disabled")

    def _aplicar_snapshot(self, snapshot, acao):
        if self.debounce_id:
            self.after_cancel(self.debounce_id)
            self.debounce_id = None
        self.estado = editor_state.substituir_temporario(snapshot["ajustes"])
        self._salvar_json_atomico(JOB_TEMP_PATH, snapshot["job"])
        self.photo_var.set(str(snapshot["job"].get("foto", "")))
        self.dirty_fields.clear()
        self.content_dirty = False
        self.photo_dirty = False
        self.change_version += 1
        self._reconstruir_controles()
        self._atualizar_botoes_historico()
        self.render_preview_fast()
        self.status.set(f"{acao} — render PSD pendente.")

    def _desfazer(self, _evento=None):
        try:
            self._salvar_campos()
        except ValueError as exc:
            self.status.set(f"Não foi possível desfazer: {exc}")
            return "break"
        snapshot = self.historico.desfazer()
        if snapshot is None:
            self.status.set("Nada para desfazer.")
        else:
            self._aplicar_snapshot(snapshot, "Alteração desfeita")
        self._atualizar_botoes_historico()
        return "break"

    def _refazer(self, _evento=None):
        try:
            self._salvar_campos()
        except ValueError as exc:
            self.status.set(f"Não foi possível refazer: {exc}")
            return "break"
        snapshot = self.historico.refazer()
        if snapshot is None:
            self.status.set("Nada para refazer.")
        else:
            self._aplicar_snapshot(snapshot, "Alteração refeita")
        self._atualizar_botoes_historico()
        return "break"

    @staticmethod
    def _salvar_json_atomico(caminho, dados):
        temporario = caminho + ".write.tmp"
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        os.replace(temporario, caminho)

    def _preparar_job_temporario(self, force=False):
        origem = os.path.abspath(self._source_job_absoluto())
        if not force and os.path.isfile(JOB_TEMP_PATH):
            try:
                with open(JOB_TEMP_PATH, "r", encoding="utf-8") as arquivo:
                    existente = json.load(arquivo)
                if existente.get("_editor_source") == origem:
                    return
            except (OSError, json.JSONDecodeError):
                pass
        with open(origem, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        dados["_editor_source"] = origem
        self._salvar_json_atomico(JOB_TEMP_PATH, dados)

    @staticmethod
    def _carregar_job_temporario():
        with open(JOB_TEMP_PATH, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def _validar_conteudo(self):
        if not self.content_key or self.content_var is None:
            return None
        valor = self.content_var.get().strip()
        if not valor:
            raise ValueError("o conteúdo não pode ficar vazio")
        if self.content_key == "edicao":
            try:
                numero = int(valor)
            except ValueError as exc:
                raise ValueError("edição deve ser um número inteiro") from exc
            if numero <= 0:
                raise ValueError("edição deve ser positiva")
            return numero
        if self.content_key == "data":
            try:
                dt.date.fromisoformat(valor)
            except ValueError as exc:
                raise ValueError("data deve usar AAAA-MM-DD") from exc
        return valor

    def _salvar_conteudo_temporario(self, registrar=True):
        valor = self._validar_conteudo()
        if self.content_key and valor is not None:
            dados = self._carregar_job_temporario()
            dados[self.content_key] = valor
            self._salvar_json_atomico(JOB_TEMP_PATH, dados)
        self.content_dirty = False
        if registrar:
            self._registrar_historico()

    def _conteudo_digitado(self, _evento=None):
        self.content_dirty = True
        self.change_version += 1
        self.status.set("Texto editado — preview rápido pendente.")
        try:
            self._validar_conteudo()
        except ValueError:
            return
        if self.politica_render.get() == POLICY_MANUAL:
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(300, self.render_preview_fast)

    def _conteudo_confirmado(self, _evento=None):
        try:
            self._salvar_conteudo_temporario()
        except ValueError as exc:
            self.status.set(f"Conteúdo inválido: {exc}")
            return
        self._render_apos_dado_alterado()

    def _output_path(self):
        try:
            with open(self._job_absoluto(), "r", encoding="utf-8") as arquivo:
                edicao = json.load(arquivo)["edicao"]
            return os.path.join(ROOT, "outputs", f"fbs{edicao}_feed.png")
        except Exception:
            return None

    def render_preview_fast(self):
        """Render aproximado sem PSD em processo de background."""
        try:
            self._salvar_campos()
        except Exception as exc:
            messagebox.showerror("Ajustes inválidos", str(exc))
            return
        versao = self.change_version
        if self.fast_running:
            self.fast_pending = True
            self.status.set("Preview rápido pendente…")
            return
        self.fast_running = True
        self.fast_version = versao
        self.preview_epoch += 1
        epoch = self.preview_epoch
        self.status.set("Gerando preview rápido…")
        job_absoluto = self._job_absoluto()
        ajustes_temporarios = editor_state.AJUSTES_TEMP

        def executar():
            proc = subprocess.run(
                [sys.executable, "render_fast.py", "--job", job_absoluto,
                 "--ajustes", ajustes_temporarios, "--out", FAST_PREVIEW_PATH],
                cwd=ROOT, capture_output=True, text=True,
            )
            self._fast_queue.put((versao, epoch, proc))

        threading.Thread(target=executar, daemon=True).start()

    def render_preview_real(self):
        """Render PSD real em background; nunca é chamado por tick de slider."""
        try:
            self._salvar_campos()
        except Exception as exc:
            messagebox.showerror("Ajustes inválidos", str(exc))
            return
        versao = self.change_version
        if self.render_running:
            self.render_pending = True
            self.status.set("Alteração pendente; aguardando render atual…")
            return
        self.render_version = versao
        self.render_running = True
        self.preview_epoch += 1  # invalida preview rápido anterior
        self.status.set("Renderizando PSD…")
        job_absoluto = self._job_absoluto()
        ajustes_temporarios = editor_state.AJUSTES_TEMP

        def executar():
            proc = subprocess.run(
                [sys.executable, "gerar.py", "--job", job_absoluto,
                 "--ajustes", ajustes_temporarios],
                cwd=ROOT, capture_output=True, text=True,
            )
            self._render_queue.put((versao, proc))

        threading.Thread(target=executar, daemon=True).start()

    def _poll_render_queue(self):
        try:
            while True:
                versao, processo = self._render_queue.get_nowait()
                self._render_concluido(versao, processo)
        except queue.Empty:
            pass
        try:
            while True:
                versao, epoch, processo = self._fast_queue.get_nowait()
                self._fast_concluido(versao, epoch, processo)
        except queue.Empty:
            pass
        try:
            self.after(100, self._poll_render_queue)
        except tk.TclError:
            pass

    @staticmethod
    def _resumir_erro(processo):
        texto = (processo.stderr or processo.stdout or "Erro desconhecido").strip()
        linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
        for linha in reversed(linhas):
            if linha.startswith(("ValueError:", "RuntimeError:", "ERRO:")):
                return linha
        return linhas[-1] if linhas else "Erro desconhecido"

    def _fast_concluido(self, versao, epoch, processo):
        self.fast_running = False
        if processo.returncode != 0:
            self.status.set("Falha no preview rápido.")
            messagebox.showerror("Erro no preview rápido", self._resumir_erro(processo))
        elif versao == self.change_version and epoch == self.preview_epoch:
            self._recarregar_gerado(force=True, caminho=FAST_PREVIEW_PATH, atualizar_metricas=False)
            self.status.set("Preview rápido atualizado — validação PSD pendente.")
            self._mostrar_preview()
        else:
            self.status.set("Preview rápido ignorado: existe mudança mais recente.")
        if self.fast_pending:
            self.fast_pending = False
            self.render_preview_fast()

    def _render_concluido(self, versao, processo):
        self.render_running = False
        if processo.returncode != 0:
            self.status.set("Falha no preview.")
            messagebox.showerror("Erro ao renderizar", self._resumir_erro(processo))
        elif versao == self.change_version:
            self._recarregar_gerado(force=True)
            self.status.set("Preview atualizado.")
            self._mostrar_preview()
        else:
            self.status.set("Render ignorado: já existe mudança mais recente.")
        if self.render_pending:
            self.render_pending = False
            self.render_preview_real()

    def _recarregar_gerado(self, force=False, caminho=None, atualizar_metricas=True):
        caminho = caminho or self._output_path()
        if caminho and os.path.isfile(caminho) and (force or caminho != self._cached_output_path):
            self._cached_generated = Image.open(caminho).convert("RGB").copy()
            self._cached_output_path = caminho
            self._cached_ref_resized = (
                self._cached_reference.resize(self._cached_generated.size, Image.LANCZOS)
                if self._cached_reference else None
            )
            if atualizar_metricas:
                self._atualizar_metricas_cache()
            else:
                self._cached_metrics = ""

    def _atualizar_metricas_cache(self):
        if self._cached_generated is None or self._cached_ref_resized is None:
            self._cached_metrics = ""
            return
        a = np.asarray(self._cached_generated, dtype=np.float32)
        b = np.asarray(self._cached_ref_resized, dtype=np.float32)
        media = float(np.abs(a - b).mean())
        texto = f"Diferença média: {media:.2f}/255"
        try:
            from skimage.metrics import structural_similarity
            ssim = structural_similarity(a.astype(np.uint8), b.astype(np.uint8), channel_axis=2)
            texto += f"  |  SSIM: {ssim:.4f}"
        except Exception:
            pass
        self._cached_metrics = texto

    def _carregar_imagens(self):
        return self._cached_generated, self._cached_reference

    def _imagem_modo(self):
        gerado, referencia = self._carregar_imagens()
        modo = self.modo.get()
        self.metricas.set(self._cached_metrics)
        if modo == "Referência":
            return referencia
        if modo == "Lado a lado" and gerado and referencia:
            ref = self._cached_ref_resized
            saida = Image.new("RGB", (gerado.width * 2, gerado.height))
            saida.paste(gerado, (0, 0)); saida.paste(ref, (gerado.width, 0))
            return saida
        if modo == "Overlay" and gerado and referencia:
            ref = self._cached_ref_resized
            return Image.blend(gerado, ref, float(self.overlay_alpha.get()))
        if modo == "Diff" and gerado and referencia:
            ref = self._cached_ref_resized
            diff = np.abs(np.asarray(gerado, dtype=np.int16) - np.asarray(ref, dtype=np.int16))
            return Image.fromarray(np.clip(diff * 2, 0, 255).astype(np.uint8), "RGB")
        return gerado or referencia

    def _mostrar_preview(self):
        if not hasattr(self, "canvas"):
            return
        imagem = self._imagem_modo()
        self.canvas.delete("all")
        if imagem is None:
            self.canvas.create_text(300, 250, text="Renderize um preview.", fill="white")
            return
        cw, ch = max(10, self.canvas.winfo_width()), max(10, self.canvas.winfo_height())
        escala = min(cw / imagem.width, ch / imagem.height)
        tamanho = (max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala)))
        exibida = imagem.resize(tamanho, Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(exibida)
        ox, oy = (cw - tamanho[0]) // 2, (ch - tamanho[1]) // 2
        self.canvas.create_image(ox, oy, image=self.preview_photo, anchor="nw")
        self.preview_scale = escala if self.modo.get() != "Lado a lado" else escala * 2
        self.preview_origin = (ox, oy)
        self.update_fast_overlay()

    def _valor_visual(self, chave, fallback):
        dados = self.estado.get("feed", {}).get(self.current_slot, {})
        if chave in self.dirty_fields or chave in dados:
            try:
                return self._valor(chave, self.vars[chave])
            except (KeyError, tk.TclError, ValueError):
                return dados.get(chave, fallback)
        return fallback

    def update_fast_overlay(self):
        """Atualiza somente a guia instantânea; nunca chama gerar.py."""
        if not hasattr(self, "canvas"):
            return
        self.canvas.delete("fast-guide")
        slot = self.current_slot
        if slot == "global" or self.modo.get() not in ("Gerado", "Overlay"):
            return
        x1, y1, x2, y2 = SLOT_BBOXES[slot]
        if slot.startswith("txt_"):
            bbox_largura, bbox_altura = x2 - x1, y2 - y1
            x1 = float(self._valor_visual("caixa_x", x1))
            largura = float(self._valor_visual("caixa_largura", bbox_largura))
            altura = float(self._valor_visual("caixa_altura", bbox_altura))
            x2, y2 = x1 + largura, y1 + altura
        ox = float(self._valor_visual("offset_x", 0))
        oy = float(self._valor_visual("offset_y", 0))
        if slot in {"txt_data_mes", "txt_data_dia", "txt_data_semana", "txt_data_hora"}:
            ox = 0  # eixo horizontal é fixado pelo pipeline.
        x1, x2, y1, y2 = x1 + ox, x2 + ox, y1 + oy, y2 + oy
        origem_x, origem_y = self.preview_origin
        escala = self.preview_scale
        coords = (origem_x + x1 * escala, origem_y + y1 * escala,
                  origem_x + x2 * escala, origem_y + y2 * escala)
        self.canvas.create_rectangle(*coords, outline="#00ff66", width=2,
                                     dash=(6, 4), tags="fast-guide")
        self.canvas.create_text(coords[0] + 4, coords[1] + 4, text=slot,
                                fill="#00ff66", anchor="nw", tags="fast-guide")

    def _drag_inicio(self, evento):
        if self.slot.get() == "global" or self.modo.get() not in ("Gerado", "Overlay"):
            return
        self.drag_start = (evento.x, evento.y)
        self.drag_values = (
            float(self._valor("offset_x", self.vars["offset_x"])) if "offset_x" in self.vars else 0,
            float(self._valor("offset_y", self.vars["offset_y"])) if "offset_y" in self.vars else 0,
        )

    def _set_numero_controle(self, chave, valor):
        passo = self.field_steps.get(chave, 1)
        numero = self._quantizar(self._limitar_numero_foto(chave, valor), passo)
        self.vars[chave].set(self._formatar_numero(numero, passo))
        if chave in self.scale_vars:
            self.scale_vars[chave].set(numero)

    def _drag_movimento(self, evento):
        if not self.drag_start:
            return
        dx = (evento.x - self.drag_start[0]) / max(self.preview_scale, .001)
        dy = (evento.y - self.drag_start[1]) / max(self.preview_scale, .001)
        slot = self.slot.get()
        if "offset_x" in self.vars and slot not in {"txt_data_mes", "txt_data_dia", "txt_data_semana", "txt_data_hora"}:
            self._set_numero_controle("offset_x", self.drag_values[0] + dx)
            self.dirty_fields.add("offset_x")
        if "offset_y" in self.vars:
            self._set_numero_controle("offset_y", self.drag_values[1] + dy)
            self.dirty_fields.add("offset_y")
        self.change_version += 1
        self.status.set("Preview rápido — arrastando guia.")
        self.update_fast_overlay()

    def _drag_fim(self, _evento):
        if not self.drag_start:
            return
        self.drag_start = None
        self._salvar_campos()
        politica = self.politica_render.get()
        if politica in (POLICY_RELEASE, POLICY_AUTO):
            self.render_preview_real()
        else:
            self.status.set("Render real pendente — clique em Renderizar PSD.")
            self.render_preview_fast()

    def _salvar_principal(self):
        self._salvar_campos()
        if not messagebox.askyesno("Salvar ajustes", "Criar backup e substituir ajustes.json?"):
            return
        backup = editor_state.salvar_no_principal()
        self.status.set(f"ajustes.json salvo. Backup: {os.path.basename(backup)}")

    def _restaurar(self):
        if messagebox.askyesno("Restaurar", "Descartar temporários e recarregar ajustes.json?"):
            self.estado = editor_state.restaurar_do_principal()
            self._registrar_historico()
            self._reconstruir_controles()
            self.status.set("Temporário restaurado do ajustes.json.")
            self.render_preview_fast()

    def _voltar_psd_original(self):
        mensagem = (
            "Remover todos os ajustes visuais temporários do feed e voltar às "
            "medidas/posições herdadas do PSD?\n\n"
            "ajustes.json e o job original NÃO serão alterados. "
            "Os textos temporários serão preservados e esta ação poderá ser "
            "desfeita com Ctrl+Z."
        )
        if not messagebox.askyesno("Voltar ao PSD original", mensagem, icon="warning"):
            return
        try:
            self._salvar_campos()
        except ValueError as exc:
            messagebox.showerror("Ajustes inválidos", str(exc))
            return
        self.estado = editor_state.restaurar_feed_psd()
        self._registrar_historico()
        self._reconstruir_controles()
        self.change_version += 1
        self.render_preview_fast()
        self.status.set("Overrides do feed removidos — PSD original; Ctrl+Z para desfazer.")

    def _backup(self):
        backup = editor_state.criar_backup()
        self.status.set(f"Backup criado: {os.path.basename(backup)}")

    def _salvar_job_original(self):
        try:
            self._salvar_campos()
        except ValueError as exc:
            messagebox.showerror("Dados inválidos", str(exc))
            return
        if not messagebox.askyesno("Salvar dados e foto", "Criar backup e atualizar o job selecionado?"):
            return
        origem = self._source_job_absoluto()
        os.makedirs(editor_state.BACKUPS_DIR, exist_ok=True)
        timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup = os.path.join(editor_state.BACKUPS_DIR,
                              f"job_{os.path.splitext(os.path.basename(origem))[0]}_{timestamp}.json")
        shutil.copy2(origem, backup)
        dados = self._carregar_job_temporario()
        dados.pop("_editor_source", None)
        self._salvar_json_atomico(origem, dados)
        self.status.set(f"Job salvo. Backup: {os.path.basename(backup)}")

    def _gerar_final(self):
        subprocess.Popen([sys.executable, "gerar.py", "--job", self._job_absoluto()], cwd=ROOT)
        self.status.set("Geração final iniciada com ajustes.json.")


if __name__ == "__main__":
    EditorVisual().mainloop()
