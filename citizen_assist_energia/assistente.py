"""Assistente de energia do Citizen Assist AI.

Entende texto livre (ex.: "somos 3 pessoas, banho de 15 min, vale a pena o solar?"),
extrai os dados do usuário e monta a resposta a partir dos CÁLCULOS, nunca de texto fixo.
"""
import re
import unicodedata
from dataclasses import dataclass, field

import calculos
from calculos import Parametros

PADRAO_PESSOAS = 4
PADRAO_MINUTOS = 10
HORIZONTE_ANOS = 10

LIMITES = {
    "pessoas": (1, 20),
    "min_atual": (1, 60),
    "min_meta": (1, 60),
    "tarifa": (0.1, 5.0),
    "potencia_w": (500, 10000),
}

# Ordem importa: em caso de empate vence a primeira intenção da lista.
INTENCOES = {
    "comparar": ["comparar", "comparacao", "melhor", "alternativa", "vale a pena", "compensa",
                 "payback", "retorno", "se paga"],
    "solar": ["solar", "aquecedor", "placa", "renovavel", "boiler", "coletor"],
    "reduzir": ["reduzir", "diminuir", "economizar", "economia", "banho curto", "banho mais curto",
                "menos tempo", "tempo de banho", "encurtar"],
    "custo": ["custo", "custa", "conta de luz", "reais", "tarifa", "pagar", "gasto em reais"],
    "consumo": ["consumo", "consome", "kwh", "gasta", "potencia", "energia do banho"],
    "co2": ["co2", "carbono", "ambiental", "emissao", "emissoes", "meio ambiente", "sustentavel"],
    "fontes": ["fonte", "fontes", "referencia", "referencias", "garantido", "limitacao",
               "limitacoes", "confiavel", "premissa", "premissas", "de onde"],
    "ajuda": ["ajuda", "help", "o que voce faz", "como funciona o assistente", "comandos", "exemplos"],
}

# Frases que indicam pergunta de decisão (valem mais que uma palavra solta como "solar").
FRASES_FORTES = {"vale a pena", "compensa", "payback", "retorno", "se paga"}

LIMITACOES = (
    "Estimativas, não resultados garantidos. O consumo real varia com o modelo do chuveiro, a "
    "temperatura da água e os hábitos da casa. O aquecedor solar depende de insolação, instalação "
    "adequada e, em dias nublados, de apoio elétrico. A tarifa padrão não inclui impostos "
    "(informe a da sua conta para um valor mais fiel)."
)


@dataclass
class Resposta:
    texto: str
    intencao: str
    pergunta: str = ""
    encontrou: bool = True
    avaliavel: bool = True      # pergunta "ajudou?" ao usuário
    origem: str = "regras"      # "regras" (cálculos do projeto) ou "ia" (modelo de linguagem)
    usou_padrao: bool = False
    parametros: dict = field(default_factory=dict)


