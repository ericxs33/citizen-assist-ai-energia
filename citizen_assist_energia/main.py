"""Citizen Assist AI - Energia. Execute com:  python main.py"""
import getpass
import os
import sys
from pathlib import Path

# Permite rodar de qualquer pasta (ex.: python caminho\para\main.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_ia
import premissas as modulo_premissas
from assistente import Assistente, Resposta, contem_dados_pessoais
from ia import ConsultorIA, ErroIA, situacao_provedores
from registros import Sessao

LARGURA = 66
COMANDOS_SAIDA = {"sair", "0", "exit", "quit"}
AVISO_IA = (
    "[Resposta gerada por IA. Ela não passou pelos cálculos do assistente: "
    "confira os números e as fontes.]\n"
)

# Atalhos numéricos do menu -> pergunta enviada ao assistente
ATALHOS = {
    "1": "quanto o chuveiro consome?",
    "2": "quanto custa o banho na conta de luz?",
    "3": "como economizar reduzindo o tempo de banho?",
    "4": "como funciona o aquecedor solar?",
    "5": "compare as alternativas",
    "6": "qual o impacto ambiental?",
    "7": "fontes",
    "8": "ajuda",
}

OPCOES_MENU = [
    ("1", "Consumo do chuveiro (kWh por mês)"),
    ("2", "Custo do banho na conta de luz"),
    ("3", "Economizar com banho mais curto"),
    ("4", "Aquecedor solar: como funciona e retorno"),
    ("5", "Comparar todas as alternativas"),
    ("6", "Impacto ambiental (CO2)"),
    ("7", "Fontes e premissas usadas"),
    ("8", "Ajuda com exemplos de perguntas"),
    ("9", "Zerar meus dados e voltar ao exemplo"),
    ("C", "Configurar a chave das IAs (Gemini, Groq...)"),
    ("0", "Sair e avaliar o assistente"),
]

# ---------------------------------------------------------------------------
# Terminal: cores, moldura e limpeza de tela
# ---------------------------------------------------------------------------
INTERATIVO = sys.stdout.isatty()
USAR_COR = INTERATIVO and not os.environ.get("NO_COLOR")


def _preparar_terminal():
    if os.name == "nt" and INTERATIVO:
        os.system("")  # habilita cores ANSI no PowerShell/CMD do Windows


def cor(texto, codigo):
    return f"\033[{codigo}m{texto}\033[0m" if USAR_COR else texto


def _moldura():
    try:
        "═║╔╗╚╝╠╣".encode(sys.stdout.encoding or "utf-8")
        return {"h": "═", "v": "║", "tl": "╔", "tr": "╗", "bl": "╚", "br": "╝", "ml": "╠", "mr": "╣"}
    except (UnicodeEncodeError, LookupError):
        return {"h": "=", "v": "|", "tl": "+", "tr": "+", "bl": "+", "br": "+", "ml": "+", "mr": "+"}


