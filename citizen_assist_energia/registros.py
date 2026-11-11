"""Registro dos atendimentos e avaliações. Grava em modo ANEXAR, então nada é sobrescrito.

Evidência dos testes com usuários: data/atendimentos.csv (cada resposta) e
data/avaliacoes.csv (uma linha por sessão, com nota e comentário). Sem dados pessoais.
"""
import csv
import uuid
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).parent / "data"
ATENDIMENTOS = PASTA / "atendimentos.csv"
AVALIACOES = PASTA / "avaliacoes.csv"

CAMPOS_ATENDIMENTO = [
    "data", "sessao", "origem", "intencao", "pergunta", "pessoas",
    "min_atual", "min_meta", "usou_padrao", "ajudou",
]
CAMPOS_AVALIACAO = [
    "data", "sessao", "atendimentos", "taxa_ajudou_pct", "nota_facilidade", "comentario",
]


def _anexar(caminho, campos, linha):
    PASTA.mkdir(exist_ok=True)
    if caminho.exists():
        # Se o formato mudou (ex.: coluna nova), guarda o arquivo antigo em vez de misturar colunas
        with open(caminho, "r", encoding="utf-8-sig") as arquivo:
            cabecalho = arquivo.readline().strip().split(",")
        if cabecalho != campos:
            caminho.rename(caminho.with_name(f"{caminho.stem}_antigo_{datetime.now():%Y%m%d%H%M%S}.csv"))
    novo = not caminho.exists()
    # utf-8-sig só na criação do arquivo, para o Excel abrir os acentos corretamente
    with open(caminho, "a", encoding="utf-8-sig" if novo else "utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)


class Sessao:
    def __init__(self):
        self.id = uuid.uuid4().hex[:8]
        self.atendimentos = 0
        self.ajudou = 0

    def registrar_atendimento(self, resposta, ajudou):
        self.atendimentos += 1
        self.ajudou += 1 if ajudou else 0
        parametros = resposta.parametros
        _anexar(ATENDIMENTOS, CAMPOS_ATENDIMENTO, {
            "data": datetime.now().isoformat(timespec="seconds"),
            "sessao": self.id,
            "origem": resposta.origem,
            "intencao": resposta.intencao,
            "pergunta": resposta.pergunta,
            "pessoas": parametros.get("pessoas", ""),
            "min_atual": parametros.get("min_atual", ""),
            "min_meta": parametros.get("min_meta", ""),
            "usou_padrao": resposta.usou_padrao,
            "ajudou": ajudou,
        })

    @property
    def taxa_ajudou(self):
        return 100 * self.ajudou / self.atendimentos if self.atendimentos else 0.0

    def registrar_avaliacao(self, nota, comentario):
        _anexar(AVALIACOES, CAMPOS_AVALIACAO, {
            "data": datetime.now().isoformat(timespec="seconds"),
            "sessao": self.id,
            "atendimentos": self.atendimentos,
            "taxa_ajudou_pct": round(self.taxa_ajudou, 1),
            "nota_facilidade": nota if nota is not None else "",
            "comentario": comentario,
        })
