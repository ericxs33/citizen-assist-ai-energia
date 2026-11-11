"""Configuração local da IA de apoio.

As chaves de API ficam em config_ia.json, na pasta do projeto, SOMENTE neste computador.
O arquivo está no .gitignore, então não vai para o GitHub. Nunca escreva chaves dentro de arquivos .py.
Formato (veja config_ia.exemplo.json):
    {"provedor": "groq", "chaves": {"groq": "..."}, "modelos": {"groq": "nome-do-modelo"}}
"""
import json
import os
from pathlib import Path

CAMINHO = Path(__file__).parent / "config_ia.json"


def _vazio():
    return {"provedor": "", "chaves": {}, "modelos": {}}


def normalizar(dados):
    """Aceita qualquer coisa (inclusive arquivo malformado) e devolve a estrutura completa."""
    base = _vazio()
    if not isinstance(dados, dict):
        return base
    if isinstance(dados.get("provedor"), str):
        base["provedor"] = dados["provedor"].strip().lower()
    for campo in ("chaves", "modelos"):
        origem = dados.get(campo)
        if isinstance(origem, dict):
            base[campo] = {
                str(k).lower(): v.strip() for k, v in origem.items() if isinstance(v, str) and v.strip()
            }
    return base


def carregar(caminho=None):
    caminho = Path(caminho) if caminho else CAMINHO
    try:
        with open(caminho, "r", encoding="utf-8-sig") as arquivo:  # tolera arquivo salvo pelo Bloco de Notas
            return normalizar(json.load(arquivo))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _vazio()


def salvar(dados, caminho=None):
    caminho = Path(caminho) if caminho else CAMINHO
    temporario = caminho.with_name(caminho.name + ".tmp")
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump(normalizar(dados), arquivo, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)  # troca atômica: nunca deixa o arquivo pela metade
    try:
        os.chmod(caminho, 0o600)  # só o dono lê (no Windows é ignorado)
    except OSError:
        pass


def limpar_chave(texto):
    """Valida a chave colada. Levanta ValueError com mensagem clara se estiver estranha."""
    chave = (texto or "").strip().strip("\"'")
    if len(chave) < 10 or any(c.isspace() for c in chave) or not chave.isprintable() or not chave.isascii():
        raise ValueError("Chave inválida. Confira se copiou ela inteira, sem espaços nem aspas.")
    return chave


def mascarar(chave):
    return "****" + chave[-4:] if chave and len(chave) > 8 else "****"


def definir_chave(provedor, chave, caminho=None):
    dados = carregar(caminho)
    dados["chaves"][provedor] = limpar_chave(chave)
    if not dados["provedor"]:
        dados["provedor"] = provedor  # primeira chave vira o provedor em uso
    salvar(dados, caminho)


def remover_chave(provedor, caminho=None):
    dados = carregar(caminho)
    dados["chaves"].pop(provedor, None)
    if dados["provedor"] == provedor:
        dados["provedor"] = next(iter(dados["chaves"]), "")
    salvar(dados, caminho)


def definir_modelo(provedor, modelo, caminho=None):
    dados = carregar(caminho)
    modelo = (modelo or "").strip()
    if modelo:
        dados["modelos"][provedor] = modelo
    else:
        dados["modelos"].pop(provedor, None)  # vazio = volta ao modelo padrão
    salvar(dados, caminho)


def definir_provedor(provedor, caminho=None):
    dados = carregar(caminho)
    dados["provedor"] = provedor
    salvar(dados, caminho)
