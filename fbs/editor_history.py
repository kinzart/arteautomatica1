"""Histórico em memória para desfazer/refazer estados completos do editor."""
from __future__ import annotations

import copy


class HistoricoEditor:
    def __init__(self, estado_inicial, limite=100):
        self.limite = max(2, int(limite))
        self._estados = [copy.deepcopy(estado_inicial)]
        self._indice = 0

    @property
    def pode_desfazer(self):
        return self._indice > 0

    @property
    def pode_refazer(self):
        return self._indice < len(self._estados) - 1

    @property
    def atual(self):
        return copy.deepcopy(self._estados[self._indice])

    def registrar(self, estado):
        estado = copy.deepcopy(estado)
        if estado == self._estados[self._indice]:
            return False
        del self._estados[self._indice + 1:]
        self._estados.append(estado)
        if len(self._estados) > self.limite:
            excesso = len(self._estados) - self.limite
            del self._estados[:excesso]
        self._indice = len(self._estados) - 1
        return True

    def desfazer(self):
        if not self.pode_desfazer:
            return None
        self._indice -= 1
        return self.atual

    def refazer(self):
        if not self.pode_refazer:
            return None
        self._indice += 1
        return self.atual
