# arteautomatica1

Gerador local de cartazes FBS orientado por um template PSD. O usuário informa
artista, foto, data e edição pelo painel; o pipeline substitui os elementos
variáveis, aplica enquadramento, máscaras, textura e ajustes tipográficos.

## Uso

No Windows, abra `abrir_painel.bat`. Alternativamente:

```powershell
python painel.py
```

Geração direta:

```powershell
python gerar.py --job jobs/job.json
```

Os PNGs são gravados em `outputs/`. Consulte `AJUSTES.md` para todos os
controles e `RESUMO_PROJETO.md` para arquitetura, estado e próximos passos.

Referência visual oficial: `assets/referencias/fbs_goldmaster.png`. O PSD
continua sendo usado como estrutura técnica, não como alvo visual final.

## Testes

```powershell
python -m unittest -v test_layout_artista.py
```
