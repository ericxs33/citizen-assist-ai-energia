"""Carrega e valida as premissas (dados, origem, tipo e data de consulta)."""
import json
from pathlib import Path

CAMINHO = Path(__file__).parent / "data" / "premissas.json"

OBRIGATORIAS = (
    "potencia_chuveiro_w",
    "tarifa_rs_kwh",
    "fator_co2_kg_kwh",
    "fracao_solar",
    "investimento_solar_rs",
)


class PremissasInvalidas(Exception):
    """Premissas ausentes, não numéricas ou fora do intervalo esperado."""


def carregar(caminho=CAMINHO):
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError:
        raise PremissasInvalidas(f"Arquivo de premissas não encontrado: {caminho}")
    except json.JSONDecodeError as erro:
        raise PremissasInvalidas(f"JSON de premissas inválido: {erro}")

    problemas = []
    for nome in OBRIGATORIAS:
        item = dados.get(nome)
        if not isinstance(item, dict) or not isinstance(item.get("valor"), (int, float)):
            problemas.append(f"'{nome}' ausente ou sem valor numérico")
            continue
        for campo in ("tipo", "fonte", "consulta"):
            if not item.get(campo):
                problemas.append(f"'{nome}' sem '{campo}'")
        if item["valor"] <= 0:
            problemas.append(f"'{nome}' deve ser maior que zero")

    fracao = dados.get("fracao_solar", {}).get("valor")
    if isinstance(fracao, (int, float)) and not 0 < fracao <= 1:
        problemas.append("'fracao_solar' deve estar entre 0 e 1")

    if problemas:
        raise PremissasInvalidas("; ".join(problemas))

    return dados
