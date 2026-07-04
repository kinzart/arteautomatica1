#!/usr/bin/env python
"""Painel local para preencher os dados essenciais e gerar o cartaz."""
import datetime
import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

ROOT = os.path.dirname(os.path.abspath(__file__))
JOB_PATH = os.path.join(ROOT, "jobs", "job.json")
FOTOS_DIR = os.path.join(ROOT, "fotos")


class PainelFBS(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de Cartaz FBS")
        self.geometry("920x720")
        self.minsize(780, 600)
        self.job = self._carregar_job()
        self.preview_ref = None
        self._montar()

    def _carregar_job(self):
        with open(JOB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _montar(self):
        principal = ttk.Frame(self, padding=20)
        principal.pack(fill="both", expand=True)
        principal.columnconfigure(1, weight=1)
        principal.rowconfigure(5, weight=1)

        self.artista = tk.StringVar(value=self.job.get("artista", ""))
        self.foto = tk.StringVar(value=self.job.get("foto", ""))
        self.data = tk.StringVar(value=self.job.get("data", ""))
        self.edicao = tk.StringVar(value=str(self.job.get("edicao", "")))
        self.status = tk.StringVar(value="Preencha os dados e clique em Gerar cartaz.")

        campos = (
            ("Nome do artista", self.artista),
            ("Data (AAAA-MM-DD)", self.data),
            ("Edição", self.edicao),
        )
        for linha, (rotulo, variavel) in enumerate(campos):
            ttk.Label(principal, text=rotulo).grid(row=linha, column=0, sticky="w", padx=(0, 12), pady=7)
            ttk.Entry(principal, textvariable=variavel).grid(row=linha, column=1, columnspan=2, sticky="ew", pady=7)

        ttk.Label(principal, text="Foto").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=7)
        ttk.Entry(principal, textvariable=self.foto).grid(row=3, column=1, sticky="ew", pady=7)
        ttk.Button(principal, text="Escolher foto…", command=self._escolher_foto).grid(row=3, column=2, padx=(10, 0), pady=7)

        botoes = ttk.Frame(principal)
        botoes.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 14))
        self.botao_gerar = ttk.Button(botoes, text="Gerar cartaz", command=self._gerar)
        self.botao_gerar.pack(side="left")
        ttk.Button(botoes, text="Abrir resultado", command=self._abrir_resultado).pack(side="left", padx=10)
        ttk.Label(botoes, textvariable=self.status).pack(side="left", padx=12)

        self.preview = ttk.Label(principal, anchor="center")
        self.preview.grid(row=5, column=0, columnspan=3, sticky="nsew")
        self._atualizar_preview()

    def _escolher_foto(self):
        caminho = filedialog.askopenfilename(
            title="Escolha a foto do artista",
            initialdir=FOTOS_DIR,
            filetypes=(("Imagens", "*.jpg *.jpeg *.png *.webp"), ("Todos os arquivos", "*.*")),
        )
        if caminho:
            self.foto.set(os.path.relpath(caminho, ROOT).replace("\\", "/"))

    def _validar(self):
        artista = self.artista.get().strip()
        if not artista:
            raise ValueError("Informe o nome do artista.")
        try:
            datetime.date.fromisoformat(self.data.get().strip())
        except ValueError as exc:
            raise ValueError("A data deve estar no formato AAAA-MM-DD.") from exc
        try:
            edicao = int(self.edicao.get().strip())
            if edicao <= 0:
                raise ValueError
        except ValueError as exc:
            raise ValueError("A edição deve ser um número inteiro positivo.") from exc
        foto = self.foto.get().strip()
        foto_abs = foto if os.path.isabs(foto) else os.path.join(ROOT, foto)
        if not os.path.isfile(foto_abs):
            raise ValueError(f"Foto não encontrada: {foto}")
        return artista, foto, self.data.get().strip(), edicao

    def _gerar(self):
        try:
            artista, foto, data, edicao = self._validar()
        except ValueError as exc:
            messagebox.showerror("Dados inválidos", str(exc))
            return

        self.job.update({"artista": artista, "foto": foto, "data": data, "edicao": edicao})
        with open(JOB_PATH, "w", encoding="utf-8") as f:
            json.dump(self.job, f, ensure_ascii=False, indent=2)
            f.write("\n")

        self.botao_gerar.configure(state="disabled")
        self.status.set("Gerando…")
        self.update_idletasks()
        processo = subprocess.run(
            [sys.executable, "gerar.py", "--job", os.path.relpath(JOB_PATH, ROOT)],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.botao_gerar.configure(state="normal")
        if processo.returncode != 0:
            self.status.set("Falha na geração.")
            detalhes = (processo.stderr or processo.stdout).strip()
            linhas = [linha for linha in detalhes.splitlines() if linha.strip()]
            resumo = next((linha.removeprefix("ERRO: ").removeprefix("ERRO inesperado: ")
                           for linha in linhas if linha.startswith("ERRO")), linhas[-1] if linhas else "Erro desconhecido")
            messagebox.showerror("Erro ao gerar", resumo)
            return
        self.status.set("Cartaz gerado com sucesso.")
        self._atualizar_preview()

    def _resultado_path(self):
        try:
            edicao = int(self.edicao.get())
        except ValueError:
            return None
        return os.path.join(ROOT, "outputs", f"fbs{edicao}_feed.png")

    def _atualizar_preview(self):
        caminho = self._resultado_path()
        if not caminho or not os.path.isfile(caminho):
            self.preview.configure(text="A pré-visualização aparecerá aqui.", image="")
            return
        imagem = Image.open(caminho).convert("RGB")
        imagem.thumbnail((440, 550), Image.LANCZOS)
        self.preview_ref = ImageTk.PhotoImage(imagem)
        self.preview.configure(image=self.preview_ref, text="")

    def _abrir_resultado(self):
        caminho = self._resultado_path()
        if not caminho or not os.path.isfile(caminho):
            messagebox.showinfo("Resultado", "Gere o cartaz primeiro.")
            return
        os.startfile(caminho)


if __name__ == "__main__":
    PainelFBS().mainloop()
