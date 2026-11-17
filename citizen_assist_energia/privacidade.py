"""Proteção de dados pessoais: detecta e oculta CPF, telefone, e-mail e similares.

Usado em dois momentos:
  1) contem_dados_pessoais: o assistente recusa a pergunta antes de responder ou enviar à IA.
  2) ocultar_dados_pessoais: rede de segurança, mascara o texto antes de gravar nos arquivos de registro.
"""
import re
import unicodedata

MARCA = "[removido]"

# 8 ou mais dígitos seguidos, aceitando até 2 separadores entre eles (espaço, ponto, hífen, barra, parênteses).
# Pega CPF, CNPJ, telefone e RG em qualquer pontuação. Decimais como 0,78938 não entram (vírgula não é separador).
SEQUENCIA_NUMERICA = re.compile(r"\d(?:[\s.\-/()]{0,2}\d){7,}")
EMAIL = re.compile(r"\S*@\S*")

# Palavra sensível + qualquer número no texto = bloqueia (ex.: "meu cpf é 12345").
PALAVRAS_SENSIVEIS = re.compile(r"\b(?:cpf|cnpj|rg|telefone|fone|celular|whatsapp|zap|senha|cartao)\b")
TEM_DIGITO = re.compile(r"\d")


def _normalizar(texto):
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return sem_acento


def _palavra_sensivel_com_numero(texto):
    return bool(PALAVRAS_SENSIVEIS.search(_normalizar(texto)) and TEM_DIGITO.search(texto))


def contem_dados_pessoais(texto):
    return bool(
        EMAIL.search(texto)
        or SEQUENCIA_NUMERICA.search(texto)
        or _palavra_sensivel_com_numero(texto)
    )


def ocultar_dados_pessoais(texto):
    """Devolve o texto com os dados pessoais trocados por [removido]."""
    if not texto:
        return texto
    saida = EMAIL.sub(MARCA, texto)
    saida = SEQUENCIA_NUMERICA.sub(MARCA, saida)
    if _palavra_sensivel_com_numero(saida):
        saida = re.sub(r"\d+", MARCA, saida)  # ex.: "cpf 12345" vira "cpf [removido]"
    return saida