def fmt(valor, casas=2):
    """Formata número no padrão brasileiro (1.234,56)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "#").replace(".", ",").replace("#", ".")


def fmt_valor(valor):
    """Número no padrão brasileiro, sem zeros sobrando (5.500 | 0,78938 | 0,7)."""
    texto = fmt(valor, 5)
    return texto.rstrip("0").rstrip(",") if "," in texto else texto


def normalizar(texto):
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^\w\s.,$%-]", " ", sem_acento).split())


def contem_dados_pessoais(texto):
    if "@" in texto:
        return True
    cpf = r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"
    telefone = r"(?<!\d)\(?\d{2}\)?[\s-]?9?\d{4}-?\d{4}(?!\d)"
    return bool(re.search(cpf, texto) or re.search(telefone, texto) or re.search(r"\d{8,}", texto))


def extrair_parametros(t):
    """Lê números do texto normalizado. Retorna (valores, avisos)."""
    ex = {}

    m = re.search(r"(\d+)\s*(?:pessoas?|moradores?)", t) or re.search(r"somos\s*(\d+)", t)
    if m:
        ex["pessoas"] = int(m.group(1))

    ocorrencias = [(m.start(1), int(m.group(1))) for m in re.finditer(r"(\d+)\s*(?:min\b|minutos?)", t)]
    meta = re.search(r"(?:para|ate|meta(?: de)?)\s*(\d+)\s*(?:min\b|minutos?)", t)
    if meta:
        ex["min_meta"] = int(meta.group(1))
        outras = [v for pos, v in ocorrencias if pos != meta.start(1)]
        if outras:
            ex["min_atual"] = outras[0]
    elif ocorrencias:
        ex["min_atual"] = ocorrencias[0][1]
        if len(ocorrencias) > 1:
            ex["min_meta"] = ocorrencias[1][1]

    m = re.search(r"tarifa[^\d]{0,15}(\d+(?:[.,]\d+)?)", t)
    if m:
        ex["tarifa"] = float(m.group(1).replace(",", "."))

    m = re.search(r"(\d{3,5})\s*w\b", t)
    if m:
        ex["potencia_w"] = int(m.group(1))

    avisos = []
    for chave in list(ex):
        minimo, maximo = LIMITES[chave]
        if not minimo <= ex[chave] <= maximo:
            avisos.append(f"Ignorei {chave.replace('_', ' ')} = {ex[chave]:g} (fora do intervalo {minimo:g} a {maximo:g}).")
            del ex[chave]
    return ex, avisos


def identificar_intencao(t):
    melhor, melhor_pontos = None, 0
    for intencao, palavras in INTENCOES.items():
        pontos = sum(3 if palavra in FRASES_FORTES else 1 for palavra in palavras if palavra in t)
        if pontos > melhor_pontos:
            melhor, melhor_pontos = intencao, pontos
    return melhor


class Assistente:
    def __init__(self, premissas):
        self.premissas = premissas
        self.contexto = {}  # dados informados pelo usuário e lembrados na conversa

    # ---------- entrada ----------
    def responder(self, texto):
        if contem_dados_pessoais(texto):
            return Resposta(
                "Atenção: não digite CPF, telefone ou e-mail. Reescreva sem esses dados.",
                "bloqueado", pergunta="", encontrou=False, avaliavel=False,
            )

        t = normalizar(texto)
        extraidos, avisos = extrair_parametros(t)
        intencao = identificar_intencao(t)
        if intencao is None and extraidos:
            intencao = "comparar"
        if intencao is None:
            return Resposta(self._nao_entendi(), "nao_encontrou", pergunta=texto,
                            encontrou=False, avaliavel=False)

        self._atualizar_contexto(extraidos)
        if intencao in ("ajuda", "fontes"):
            corpo = self._ajuda() if intencao == "ajuda" else self._fontes()
            return Resposta(corpo, intencao, pergunta=texto, avaliavel=intencao == "fontes")

        pessoas, atual, meta, usou_padrao = self._dados_do_banho()
        p = Parametros.de_premissas(
            self.premissas, tarifa=self.contexto.get("tarifa"), potencia_w=self.contexto.get("potencia_w")
        )
        res = calculos.comparar(p, pessoas, atual, meta, HORIZONTE_ANOS)

        construtores = {
            "consumo": self._consumo, "custo": self._custo, "reduzir": self._reduzir,
            "solar": self._solar, "comparar": self._comparar, "co2": self._co2,
        }
        partes = [*avisos, construtores[intencao](res, p)]
        if usou_padrao:
            partes.append(
                f"(Usei {PADRAO_PESSOAS} pessoas e {PADRAO_MINUTOS} min por banho como exemplo. "
                "Informe os seus, ex.: 'somos 3 pessoas, banho de 15 min'.)"
            )
        partes.append(self._rodape(p))

        return Resposta(
            "\n\n".join(partes), intencao, pergunta=texto, usou_padrao=usou_padrao,
            parametros={"pessoas": res.pessoas, "min_atual": res.min_atual, "min_meta": res.min_meta},
        )

    # ---------- dados do usuário ----------
    def resumo_dados(self):
        """Dados que estão valendo agora, como lista de (rótulo, texto), indicando a origem."""
        ctx = self.contexto
        pessoas, atual, meta, _ = self._dados_do_banho()
        p = Parametros.de_premissas(self.premissas, tarifa=ctx.get("tarifa"), potencia_w=ctx.get("potencia_w"))
        return [
            ("Pessoas", f"{pessoas}" + ("" if "pessoas" in ctx else " (exemplo)")),
            ("Minutos por banho", f"{atual} min" + ("" if "min_atual" in ctx else " (exemplo)")),
            ("Meta de banho", f"{meta} min" + ("" if "min_meta" in ctx else " (metade, automática)")),
            ("Tarifa", f"R$ {fmt(p.tarifa_rs_kwh, 5)}/kWh" + (" (sua)" if "tarifa" in ctx else " (ANEEL, sem impostos)")),
            ("Chuveiro", f"{fmt(p.potencia_w, 0)} W" + (" (seu)" if "potencia_w" in ctx else " (estimado)")),
        ]

    def parametros_atuais(self):
        pessoas, atual, meta, _ = self._dados_do_banho()
        return {"pessoas": pessoas, "min_atual": atual, "min_meta": meta}

    def contexto_para_ia(self):
        """Texto com as premissas e os cálculos do projeto, para a IA responder SEM inventar números."""
        pessoas, atual, meta, _ = self._dados_do_banho()
        ctx = self.contexto
        p = Parametros.de_premissas(self.premissas, tarifa=ctx.get("tarifa"), potencia_w=ctx.get("potencia_w"))
        res = calculos.comparar(p, pessoas, atual, meta, HORIZONTE_ANOS)

        linhas = ["PREMISSAS DO PROJETO (valor, tipo, fonte, data de consulta):"]
        for item in self.premissas.values():
            linhas.append(
                f"- {item['descricao']}: {fmt_valor(item['valor'])} {item['unidade']} "
                f"[{item['tipo']}] fonte: {item['fonte']} (consulta {item['consulta']})"
            )
        linhas.append("")
        linhas.append("DADOS EM USO PARA O USUÁRIO:")
        for rotulo, valor in self.resumo_dados():
            linhas.append(f"- {rotulo}: {valor}")
        linhas.append("")
        linhas.append(f"CÁLCULOS DO PROJETO (30 dias; custo acumulado em {HORIZONTE_ANOS} anos inclui investimento):")
        for c in res.cenarios.values():
            linhas.append(
                f"- {c.nome}: {fmt(c.kwh_mes, 1)} kWh/mês, R$ {fmt(c.custo_mes)}/mês, "
                f"{fmt(c.co2_kg_mes)} kg CO2/mês, custo acumulado R$ {fmt(c.custo_acumulado, 0)}"
            )
        if res.payback_solar_anos:
            linhas.append(f"- Payback do aquecedor solar: {fmt(res.payback_solar_anos, 1)} anos")
        if res.payback_solar_apos_banho_curto_anos:
            linhas.append(
                f"- Payback do solar para quem já encurtou o banho: {fmt(res.payback_solar_apos_banho_curto_anos, 1)} anos"
            )
        linhas.append(f"LIMITAÇÕES: {LIMITACOES}")
        return "\n".join(linhas)

    def reiniciar_dados(self):
        """Esquece os dados informados pelo usuário e volta aos valores de exemplo."""
        self.contexto.clear()

    # ---------- contexto ----------
    def _atualizar_contexto(self, extraidos):
        if "min_atual" in extraidos and "min_meta" not in extraidos:
            self.contexto.pop("min_meta", None)  # a meta antiga não vale mais
        self.contexto.update(extraidos)

    def _dados_do_banho(self):
        pessoas = self.contexto.get("pessoas", PADRAO_PESSOAS)
        atual = self.contexto.get("min_atual", PADRAO_MINUTOS)
        meta = min(self.contexto.get("min_meta", max(1, atual // 2)), atual)
        usou_padrao = "pessoas" not in self.contexto or "min_atual" not in self.contexto
        return pessoas, atual, meta, usou_padrao

    # ---------- respostas ----------
    def _consumo(self, res, p):
        c = res.cenarios["atual"]
        return (
            f"O consumo é energia = potência × tempo. Chuveiro de {fmt(p.potencia_w, 0)} W, "
            f"{res.pessoas} pessoa(s), {res.min_atual} min por banho, 30 dias:\n"
            f"{fmt(p.potencia_w / 1000, 2)} kW × {fmt(res.min_atual / 60, 2)} h × {res.pessoas} × 30 "
            f"= {fmt(c.kwh_mes, 1)} kWh por mês."
        )

    def _custo(self, res, p):
        c = res.cenarios["atual"]
        return (
            f"Custo = kWh × tarifa. Com {fmt(c.kwh_mes, 1)} kWh por mês e tarifa de "
            f"R$ {fmt(p.tarifa_rs_kwh, 5)}/kWh, o banho custa cerca de R$ {fmt(c.custo_mes)} por mês "
            f"(R$ {fmt(c.custo_mes * 12)} por ano)."
        )

    def _reduzir(self, res, p):
        a, c = res.cenarios["atual"], res.cenarios["curto"]
        return (
            f"O consumo é proporcional ao tempo. Passando de {res.min_atual} para {res.min_meta} min "
            f"por banho: {fmt(a.kwh_mes, 1)} → {fmt(c.kwh_mes, 1)} kWh por mês e "
            f"R$ {fmt(a.custo_mes)} → R$ {fmt(c.custo_mes)}. Economia de R$ {fmt(a.custo_mes - c.custo_mes)} "
            "por mês, sem investimento."
        )

    def _solar(self, res, p):
        a, s = res.cenarios["atual"], res.cenarios["solar"]
        retorno = (
            f"retorno estimado em {fmt(res.payback_solar_anos, 1)} anos"
            if res.payback_solar_anos else "sem retorno com esses dados"
        )
        return (
            "O aquecedor solar esquenta a água com coletores no telhado e a guarda em um reservatório. "
            f"Na estimativa, ele cobre {fmt(p.fracao_solar * 100, 0)}% da energia do banho; o restante "
            "vem do apoio elétrico em dias nublados.\n"
            f"Para {res.pessoas} pessoa(s) e {res.min_atual} min: {fmt(a.kwh_mes, 1)} → {fmt(s.kwh_mes, 1)} kWh "
            f"por mês, R$ {fmt(a.custo_mes)} → R$ {fmt(s.custo_mes)} (economia de "
            f"R$ {fmt(a.custo_mes - s.custo_mes)} por mês). Investimento estimado: "
            f"R$ {fmt(p.investimento_solar_rs, 0)}; {retorno}."
        )

    def _comparar(self, res, p):
        linhas = [
            f"Comparação para {res.pessoas} pessoa(s), banho de {res.min_atual} min (meta: {res.min_meta} min), "
            f"30 dias, custo acumulado em {res.horizonte_anos} anos:",
            "",
            f"{'Alternativa':<27}{'kWh/mês':>9}{'R$/mês':>9}{'kg CO2':>8}{'R$ acumulado':>14}",
        ]
        for c in res.cenarios.values():
            linhas.append(
                f"{c.nome:<27}{fmt(c.kwh_mes, 1):>9}{fmt(c.custo_mes):>9}"
                f"{fmt(c.co2_kg_mes):>8}{fmt(c.custo_acumulado, 0):>14}"
            )
        linhas += ["", self._recomendacao(res, p)]
        return "\n".join(linhas)

    def _co2(self, res, p):
        a, s = res.cenarios["atual"], res.cenarios["combinado"]
        return (
            f"Com o fator de emissão da rede ({fmt(p.fator_co2_kg_kwh * 1000, 1)} kg CO2/MWh em 2023), "
            f"{res.pessoas} pessoa(s) com {res.min_atual} min emitem cerca de {fmt(a.co2_kg_mes)} kg de CO2 "
            f"por mês; com banho curto + solar, {fmt(s.co2_kg_mes)} kg. Como a matriz elétrica brasileira já é "
            "bastante renovável, o CO2 evitado é pequeno em kg; o ganho mais claro é a economia na conta."
        )

    def _recomendacao(self, res, p):
        melhor = min(res.cenarios.values(), key=lambda c: c.custo_acumulado)
        h = res.horizonte_anos
        if melhor.chave == "curto":
            texto = (f"Em {h} anos, o banho mais curto tem o menor custo total e não exige investimento. "
                     "É a primeira medida a adotar.")
        elif melhor.chave == "atual":
            texto = f"Em {h} anos, nenhuma alternativa compensa com esses dados."
        else:
            texto = (f"Em {h} anos, '{melhor.nome}' tem o menor custo total, mesmo com investimento de "
                     f"R$ {fmt(p.investimento_solar_rs, 0)}.")
        if res.payback_solar_anos:
            texto += f" O aquecedor solar se paga em cerca de {fmt(res.payback_solar_anos, 1)} anos"
            if res.payback_solar_anos > h:
                texto += f", mais que o horizonte de {h} anos"
            texto += "."
        if res.payback_solar_apos_banho_curto_anos:
            texto += (f" Se você já encurtar o banho, o solar demora mais: "
                      f"{fmt(res.payback_solar_apos_banho_curto_anos, 1)} anos.")
        return "Recomendação: " + texto

    def _rodape(self, p):
        tarifa_origem = "informada por você" if "tarifa" in self.contexto else "ANEEL, sem impostos"
        potencia_origem = "informada por você" if "potencia_w" in self.contexto else "estimada"
        return (
            f"Premissas: chuveiro {fmt(p.potencia_w, 0)} W ({potencia_origem}), tarifa "
            f"R$ {fmt(p.tarifa_rs_kwh, 5)}/kWh ({tarifa_origem}). Digite 'fontes' para ver as referências.\n"
            f"Limitações: {LIMITACOES}"
        )

    def _fontes(self):
        linhas = ["Dados usados e de onde vêm:"]
        for item in self.premissas.values():
            linhas.append(
                f"- {item['descricao']}: {fmt_valor(item['valor'])} {item['unidade']} [{item['tipo']}]\n"
                f"  Fonte: {item['fonte']} (consulta: {item['consulta']})"
            )
        linhas += ["", f"Limitações: {LIMITACOES}"]
        return "\n".join(linhas)

    def _ajuda(self):
        return (
            "Eu ajudo a entender e reduzir o gasto de energia do chuveiro elétrico. Pergunte, por exemplo:\n"
            "- quanto o chuveiro consome?\n"
            "- quanto custa o banho na conta de luz?\n"
            "- como economizar reduzindo o banho de 15 para 8 min?\n"
            "- o aquecedor solar vale a pena?\n"
            "- compare as alternativas\n"
            "Se eu não souber responder (ou se a resposta não ajudar), a IA de apoio pode assumir, quando ativada.\n"
            "Você pode informar seus dados: 'somos 3 pessoas, banho de 15 min, tarifa 0,95, chuveiro de 4500 W'.\n"
            "Comandos: 'fontes' (referências), 'ajuda' e 'sair'."
        )

    def _nao_entendi(self):
        return (
            "Não entendi a pergunta. Tente falar de consumo, custo, banho mais curto, aquecedor solar, "
            "comparação ou CO2. Digite 'ajuda' para ver exemplos."
        )
