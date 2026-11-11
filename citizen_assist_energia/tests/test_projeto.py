"""Rode na pasta do projeto:  python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import calculos
import config_ia
import premissas
from ia import ConsultorIA, ErroIA, situacao_provedores
from assistente import (Assistente, contem_dados_pessoais, extrair_parametros,
                        identificar_intencao, normalizar)


class TestCalculos(unittest.TestCase):
    def setUp(self):
        self.p = calculos.Parametros(
            potencia_w=5500, tarifa_rs_kwh=0.78938, fator_co2_kg_kwh=0.0385,
            fracao_solar=0.70, investimento_solar_rs=7000,
        )

    def test_energia(self):
        self.assertAlmostEqual(calculos.energia_kwh(5500, 10, 4), 110.0)
        self.assertAlmostEqual(calculos.energia_kwh(5500, 10, 1), 27.5)

    def test_comparacao(self):
        r = calculos.comparar(self.p, 4, 10, 5)
        c = r.cenarios
        self.assertAlmostEqual(c["atual"].kwh_mes, 110.0)
        self.assertAlmostEqual(c["curto"].kwh_mes, 55.0)
        self.assertAlmostEqual(c["solar"].kwh_mes, 33.0)
        self.assertAlmostEqual(c["combinado"].kwh_mes, 16.5)
        self.assertAlmostEqual(c["atual"].custo_mes, 110 * 0.78938)
        self.assertAlmostEqual(c["atual"].co2_kg_mes, 110 * 0.0385)
        self.assertAlmostEqual(r.payback_solar_anos, 9.6, places=1)  # 7000 / (60,78 x 12)

    def test_custo_acumulado_inclui_investimento(self):
        r = calculos.comparar(self.p, 4, 10, 5, horizonte_anos=10)
        solar = r.cenarios["solar"]
        self.assertAlmostEqual(solar.custo_acumulado, 7000 + solar.custo_mes * 120)
        self.assertAlmostEqual(r.cenarios["curto"].custo_acumulado, r.cenarios["curto"].custo_mes * 120)

    def test_meta_maior_que_atual_e_limitada(self):
        r = calculos.comparar(self.p, 2, 8, 20)
        self.assertEqual(r.min_meta, 8)

    def test_payback_sem_economia(self):
        self.assertIsNone(calculos.payback_anos(7000, 0))


class TestPremissas(unittest.TestCase):
    def test_carrega_e_tem_fonte(self):
        dados = premissas.carregar()
        for nome in premissas.OBRIGATORIAS:
            self.assertIn(dados[nome]["tipo"], ("real", "estimado"))
            self.assertTrue(dados[nome]["fonte"])
            self.assertTrue(dados[nome]["consulta"])

    def test_arquivo_inexistente(self):
        with self.assertRaises(premissas.PremissasInvalidas):
            premissas.carregar(Path("nao_existe.json"))


class TestAssistente(unittest.TestCase):
    def setUp(self):
        self.a = Assistente(premissas.carregar())

    def test_normalizar(self):
        self.assertEqual(normalizar("Quanto CUSTA o Banho?"), "quanto custa o banho")

    def test_extrair_parametros(self):
        ex, avisos = extrair_parametros(normalizar("Somos 3 pessoas, banho de 15 min para 8 min, tarifa 0,95, chuveiro de 4500 W"))
        self.assertEqual(ex["pessoas"], 3)
        self.assertEqual(ex["min_atual"], 15)
        self.assertEqual(ex["min_meta"], 8)
        self.assertAlmostEqual(ex["tarifa"], 0.95)
        self.assertEqual(ex["potencia_w"], 4500)
        self.assertEqual(avisos, [])

    def test_valor_fora_do_intervalo_e_ignorado(self):
        ex, avisos = extrair_parametros(normalizar("100 pessoas"))
        self.assertNotIn("pessoas", ex)
        self.assertEqual(len(avisos), 1)

    def test_intencoes(self):
        casos = {
            "quanto o chuveiro consome": "consumo",
            "quanto custa o banho": "custo",
            "como economizar reduzindo o banho": "reduzir",
            "o aquecedor solar vale a pena": "comparar",
            "como funciona o aquecedor solar": "solar",
            "qual o impacto ambiental": "co2",
            "quais as fontes": "fontes",
        }
        for pergunta, esperado in casos.items():
            self.assertEqual(identificar_intencao(normalizar(pergunta)), esperado, pergunta)

    def test_dados_pessoais(self):
        self.assertTrue(contem_dados_pessoais("meu email é a@b.com"))
        self.assertTrue(contem_dados_pessoais("meu cpf 123.456.789-10"))
        self.assertTrue(contem_dados_pessoais("liga (11) 91234-5678"))
        self.assertFalse(contem_dados_pessoais("somos 4 pessoas, 10 min, tarifa 0,78938"))

    def test_resposta_usa_calculo(self):
        r = self.a.responder("quanto consome com 4 pessoas e banho de 10 min?")
        self.assertIn("110,0 kWh", r.texto)
        self.assertEqual(r.intencao, "consumo")
        self.assertFalse(r.usou_padrao)

    def test_contexto_e_lembrado(self):
        self.a.responder("somos 2 pessoas e banho de 20 min, quanto consome?")
        r = self.a.responder("quanto custa?")
        self.assertEqual(r.parametros["pessoas"], 2)
        self.assertEqual(r.parametros["min_atual"], 20)

    def test_padrao_e_avisado(self):
        r = self.a.responder("quanto consome o chuveiro?")
        self.assertTrue(r.usou_padrao)
        self.assertIn("como exemplo", r.texto)

    def test_resumo_e_reinicio_dos_dados(self):
        resumo = dict(self.a.resumo_dados())
        self.assertIn("(exemplo)", resumo["Pessoas"])
        self.a.responder("somos 2 pessoas, banho de 20 min, tarifa 0,95, chuveiro de 4500 W")
        resumo = dict(self.a.resumo_dados())
        self.assertEqual(resumo["Pessoas"], "2")
        self.assertIn("(sua)", resumo["Tarifa"])
        self.assertIn("(seu)", resumo["Chuveiro"])
        self.a.reiniciar_dados()
        self.assertIn("(exemplo)", dict(self.a.resumo_dados())["Pessoas"])

    def test_nao_entendi(self):
        r = self.a.responder("qual a capital da França")
        self.assertFalse(r.encontrou)

    def test_toda_resposta_de_calculo_traz_limitacoes(self):
        for pergunta in ("quanto consome", "quanto custa", "compare as alternativas", "impacto ambiental"):
            self.assertIn("Limitações", self.a.responder(pergunta).texto)


class TestIA(unittest.TestCase):
    def setUp(self):
        self.a = Assistente(premissas.carregar())
        self.chamadas = []

        def falso(url, cabecalhos, corpo, timeout):
            self.chamadas.append((url, cabecalhos, corpo))
            return self.resposta_falsa

        self.falso = falso
        self.resposta_falsa = {"content": [{"type": "text", "text": "Resposta de teste."}]}

    def _ia(self, provedor, **kw):
        return ConsultorIA(provedor=provedor, chave="chave-secreta-123", modelo="modelo-x",
                           enviar=self.falso, config={}, **kw)

    def test_sem_chave_fica_desativada(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            ia = ConsultorIA(enviar=self.falso, config={})
        self.assertFalse(ia.disponivel)
        self.assertIn("Pressione C", ia.motivo)
        with self.assertRaises(ErroIA):
            ia.perguntar("oi", "ctx")

    def test_detecta_provedor_pela_chave(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k"}, clear=True):
            ia = ConsultorIA(enviar=self.falso, config={})
        self.assertTrue(ia.disponivel)
        self.assertEqual(ia.provedor, "groq")
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k"}, clear=True):
            self.assertEqual(ConsultorIA(enviar=self.falso, config={}).provedor, "gemini")

    def test_provedor_forcado_e_chave_generica(self):
        env = {"IA_PROVEDOR": "groq", "IA_CHAVE": "k", "GEMINI_API_KEY": "outra"}
        with mock.patch.dict(os.environ, env, clear=True):
            ia = ConsultorIA(enviar=self.falso, config={})
        self.assertEqual(ia.provedor, "groq")
        self.assertEqual(ia.chave, "k")

    def test_provedor_sem_modelo_padrao_exige_ia_modelo(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "k"}, clear=True):
            ia = ConsultorIA(enviar=self.falso, config={})
        self.assertFalse(ia.disponivel)
        self.assertIn("IA_MODELO", ia.motivo)

    def test_provedor_desconhecido(self):
        ia = ConsultorIA(provedor="xyz", chave="k", enviar=self.falso, config={})
        self.assertFalse(ia.disponivel)
        self.assertIn("desconhecido", ia.motivo)

    def test_formato_gemini(self):
        self.resposta_falsa = {"candidates": [{"content": {"parts": [{"text": "Olá "}, {"text": "mundo"}]}}]}
        ia = self._ia("gemini")
        self.assertEqual(ia.perguntar("posso usar ar-condicionado?", self.a.contexto_para_ia()), "Olá mundo")
        url, cab, corpo = self.chamadas[0]
        self.assertTrue(url.startswith("https://generativelanguage.googleapis.com/"))
        self.assertIn("modelo-x:generateContent", url)
        self.assertNotIn("chave-secreta-123", url)           # chave só na header
        self.assertEqual(cab["x-goog-api-key"], "chave-secreta-123")
        self.assertIn("ANEEL", corpo["system_instruction"]["parts"][0]["text"])
        self.assertIn("ar-condicionado", corpo["contents"][0]["parts"][0]["text"])
        self.assertNotIn("chave-secreta-123", str(corpo))

    def test_formato_groq_e_openai(self):
        self.resposta_falsa = {"choices": [{"message": {"content": "Resposta compatível."}}]}
        for nome, campo in (("groq", "max_completion_tokens"), ("openrouter", "max_tokens")):
            self.chamadas.clear()
            ia = self._ia(nome)
            self.assertEqual(ia.perguntar("x", "contexto de teste"), "Resposta compatível.")
            url, cab, corpo = self.chamadas[0]
            self.assertEqual(cab["authorization"], "Bearer chave-secreta-123")
            self.assertEqual(corpo["model"], "modelo-x")
            self.assertIn(campo, corpo)
            self.assertEqual([m["role"] for m in corpo["messages"]], ["system", "user"])
            self.assertIn("contexto de teste", corpo["messages"][0]["content"])
            self.assertNotIn("chave-secreta-123", str(corpo))

    def test_formato_anthropic(self):
        ia = self._ia("anthropic")
        self.assertEqual(ia.perguntar("x", "ctx"), "Resposta de teste.")
        url, cab, corpo = self.chamadas[0]
        self.assertTrue(url.startswith("https://api.anthropic.com/"))
        self.assertEqual(cab["x-api-key"], "chave-secreta-123")
        self.assertIn("Nunca invente", corpo["system"])

    def test_resposta_anterior_vai_para_a_ia(self):
        self.resposta_falsa = {"choices": [{"message": {"content": "ok"}}]}
        self._ia("groq").perguntar("x", "ctx", resposta_anterior="texto antigo")
        self.assertIn("texto antigo", self.chamadas[0][2]["messages"][1]["content"])

    def test_pergunta_muito_longa_e_cortada(self):
        self.resposta_falsa = {"choices": [{"message": {"content": "ok"}}]}
        self._ia("groq").perguntar("a" * 5000, "ctx")
        self.assertLess(len(self.chamadas[0][2]["messages"][1]["content"]), 700)

    def test_resposta_vazia_ou_inesperada_gera_erro(self):
        for lixo in ({"content": []}, {}, {"choices": []}, {"candidates": [{}]}, None):
            self.resposta_falsa = lixo
            for nome in ("gemini", "groq", "anthropic"):
                with self.assertRaises(ErroIA):
                    self._ia(nome).perguntar("x", "ctx")

    def test_erro_da_api_nao_expoe_chave(self):
        def quebra(*a):
            raise ErroIA("chave recusada pelo provedor")
        ia = ConsultorIA(provedor="groq", chave="chave-secreta-123", enviar=quebra, config={})
        with self.assertRaises(ErroIA) as ctx:
            ia.perguntar("x", "ctx")
        self.assertNotIn("chave-secreta-123", str(ctx.exception))

    def test_contexto_para_ia_traz_calculos_e_fontes(self):
        self.a.responder("somos 4 pessoas e banho de 10 min")
        ctx = self.a.contexto_para_ia()
        self.assertIn("110,0 kWh/mês", ctx)
        self.assertIn("ANEEL", ctx)
        self.assertIn("Payback do aquecedor solar", ctx)
        self.assertIn("estimado", ctx)


class TestConfiguracao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "config_ia.json"

    def tearDown(self):
        self.pasta.cleanup()

    def test_arquivo_inexistente_ou_lixo_vira_config_vazia(self):
        self.assertEqual(config_ia.carregar(self.caminho), {"provedor": "", "chaves": {}, "modelos": {}})
        self.caminho.write_text("{isso não é json", encoding="utf-8")
        self.assertEqual(config_ia.carregar(self.caminho)["chaves"], {})
        self.caminho.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(config_ia.carregar(self.caminho)["provedor"], "")

    def test_primeira_chave_vira_provedor_em_uso(self):
        config_ia.definir_chave("groq", "gsk_abcdefghij1234", self.caminho)
        dados = config_ia.carregar(self.caminho)
        self.assertEqual(dados["provedor"], "groq")
        self.assertEqual(dados["chaves"]["groq"], "gsk_abcdefghij1234")
        config_ia.definir_chave("gemini", "AIzaSyABCDEFGHIJ", self.caminho)
        self.assertEqual(config_ia.carregar(self.caminho)["provedor"], "groq")  # não troca sozinho
        config_ia.definir_provedor("gemini", self.caminho)
        self.assertEqual(config_ia.carregar(self.caminho)["provedor"], "gemini")

    def test_remover_chave_do_provedor_em_uso_escolhe_outro(self):
        config_ia.definir_chave("groq", "gsk_abcdefghij1234", self.caminho)
        config_ia.definir_chave("gemini", "AIzaSyABCDEFGHIJ", self.caminho)
        config_ia.remover_chave("groq", self.caminho)
        dados = config_ia.carregar(self.caminho)
        self.assertNotIn("groq", dados["chaves"])
        self.assertEqual(dados["provedor"], "gemini")
        config_ia.remover_chave("gemini", self.caminho)
        self.assertEqual(config_ia.carregar(self.caminho)["provedor"], "")

    def test_modelo_e_removido_com_texto_vazio(self):
        config_ia.definir_modelo("groq", "meu-modelo", self.caminho)
        self.assertEqual(config_ia.carregar(self.caminho)["modelos"]["groq"], "meu-modelo")
        config_ia.definir_modelo("groq", "", self.caminho)
        self.assertNotIn("groq", config_ia.carregar(self.caminho)["modelos"])

    def test_chave_invalida_e_recusada(self):
        for ruim in ("", "curta", "tem espaço no meio da chave", "chave-com-acento-çãõ-123456"):
            with self.assertRaises(ValueError):
                config_ia.limpar_chave(ruim)
        self.assertEqual(config_ia.limpar_chave('  "gsk_abcdefghij1234"  '), "gsk_abcdefghij1234")

    def test_mascarar_nao_mostra_a_chave(self):
        self.assertEqual(config_ia.mascarar("gsk_abcdefghij1234"), "****1234")
        self.assertEqual(config_ia.mascarar("curta"), "****")

    def test_aceita_arquivo_com_bom_do_bloco_de_notas(self):
        self.caminho.write_text('{"provedor": "groq", "chaves": {"groq": "gsk_abcdefghij1234"}}', encoding="utf-8-sig")
        self.assertEqual(config_ia.carregar(self.caminho)["chaves"]["groq"], "gsk_abcdefghij1234")

    def test_ia_usa_a_chave_do_arquivo(self):
        config = {"provedor": "groq", "chaves": {"groq": "gsk_abcdefghij1234"}, "modelos": {"groq": "modelo-do-arquivo"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            ia = ConsultorIA(config=config)
        self.assertTrue(ia.disponivel)
        self.assertEqual((ia.provedor, ia.chave, ia.modelo), ("groq", "gsk_abcdefghij1234", "modelo-do-arquivo"))

    def test_ambiente_tem_prioridade_sobre_o_arquivo_na_chave(self):
        config = {"provedor": "groq", "chaves": {"groq": "chave-do-arquivo"}}
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "chave-do-ambiente"}, clear=True):
            self.assertEqual(ConsultorIA(config=config).chave, "chave-do-ambiente")

    def test_provedor_escolhido_no_arquivo_vence_a_deteccao_pelo_ambiente(self):
        config = {"provedor": "groq", "chaves": {"groq": "k-groq-123456"}}
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k-gem-123456"}, clear=True):
            self.assertEqual(ConsultorIA(config=config).provedor, "groq")

    def test_detecta_pelo_arquivo_quando_nao_ha_provedor_escolhido(self):
        config = {"chaves": {"gemini": "k-gem-123456"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(ConsultorIA(config=config).provedor, "gemini")

    def test_situacao_dos_provedores_nunca_expoe_a_chave(self):
        config = {"provedor": "groq", "chaves": {"groq": "gsk_abcdefghij1234"}}
        with mock.patch.dict(os.environ, {}, clear=True):
            situacao = situacao_provedores(config)
        groq = next(s for s in situacao if s["nome"] == "groq")
        self.assertTrue(groq["em_uso"])
        self.assertEqual(groq["origem"], "arquivo")
        self.assertNotIn("gsk_abcdefghij1234", str(situacao))
        self.assertFalse(next(s for s in situacao if s["nome"] == "gemini")["tem_chave"])

    def test_config_real_fica_fora_do_github(self):
        gitignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("config_ia.json", gitignore)


if __name__ == "__main__":
    unittest.main()