def limpar_tela():
    if not INTERATIVO:  # saída redirecionada: só separa visualmente
        print("\n" + "-" * LARGURA)
        return
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[3J\033[2J\033[H", end="", flush=True)


def mostrar_menu(assistente, ia, aviso=None):
    m = _moldura()
    interno = LARGURA - 2

    def linha(texto="", estilo=None):
        if len(texto) > interno - 2:  # nunca quebra a moldura
            texto = texto[: interno - 5] + "..."
        corpo = (" " + texto).ljust(interno)
        return m["v"] + (cor(corpo, estilo) if estilo else corpo) + m["v"]

    def divisoria():
        return m["ml"] + m["h"] * interno + m["mr"]

    print(m["tl"] + m["h"] * interno + m["tr"])
    print(linha("CITIZEN ASSIST AI  |  ENERGIA", "1;36"))
    print(linha("Orientações sobre o gasto de energia do chuveiro elétrico"))
    print(divisoria())
    print(linha("O QUE VOCÊ PODE FAZER", "1"))
    for numero, descricao in OPCOES_MENU:
        print(linha(f"[{numero}] {descricao}"))
    print(linha())
    print(linha("Ou digite sua pergunta livremente, por exemplo:"))
    print(linha("  o aquecedor solar vale a pena?"))
    print(linha("Digite 'menu' para ver esta tela de novo."))
    print(divisoria())
    print(linha("IA DE APOIO", "1"))
    if ia.disponivel:
        print(linha(f"ATIVADA: {ia.descricao}", "32"))
        print(linha("Assume se eu não souber responder ou se você marcar"))
        print(linha("que a resposta não ajudou."))
    else:
        print(linha("DESATIVADA. " + ia.motivo, "33"))
        print(linha("Sem ela, tudo funciona, só não há resposta de reserva."))
    print(divisoria())
    print(linha("SEUS DADOS (valem para todas as respostas)", "1"))
    for rotulo, valor in assistente.resumo_dados():
        print(linha(f"{rotulo + ':':<20}{valor}"))
    print(linha())
    print(linha("Para mudar, escreva na pergunta, por exemplo:"))
    print(linha("  somos 3 pessoas, banho de 15 min para 8 min,"))
    print(linha("  tarifa 0,95, chuveiro de 4500 W"))
    print(divisoria())
    print(linha("Não digite CPF, telefone ou e-mail.", "33"))
    print(m["bl"] + m["h"] * interno + m["br"])
    if aviso:
        print(cor(aviso, "32"))


# ---------------------------------------------------------------------------
# Entrada do usuário
# ---------------------------------------------------------------------------
def _ler(texto):
    """Lê uma linha; devolve None se o usuário encerrar (Ctrl+C / Ctrl+Z)."""
    try:
        return input(texto).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None


def _perguntar_sim_nao(texto):
    while True:
        resposta = _ler(texto)
        if resposta is None:
            return None
        resposta = resposta.lower()
        if resposta in ("s", "sim"):
            return True
        if resposta in ("n", "nao", "não"):
            return False
        print("Digite 's' ou 'n'.")


def _perguntar_nota():
    while True:
        resposta = _ler("De 1 a 5, quão fácil foi usar o assistente? (Enter para pular) ")
        if not resposta:
            return None
        if resposta.isdigit() and 1 <= int(resposta) <= 5:
            return int(resposta)
        print("Digite um número de 1 a 5.")


def finalizar(sessao):
    print("\n" + cor("=== Resumo da sessão ===", "1;36"))
    if sessao.atendimentos:
        print(f"Atendimentos avaliados: {sessao.atendimentos}")
        print(f"Respostas que ajudaram: {sessao.taxa_ajudou:.0f}%")
    else:
        print("Nenhum atendimento registrado.")

    nota = _perguntar_nota()
    comentario = _ler("Comentário sobre a experiência (opcional, sem dados pessoais): ") or ""
    if contem_dados_pessoais(comentario):
        print("Comentário descartado por conter dados pessoais.")
        comentario = ""

    sessao.registrar_avaliacao(nota, comentario)
    print(cor("Avaliação salva em data/avaliacoes.csv. Obrigado!", "32"))


# ---------------------------------------------------------------------------
# Configuração da IA (tecla C)
# ---------------------------------------------------------------------------
def _quadro(linhas):
    """Desenha uma caixa. Cada item é um texto, (texto, estilo) ou '---' (divisória)."""
    m = _moldura()
    interno = LARGURA - 2
    print(m["tl"] + m["h"] * interno + m["tr"])
    for item in linhas:
        if item == "---":
            print(m["ml"] + m["h"] * interno + m["mr"])
            continue
        texto, estilo = item if isinstance(item, tuple) else (item, None)
        if len(texto) > interno - 2:
            texto = texto[: interno - 5] + "..."
        corpo = (" " + texto).ljust(interno)
        print(m["v"] + (cor(corpo, estilo) if estilo else corpo) + m["v"])
    print(m["bl"] + m["h"] * interno + m["br"])


def _ler_chave():
    """Lê a chave sem mostrar na tela. Se o terminal não permitir, lê normalmente."""
    try:
        return getpass.getpass("Cole a chave (a digitação fica invisível) e aperte Enter: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    except Exception:
        return _ler("Cole a chave e aperte Enter: ")


def testar_conexao(nome):
    ia = ConsultorIA(provedor=nome)
    if not ia.disponivel:
        print(cor(f"Não dá para testar: {ia.motivo}", "33"))
        return
    print(cor(f"Testando {ia.descricao}...", "2"))
    try:
        resposta = ia.perguntar("Teste de conexão. Responda apenas: ok", "Sem contexto: é só um teste.")
    except ErroIA as erro:
        print(cor(f"Falhou: {erro}.", "31"))
        return
    print(cor("Conexão funcionando!", "32") + f" Resposta recebida: {resposta[:80]}")


def _menu_provedor(nome):
    """Ações de um provedor: colar chave, escolher modelo, usar, testar, remover."""
    aviso = None
    while True:
        limpar_tela()
        s = next(x for x in situacao_provedores() if x["nome"] == nome)
        chave = f"{s['chave_mascarada']} ({s['origem']})" if s["tem_chave"] else "não definida"
        _quadro([
            (f"PROVEDOR: {nome.upper()}", "1;36"),
            f"Chave:  {chave}",
            f"Modelo: {s['modelo'] or '(defina na opção 2)'}",
            f"Status: {'EM USO' if s['em_uso'] else 'não é o provedor em uso'}",
            "---",
            "[1] Colar ou atualizar a chave",
            "[2] Definir o modelo (Enter vazio = padrão)",
            "[3] Usar este provedor",
            "[4] Testar a conexão",
            "[5] Remover a chave salva",
            "[0] Voltar",
            "---",
            f"Conseguir uma chave: {s['site']}",
        ])
        if aviso:
            print(aviso)
            aviso = None

        opcao = _ler("\nEscolha: ")
        if opcao is None or opcao == "0":
            return
        if opcao == "1":
            texto = _ler_chave()
            if not texto:
                aviso = cor("Nenhuma chave informada.", "33")
                continue
            try:
                config_ia.definir_chave(nome, texto)
            except ValueError as erro:
                aviso = cor(str(erro), "31")
                continue
            print(cor(f"Chave salva em config_ia.json ({config_ia.mascarar(texto.strip())}).", "32"))
            if _perguntar_sim_nao("Testar a conexão agora? (s/n): "):
                testar_conexao(nome)
                _ler("Pressione Enter para continuar...")
        elif opcao == "2":
            modelo = _ler(f"Nome do modelo para {nome} (confira no site do provedor): ")
            if modelo is not None:
                config_ia.definir_modelo(nome, modelo)
                aviso = cor("Modelo atualizado." if modelo else "Voltei ao modelo padrão.", "32")
        elif opcao == "3":
            if not s["tem_chave"]:
                aviso = cor("Cole uma chave antes (opção 1).", "33")
            else:
                config_ia.definir_provedor(nome)
                aviso = cor(f"Agora o provedor em uso é {nome}.", "32")
        elif opcao == "4":
            testar_conexao(nome)
            _ler("Pressione Enter para continuar...")
        elif opcao == "5":
            if _perguntar_sim_nao(f"Remover a chave salva de {nome}? (s/n): "):
                config_ia.remover_chave(nome)
                aviso = cor("Chave removida.", "32")
        else:
            aviso = cor("Opção inválida.", "33")


def configurar_ia():
    """Tela para colar a chave de cada IA. As chaves ficam só neste computador."""
    aviso = None
    while True:
        limpar_tela()
        provedores = situacao_provedores()
        linhas = [("CONFIGURAR IA DE APOIO", "1;36"), "Escolha o provedor para configurar:", "---"]
        for i, s in enumerate(provedores, start=1):
            chave = f"{s['chave_mascarada']} ({s['origem']})" if s["tem_chave"] else "sem chave"
            linhas.append((f"[{i}] {s['nome']:<11}{chave}" + ("   << EM USO" if s["em_uso"] else ""),
                           "32" if s["em_uso"] else None))
            linhas.append(f"     modelo: {s['modelo'] or '(defina)'}")
        linhas += ["", "[0] Voltar ao menu", "---",
                   ("As chaves ficam em config_ia.json, só neste computador,", "33"),
                   ("fora do GitHub. Nunca cole chave em arquivos .py.", "33")]
        _quadro(linhas)
        if aviso:
            print(aviso)
            aviso = None

        opcao = _ler("\nEscolha o provedor (0 para voltar): ")
        if opcao is None or opcao == "0":
            return
        if opcao.isdigit() and 1 <= int(opcao) <= len(provedores):
            _menu_provedor(provedores[int(opcao) - 1]["nome"])
        else:
            aviso = cor("Opção inválida.", "33")


# ---------------------------------------------------------------------------
# IA de apoio
# ---------------------------------------------------------------------------
def consultar_ia(ia, assistente, pergunta, resposta_anterior=None):
    """Pede a resposta à IA e a mostra. Devolve uma Resposta ou None se a IA falhar."""
    print(cor("\nConsultando a IA de apoio...", "2"))
    try:
        texto = ia.perguntar(pergunta, assistente.contexto_para_ia(), resposta_anterior)
    except ErroIA as erro:
        print(f"Não consegui consultar a IA ({erro}).")
        return None

    resposta = Resposta(
        texto=AVISO_IA + texto, intencao="ia", pergunta=pergunta, origem="ia",
        parametros=assistente.parametros_atuais(),
    )
    print("\n" + cor("Assistente (IA):", "1;35") + f" {resposta.texto}")
    return resposta


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------
def main():
    try:
        premissas = modulo_premissas.carregar()
    except modulo_premissas.PremissasInvalidas as erro:
        print(f"Não foi possível iniciar: {erro}")
        return

    _preparar_terminal()
    assistente = Assistente(premissas)
    ia = ConsultorIA()
    sessao = Sessao()

    limpar_tela()
    mostrar_menu(assistente, ia)

    while True:
        entrada = _ler("\nDigite uma opção (0-9, C) ou sua pergunta: ")
        if entrada is None or entrada.lower() in COMANDOS_SAIDA:
            break
        if not entrada:
            continue

        comando = entrada.lower()
        if comando == "menu":
            limpar_tela()
            mostrar_menu(assistente, ia)
            continue
        if comando in ("c", "config", "configurar"):
            configurar_ia()
            ia = ConsultorIA()  # recarrega com a configuração nova
            limpar_tela()
            mostrar_menu(assistente, ia, aviso="Configuração da IA atualizada.")
            continue
        if comando == "9":
            assistente.reiniciar_dados()
            limpar_tela()
            mostrar_menu(assistente, ia, aviso="Seus dados foram zerados. Voltei aos valores de exemplo.")
            continue

        pergunta = ATALHOS.get(comando, entrada)
        if pergunta != entrada:
            print(cor(f"Você escolheu: {pergunta}", "2"))

        try:
            resposta = assistente.responder(pergunta)
        except Exception as erro:  # o assistente nunca deve derrubar a conversa
            print(f"\nAssistente: ocorreu um erro inesperado ({erro}). Tente reformular.")
            continue

        print("\n" + cor("Assistente:", "1;36") + f" {resposta.texto}")

        # 1) Não soube responder: registra a falha e a IA assume
        if resposta.intencao == "nao_encontrou":
            sessao.registrar_atendimento(resposta, False)
            if ia.disponivel:
                resposta = consultar_ia(ia, assistente, pergunta)
            if resposta is None or resposta.origem != "ia":
                if not ia.disponivel:
                    print(cor("(A IA de apoio está desativada. Veja o menu para ativar.)", "2"))
                continue

        if not resposta.avaliavel:
            continue

        # 2) Pergunta se ajudou; se não ajudou, a IA tenta responder melhor
        ajudou = _perguntar_sim_nao("\nEssa resposta ajudou? (s/n): ")
        if ajudou is None:
            break
        sessao.registrar_atendimento(resposta, ajudou)

        if not ajudou and resposta.origem == "regras" and ia.disponivel:
            quer = _perguntar_sim_nao("Quer que a IA de apoio tente responder melhor? (s/n): ")
            if quer is None:
                break
            if quer:
                nova = consultar_ia(ia, assistente, pergunta, resposta_anterior=resposta.texto)
                if nova:
                    ajudou = _perguntar_sim_nao("\nA resposta da IA ajudou? (s/n): ")
                    if ajudou is None:
                        break
                    sessao.registrar_atendimento(nova, ajudou)

        limpar_tela()
        mostrar_menu(
            assistente, ia,
            aviso="Resposta registrada como " + ("útil." if ajudou else "não útil.")
            + " Pode fazer outra pergunta.",
        )

    finalizar(sessao)


if __name__ == "__main__":
    main()
