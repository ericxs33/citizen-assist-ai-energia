"""Cálculos de energia do Citizen Assist AI (funções puras, sem entrada/saída).

Necessidade: energia gasta no aquecimento de água do banho (chuveiro elétrico).
Alternativas comparadas para a MESMA necessidade e o MESMO período:
  atual      -> chuveiro elétrico como é hoje
  curto      -> banho mais curto (eficiência, sem investimento)
  solar      -> aquecedor solar (fonte renovável)
  combinado  -> banho mais curto + aquecedor solar
"""
from dataclasses import dataclass
from typing import Dict, Optional

DIAS_MES = 30
MESES_ANO = 12


@dataclass(frozen=True)
class Parametros:
    potencia_w: float
    tarifa_rs_kwh: float
    fator_co2_kg_kwh: float
    fracao_solar: float
    investimento_solar_rs: float

    @classmethod
    def de_premissas(cls, premissas, tarifa=None, potencia_w=None):
        """Monta os parâmetros; tarifa e potência podem ser trocadas pelos dados reais do usuário."""
        return cls(
            potencia_w=potencia_w if potencia_w is not None else premissas["potencia_chuveiro_w"]["valor"],
            tarifa_rs_kwh=tarifa if tarifa is not None else premissas["tarifa_rs_kwh"]["valor"],
            fator_co2_kg_kwh=premissas["fator_co2_kg_kwh"]["valor"],
            fracao_solar=premissas["fracao_solar"]["valor"],
            investimento_solar_rs=premissas["investimento_solar_rs"]["valor"],
        )


@dataclass(frozen=True)
class Cenario:
    chave: str
    nome: str
    kwh_mes: float
    custo_mes: float
    co2_kg_mes: float
    investimento: float
    custo_acumulado: float  # investimento + custo de energia ao longo do horizonte


@dataclass(frozen=True)
class Resultado:
    cenarios: Dict[str, Cenario]
    pessoas: int
    min_atual: int
    min_meta: int
    horizonte_anos: int
    payback_solar_anos: Optional[float]
    payback_solar_apos_banho_curto_anos: Optional[float]


def energia_kwh(potencia_w, minutos_por_pessoa_dia, pessoas, dias=DIAS_MES):
    """E (kWh) = P (kW) x t (h), somando todas as pessoas e dias."""
    return (potencia_w / 1000) * (minutos_por_pessoa_dia / 60) * pessoas * dias


def payback_anos(investimento, economia_mensal):
    """Anos para o investimento se pagar; None se não houver economia."""
    if economia_mensal <= 0:
        return None
    return investimento / (economia_mensal * MESES_ANO)


def comparar(p, pessoas, min_atual, min_meta, horizonte_anos=10):
    """Compara as quatro situações para 30 dias e acumula o custo no horizonte."""
    min_meta = min(min_meta, min_atual)

    kwh_atual = energia_kwh(p.potencia_w, min_atual, pessoas)
    kwh_curto = energia_kwh(p.potencia_w, min_meta, pessoas)
    kwh_solar = kwh_atual * (1 - p.fracao_solar)
    kwh_combinado = kwh_curto * (1 - p.fracao_solar)

    definicoes = (
        ("atual", "Chuveiro elétrico (atual)", kwh_atual, 0.0),
        ("curto", "Banho mais curto", kwh_curto, 0.0),
        ("solar", "Aquecedor solar", kwh_solar, p.investimento_solar_rs),
        ("combinado", "Banho curto + solar", kwh_combinado, p.investimento_solar_rs),
    )

    cenarios = {}
    for chave, nome, kwh, investimento in definicoes:
        custo_mes = kwh * p.tarifa_rs_kwh
        cenarios[chave] = Cenario(
            chave=chave,
            nome=nome,
            kwh_mes=kwh,
            custo_mes=custo_mes,
            co2_kg_mes=kwh * p.fator_co2_kg_kwh,
            investimento=investimento,
            custo_acumulado=investimento + custo_mes * MESES_ANO * horizonte_anos,
        )

    return Resultado(
        cenarios=cenarios,
        pessoas=pessoas,
        min_atual=min_atual,
        min_meta=min_meta,
        horizonte_anos=horizonte_anos,
        payback_solar_anos=payback_anos(
            p.investimento_solar_rs, cenarios["atual"].custo_mes - cenarios["solar"].custo_mes
        ),
        payback_solar_apos_banho_curto_anos=payback_anos(
            p.investimento_solar_rs, cenarios["curto"].custo_mes - cenarios["combinado"].custo_mes
        ),
    )
