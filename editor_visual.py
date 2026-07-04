#!/usr/bin/env python
"""Editor visual seguro para calibrar ajustes contra o gold master."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
import numpy as np

from fbs import editor_state

ROOT = os.path.dirname(os.path.abspath(__file__))
GOLDMASTER = os.path.join(ROOT, "assets", "referencias", "fbs_goldmaster.png")
CANVAS_W, CANVAS_H = 1080, 1350

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
    ("zoom", .1, 5, .01), ("offset_x", -600, 600, 1),
    ("offset_y", -700, 700, 1), ("brilho", 0, 2, .01),
    ("contraste", 0, 2, .01), ("saturacao", 0, 2, .01),
    ("nitidez", 0, 3, .01), ("temperatura", -100, 100, 1),
    ("mascara_opacidade", 0, 1, .01), ("mascara_blur", 0, 100, .5),
    ("mascara_offset_x", -600, 600, 1), ("mascara_offset_y", -700, 700, 1),
    ("mascara_escala", .1, 5, .01), ("mascara_contraste", 0, 4, .01),
    ("mascara_inverter", None, None, None),
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
        self.slot = tk.StringVar(value="txt_artista")
        self.modo = tk.StringVar(value="Gerado")
        self.overlay_alpha = tk.DoubleVar(value=.5)
        self.politica_render = tk.StringVar(value="Ao soltar")
        self.status = tk.StringVar(value="Pronto. Ajustes são gravados apenas no arquivo temporário.")
        self.metricas = tk.StringVar(value="")
        self.vars = {}
        self.widgets = {}
        self.dirty_fields = set()
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
        self.change_version = 0
        self._cached_reference = Image.open(GOLDMASTER).convert("RGB").copy() if os.path.isfile(GOLDMASTER) else None
        self._cached_generated = None
        self._cached_ref_resized = None
        self._cached_output_path = None
        self._cached_metrics = ""
        self._render_queue = queue.Queue()
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
                     values=("Manual", "Ao soltar", "Automático leve"),
                     state="readonly", width=17).pack(side="left")
        ttk.Button(topo, text="Renderizar preview", command=self.render_preview_real).pack(side="left", padx=(8, 0))

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
        self.dirty_fields.clear()
        ttk.Label(self.controls_frame, text=self.slot.get(), font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))
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
                widget.bind("<KeyRelease>", lambda _e, c=chave: self._campo_alterado(c))
                widget.bind("<Return>", lambda _e, c=chave: self._controle_solto(c))
                widget.bind("<FocusOut>", lambda _e, c=chave: self._controle_solto(c))
            else:
                var = tk.DoubleVar(value=float(valor))
                widget = ttk.Scale(linha, from_=minimo, to=maximo, variable=var,
                                   command=lambda _v, c=chave: self._campo_alterado(c))
                widget.pack(side="left", fill="x", expand=True)
                widget.bind("<ButtonRelease-1>", lambda _e, c=chave: self._controle_solto(c))
                entrada = ttk.Entry(linha, textvariable=var, width=8)
                entrada.pack(side="left", padx=(5, 0))
                entrada.bind("<KeyRelease>", lambda _e, c=chave: self._campo_alterado(c))
                entrada.bind("<Return>", lambda _e, c=chave: self._controle_solto(c))
                entrada.bind("<FocusOut>", lambda _e, c=chave: self._controle_solto(c))
            self.vars[chave] = var
            self.widgets[chave] = widget
        self.after_idle(self.update_fast_overlay)

    def _valor(self, chave, var):
        valor = var.get()
        if isinstance(var, tk.BooleanVar):
            return bool(valor)
        if chave == "cor":
            return str(valor)
        if isinstance(valor, float) and valor.is_integer():
            return int(valor)
        return valor

    def _salvar_campos(self, slot=None):
        slot = slot or self.current_slot
        alteracoes = {chave: self._valor(chave, self.vars[chave]) for chave in self.dirty_fields}
        if alteracoes:
            editor_state.atualizar_slot("feed", slot, alteracoes)
        self.estado = editor_state.carregar_temporario()
        self.dirty_fields.clear()
        self.status.set("Ajustes temporários salvos.")
        return True

    def _campo_alterado(self, chave):
        self.dirty_fields.add(chave)
        self.change_version += 1
        self.status.set("Preview rápido — render real pendente.")
        self.update_fast_overlay()
        if self.politica_render.get() == "Automático leve":
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(1500, self.render_preview_real)

    def _controle_solto(self, chave):
        self._campo_alterado(chave)
        if self.politica_render.get() == "Ao soltar":
            if self.debounce_id:
                self.after_cancel(self.debounce_id)
            self.debounce_id = self.after(50, self.render_preview_real)

    def _trocar_slot(self, _evento=None):
        self._salvar_campos(self.current_slot)
        self.current_slot = self.slot.get()
        self._reconstruir_controles()

    def _escolher_job(self):
        caminho = filedialog.askopenfilename(initialdir=os.path.join(ROOT, "jobs"), filetypes=(("JSON", "*.json"),))
        if caminho:
            self.job_path.set(os.path.relpath(caminho, ROOT))
            self._recarregar_gerado(force=True)
            self._mostrar_preview()

    def _job_absoluto(self):
        caminho = self.job_path.get().strip()
        return caminho if os.path.isabs(caminho) else os.path.join(ROOT, caminho)

    def _output_path(self):
        try:
            with open(self._job_absoluto(), "r", encoding="utf-8") as arquivo:
                edicao = json.load(arquivo)["edicao"]
            return os.path.join(ROOT, "outputs", f"fbs{edicao}_feed.png")
        except Exception:
            return None

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
            self.after(100, self._poll_render_queue)
        except tk.TclError:
            pass

    def _render_concluido(self, versao, processo):
        self.render_running = False
        if processo.returncode != 0:
            self.status.set("Falha no preview.")
            messagebox.showerror("Erro ao renderizar", processo.stderr or processo.stdout)
        elif versao == self.change_version:
            self._recarregar_gerado(force=True)
            self.status.set("Preview atualizado.")
            self._mostrar_preview()
        else:
            self.status.set("Render ignorado: já existe mudança mais recente.")
        if self.render_pending:
            self.render_pending = False
            self.render_preview_real()

    def _recarregar_gerado(self, force=False):
        caminho = self._output_path()
        if caminho and os.path.isfile(caminho) and (force or caminho != self._cached_output_path):
            self._cached_generated = Image.open(caminho).convert("RGB").copy()
            self._cached_output_path = caminho
            self._cached_ref_resized = (
                self._cached_reference.resize(self._cached_generated.size, Image.LANCZOS)
                if self._cached_reference else None
            )
            self._atualizar_metricas_cache()

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
            float(self.vars.get("offset_x", tk.DoubleVar(value=0)).get()),
            float(self.vars.get("offset_y", tk.DoubleVar(value=0)).get()),
        )

    def _drag_movimento(self, evento):
        if not self.drag_start:
            return
        dx = (evento.x - self.drag_start[0]) / max(self.preview_scale, .001)
        dy = (evento.y - self.drag_start[1]) / max(self.preview_scale, .001)
        slot = self.slot.get()
        if "offset_x" in self.vars and slot not in {"txt_data_mes", "txt_data_dia", "txt_data_semana", "txt_data_hora"}:
            self.vars["offset_x"].set(round(self.drag_values[0] + dx))
            self.dirty_fields.add("offset_x")
        if "offset_y" in self.vars:
            self.vars["offset_y"].set(round(self.drag_values[1] + dy))
            self.dirty_fields.add("offset_y")
        self.change_version += 1
        self.status.set("Preview rápido — arrastando guia.")
        self.update_fast_overlay()

    def _drag_fim(self, _evento):
        if not self.drag_start:
            return
        self.drag_start = None
        self._salvar_campos()
        if self.politica_render.get() in ("Ao soltar", "Automático leve"):
            self.render_preview_real()
        else:
            self.status.set("Render real pendente — clique em Renderizar preview.")

    def _salvar_principal(self):
        self._salvar_campos()
        if not messagebox.askyesno("Salvar ajustes", "Criar backup e substituir ajustes.json?"):
            return
        backup = editor_state.salvar_no_principal()
        self.status.set(f"ajustes.json salvo. Backup: {os.path.basename(backup)}")

    def _restaurar(self):
        if messagebox.askyesno("Restaurar", "Descartar temporários e recarregar ajustes.json?"):
            self.estado = editor_state.restaurar_do_principal()
            self._reconstruir_controles()
            self.status.set("Temporário restaurado do ajustes.json.")

    def _backup(self):
        backup = editor_state.criar_backup()
        self.status.set(f"Backup criado: {os.path.basename(backup)}")

    def _gerar_final(self):
        subprocess.Popen([sys.executable, "gerar.py", "--job", self._job_absoluto()], cwd=ROOT)
        self.status.set("Geração final iniciada com ajustes.json.")


if __name__ == "__main__":
    EditorVisual().mainloop()
