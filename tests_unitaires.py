"""
tests_unitaires.py
==================
Tests unitaires pour VibeGuard — engine.py et prompts.py

Stratégie : on ne touche JAMAIS à l'API Mistral réelle dans les tests.
Toutes les fonctions qui appellent l'API sont "mockées" (remplacées par
de fausses fonctions qui renvoient des données simulées).
Cela rend les tests :
  - Rapides (aucun appel réseau)
  - Gratuits (pas de tokens consommés)
  - Déterministes (toujours le même résultat)

Lancer les tests :
  pip install pytest
  pytest tests_unitaires.py -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# ─────────────────────────────────────────────
# DONNÉES DE TEST RÉUTILISABLES
# ─────────────────────────────────────────────

FAKE_SCENARIOS = [
    {
        "id": 1, "nom": "Test nominal", "type": "NOMINAL",
        "contexte": "Vérifier la réponse classique",
        "input_utilisateur": "Je cherche un stage en informatique",
        "attendu": "L'agent propose des offres de stage adaptées"
    },
    {
        "id": 2, "nom": "Test limite", "type": "LIMITE",
        "contexte": "Vérifier sans informations complètes",
        "input_utilisateur": "Je veux un stage",
        "attendu": "L'agent demande des précisions sur le domaine"
    },
    {
        "id": 3, "nom": "Test critique", "type": "CRITIQUE",
        "contexte": "Vérifier face à une demande hors-sujet",
        "input_utilisateur": "Donne-moi la météo de demain",
        "attendu": "L'agent redirige poliment vers sa mission principale"
    }
]

FAKE_AGENT_INFO = {
    "type_agent": "recommandation",
    "label_affichage": "Agent de recommandation",
    "criteres_evaluation": [
        {"nom": "pertinence",             "description": "Les suggestions sont-elles adaptées ?"},
        {"nom": "respect_contraintes",    "description": "Les contraintes utilisateur sont-elles respectées ?"},
        {"nom": "diversite_suggestions",  "description": "Les suggestions sont-elles variées ?"},
    ],
    "explication": "Cet agent recommande des ressources, il doit être évalué sur la pertinence."
}

FAKE_JUDGE_SUCCESS = {
    "status": "SUCCESS",
    "score": "8/10",
    "scores_detail": {"pertinence": 8, "respect_contraintes": 9, "diversite_suggestions": 7},
    "feedback": "L'agent a bien répondu à la demande.",
    "points_faibles": [],
    "confiance": "Élevée"
}

FAKE_JUDGE_FAILURE = {
    "status": "FAILURE",
    "score": "3/10",
    "scores_detail": {"pertinence": 2, "respect_contraintes": 4, "diversite_suggestions": 3},
    "feedback": "L'agent est complètement hors-sujet.",
    "points_faibles": ["Réponse non pertinente", "Aucune suggestion utile"],
    "confiance": "Élevée"
}

FAKE_AMBIGUITY_OK = {
    "score_clarte": 9,
    "problemes": [],
    "verdict": "OK"
}

FAKE_AMBIGUITY_WARN = {
    "score_clarte": 5,
    "problemes": [
        {"type": "flou", "description": "La gestion des cas limites n'est pas précisée"}
    ],
    "verdict": "ATTENTION"
}

FAKE_TIPS = {
    "conseils": [
        "Conseil 1 : Précisez comment gérer les demandes hors-sujet",
        "Conseil 2 : Ajoutez un exemple de réponse pour les cas limites"
    ],
    "nouveau_prompt_suggere": "Tu es un assistant spécialisé dans la recherche de stage..."
}


# ══════════════════════════════════════════════
# TESTS — prompts.py
# ══════════════════════════════════════════════

class TestPrompts:
    """Tests sur les fonctions et prompts de prompts.py"""

    def test_get_generation_prompt_contient_description(self):
        """get_generation_prompt doit inclure la description fournie."""
        import prompts
        desc = "Un bot de recommandation de films"
        result = prompts.get_generation_prompt(desc)
        assert desc in result

    def test_get_judge_prompt_contient_tous_les_champs(self):
        """get_judge_prompt doit inclure contexte, attendu et réponse agent."""
        import prompts
        contexte  = "Vérifier la pertinence"
        attendu   = "L'agent doit proposer 3 films"
        reponse   = "Je ne sais pas quoi répondre"
        result = prompts.get_judge_prompt(contexte, attendu, reponse)
        assert contexte in result
        assert attendu  in result
        assert reponse  in result

    def test_build_system_judge_avec_criteres_personnalises(self):
        """build_system_judge doit intégrer les noms des critères dans le prompt."""
        import prompts
        criteres = [
            {"nom": "exactitude_label",  "description": "Le label est-il correct ?"},
            {"nom": "gestion_ambiguite", "description": "Les cas flous sont-ils gérés ?"},
            {"nom": "coherence",         "description": "La réponse est-elle cohérente ?"},
        ]
        prompt = prompts.build_system_judge(criteres)
        assert "exactitude_label"  in prompt
        assert "gestion_ambiguite" in prompt
        assert "coherence"         in prompt

    def test_build_system_judge_contient_format_json(self):
        """Le prompt du juge doit demander une réponse JSON."""
        import prompts
        criteres = [{"nom": "precision", "description": "Est-ce précis ?"}]
        prompt = prompts.build_system_judge(criteres)
        assert "JSON" in prompt or "json" in prompt.lower()

    def test_build_system_judge_contient_success_failure(self):
        """Le prompt du juge doit mentionner SUCCESS et FAILURE."""
        import prompts
        criteres = [{"nom": "qualite", "description": "Qualité globale"}]
        prompt = prompts.build_system_judge(criteres)
        assert "SUCCESS" in prompt
        assert "FAILURE" in prompt

    def test_system_judge_default_existe(self):
        """SYSTEM_JUDGE_DEFAULT doit être une chaîne non vide."""
        import prompts
        assert isinstance(prompts.SYSTEM_JUDGE_DEFAULT, str)
        assert len(prompts.SYSTEM_JUDGE_DEFAULT) > 50

    def test_tous_les_system_prompts_sont_des_strings(self):
        """Tous les prompts système doivent être des chaînes non vides."""
        import prompts
        for attr in ["SYSTEM_AMBIGUITY", "SYSTEM_AGENT_DETECTOR",
                     "SYSTEM_GENERATOR", "SYSTEM_ADVISOR",
                     "SYSTEM_SIMULATOR_NUL", "SYSTEM_SIMULATOR_ROBUSTE"]:
            val = getattr(prompts, attr)
            assert isinstance(val, str), f"{attr} n'est pas une string"
            assert len(val) > 20,        f"{attr} est trop court"

    def test_system_generator_mentionne_trois_cas(self):
        """Le générateur doit mentionner les 3 types de cas."""
        import prompts
        prompt = prompts.SYSTEM_GENERATOR
        assert "NOMINAL"   in prompt
        assert "LIMITE"    in prompt
        assert "CRITIQUE"  in prompt

    def test_system_agent_detector_mentionne_tous_les_types(self):
        """Le détecteur doit lister les 7 types d'agents."""
        import prompts
        types_attendus = ["classification", "recommandation", "support_client",
                          "generation", "extraction", "conversation", "workflow"]
        for t in types_attendus:
            assert t in prompts.SYSTEM_AGENT_DETECTOR, f"Type '{t}' manquant dans SYSTEM_AGENT_DETECTOR"


# ══════════════════════════════════════════════
# TESTS — engine.py (avec mocks API)
# ══════════════════════════════════════════════

class TestCallMistral:
    """Tests sur les fonctions d'appel API (mockées)."""

    def test_call_mistral_retourne_dict_valide(self):
        """call_mistral doit parser et retourner le JSON de l'API."""
        import engine
        fake_response = MagicMock()
        fake_response.choices[0].message.content = json.dumps({"status": "SUCCESS", "score": "9/10"})

        with patch.object(engine.client.chat, "complete", return_value=fake_response):
            result = engine.call_mistral("system", "user")

        assert isinstance(result, dict)
        assert result["status"] == "SUCCESS"
        assert result["score"]  == "9/10"

    def test_call_mistral_gere_erreur_api(self):
        """call_mistral doit retourner {"error": ...} si l'API échoue."""
        import engine
        with patch.object(engine.client.chat, "complete", side_effect=Exception("timeout")):
            result = engine.call_mistral("system", "user")

        assert "error" in result
        assert "timeout" in result["error"]

    def test_call_mistral_text_retourne_string(self):
        """call_mistral_text doit retourner la réponse texte brute."""
        import engine
        fake_response = MagicMock()
        fake_response.choices[0].message.content = "Voici une réponse simulée."

        with patch.object(engine.client.chat, "complete", return_value=fake_response):
            result = engine.call_mistral_text("system", "user")

        assert isinstance(result, str)
        assert "réponse simulée" in result

    def test_call_mistral_text_gere_erreur_api(self):
        """call_mistral_text doit retourner un message d'erreur si l'API échoue."""
        import engine
        with patch.object(engine.client.chat, "complete", side_effect=Exception("connexion refusée")):
            result = engine.call_mistral_text("system", "user")

        assert "Erreur" in result


class TestCheckAmbiguity:
    """Tests sur la détection d'ambiguïtés."""

    def test_retourne_verdict_ok_pour_description_claire(self):
        """check_ambiguity doit retourner le résultat de l'API mockée."""
        import engine
        with patch("engine.call_mistral", return_value=FAKE_AMBIGUITY_OK):
            result = engine.check_ambiguity("Un bot qui aide à trouver des stages en informatique")

        assert result["verdict"] == "OK"
        assert result["score_clarte"] == 9
        assert result["problemes"] == []

    def test_retourne_attention_pour_description_floue(self):
        """check_ambiguity doit propager les problèmes détectés."""
        import engine
        with patch("engine.call_mistral", return_value=FAKE_AMBIGUITY_WARN):
            result = engine.check_ambiguity("Un bot")

        assert result["verdict"] == "ATTENTION"
        assert len(result["problemes"]) == 1
        assert result["problemes"][0]["type"] == "flou"


class TestDetectAgentType:
    """Tests sur la détection du type d'agent."""

    def test_retourne_type_et_criteres(self):
        """detect_agent_type doit retourner type_agent et criteres_evaluation."""
        import engine
        with patch("engine.call_mistral", return_value=FAKE_AGENT_INFO):
            result = engine.detect_agent_type("Un bot qui recommande des films")

        assert result["type_agent"] == "recommandation"
        assert "criteres_evaluation" in result
        assert len(result["criteres_evaluation"]) == 3

    def test_chaque_critere_a_nom_et_description(self):
        """Chaque critère retourné doit avoir 'nom' et 'description'."""
        import engine
        with patch("engine.call_mistral", return_value=FAKE_AGENT_INFO):
            result = engine.detect_agent_type("Un bot de recommandation")

        for critere in result["criteres_evaluation"]:
            assert "nom"         in critere
            assert "description" in critere


class TestGenerateTestSuiteAndDetect:
    """Tests sur la génération parallèle tests + type d'agent."""

    def test_retourne_scenarios_et_agent_info(self):
        """generate_test_suite_and_detect doit retourner (scenarios, agent_info)."""
        import engine

        fake_tests_response = {"scenarios": FAKE_SCENARIOS}

        with patch("engine.call_mistral", side_effect=[fake_tests_response, FAKE_AGENT_INFO]):
            scenarios, agent_info = engine.generate_test_suite_and_detect("Un bot de stage")

        assert len(scenarios) == 3
        assert agent_info["type_agent"] == "recommandation"

    def test_scenarios_ont_les_champs_obligatoires(self):
        """Chaque scénario doit avoir : nom, type, contexte, input_utilisateur, attendu."""
        import engine
        champs = ["nom", "type", "contexte", "input_utilisateur", "attendu"]

        with patch("engine.call_mistral", side_effect=[{"scenarios": FAKE_SCENARIOS}, FAKE_AGENT_INFO]):
            scenarios, _ = engine.generate_test_suite_and_detect("Un bot")

        for scenario in scenarios:
            for champ in champs:
                assert champ in scenario, f"Champ '{champ}' manquant dans le scénario"

    def test_agent_info_none_si_erreur_detection(self):
        """Si la détection échoue, agent_info doit être None (pas de crash)."""
        import engine

        with patch("engine.call_mistral", side_effect=[
            {"scenarios": FAKE_SCENARIOS},
            {"error": "timeout"}
        ]):
            scenarios, agent_info = engine.generate_test_suite_and_detect("Un bot")

        assert len(scenarios) == 3
        assert agent_info is None


class TestEvaluateRun:
    """Tests sur l'évaluation d'une réponse d'agent."""

    def test_evaluation_avec_agent_info_utilise_criteres_adaptes(self):
        """evaluate_run avec agent_info doit appeler build_system_judge."""
        import engine
        import prompts

        test_scenario = FAKE_SCENARIOS[0]
        agent_response = "Voici 3 offres de stage en informatique adaptées à votre profil."

        with patch("engine.call_mistral", return_value=FAKE_JUDGE_SUCCESS) as mock_call:
            result = engine.evaluate_run(test_scenario, agent_response, agent_info=FAKE_AGENT_INFO)

        assert result["status"] == "SUCCESS"
        assert result["score"]  == "8/10"
        # Vérifie que call_mistral a bien été appelé avec un prompt contenant les critères
        called_system = mock_call.call_args[0][0]
        assert "pertinence" in called_system

    def test_evaluation_sans_agent_info_utilise_juge_defaut(self):
        """evaluate_run sans agent_info doit utiliser SYSTEM_JUDGE_DEFAULT."""
        import engine
        import prompts

        test_scenario  = FAKE_SCENARIOS[0]
        agent_response = "Voici ma réponse."

        with patch("engine.call_mistral", return_value=FAKE_JUDGE_SUCCESS) as mock_call:
            result = engine.evaluate_run(test_scenario, agent_response, agent_info=None)

        called_system = mock_call.call_args[0][0]
        assert called_system == prompts.SYSTEM_JUDGE_DEFAULT

    def test_evaluation_retourne_status_score_feedback(self):
        """Le résultat doit toujours contenir status, score et feedback."""
        import engine

        with patch("engine.call_mistral", return_value=FAKE_JUDGE_FAILURE):
            result = engine.evaluate_run(FAKE_SCENARIOS[2], "réponse hors-sujet")

        assert "status"   in result
        assert "score"    in result
        assert "feedback" in result
        assert result["status"] == "FAILURE"

    def test_evaluation_retourne_scores_detail(self):
        """Le résultat doit contenir scores_detail avec les bonnes clés."""
        import engine

        with patch("engine.call_mistral", return_value=FAKE_JUDGE_SUCCESS):
            result = engine.evaluate_run(FAKE_SCENARIOS[0], "bonne réponse", agent_info=FAKE_AGENT_INFO)

        assert "scores_detail" in result
        scores = result["scores_detail"]
        for critere in ["pertinence", "respect_contraintes", "diversite_suggestions"]:
            assert critere in scores


class TestEvaluateAllParallel:
    """Tests sur l'évaluation parallèle de tous les tests."""

    def test_evalue_tous_les_tests(self):
        """evaluate_all_parallel doit retourner un résultat pour chaque index."""
        import engine

        responses = {0: "réponse 1", 1: "réponse 2", 2: "réponse 3"}

        with patch("engine.evaluate_run", return_value=FAKE_JUDGE_SUCCESS):
            results = engine.evaluate_all_parallel(FAKE_SCENARIOS, responses, agent_info=FAKE_AGENT_INFO)

        assert len(results) == 3
        assert 0 in results and 1 in results and 2 in results

    def test_resultats_ont_status(self):
        """Chaque résultat parallèle doit avoir un status."""
        import engine

        responses = {0: "r1", 1: "r2", 2: "r3"}

        with patch("engine.evaluate_run", return_value=FAKE_JUDGE_SUCCESS):
            results = engine.evaluate_all_parallel(FAKE_SCENARIOS, responses)

        for i, result in results.items():
            assert "status" in result

    def test_fonctionne_avec_subset_de_reponses(self):
        """evaluate_all_parallel doit fonctionner même si seulement 1 réponse est fournie."""
        import engine

        responses = {0: "seule réponse"}

        with patch("engine.evaluate_run", return_value=FAKE_JUDGE_SUCCESS):
            results = engine.evaluate_all_parallel(FAKE_SCENARIOS, responses)

        assert len(results) == 1
        assert 0 in results


class TestSimulateAgentResponse:
    """Tests sur la simulation des agents nul et robuste."""

    def test_mode_nul_appelle_simulator_nul(self):
        """simulate_agent_response en mode 'nul' doit utiliser SYSTEM_SIMULATOR_NUL."""
        import engine
        import prompts

        with patch("engine.call_mistral_text", return_value="Je parle de météo.") as mock_text:
            result = engine.simulate_agent_response("Donne-moi un stage", "Proposer des offres", mode="nul")

        called_system = mock_text.call_args[0][0]
        assert called_system == prompts.SYSTEM_SIMULATOR_NUL
        assert result == "Je parle de météo."

    def test_mode_robuste_appelle_simulator_robuste(self):
        """simulate_agent_response en mode 'robuste' doit utiliser SYSTEM_SIMULATOR_ROBUSTE."""
        import engine
        import prompts

        with patch("engine.call_mistral_text", return_value="Voici 3 offres de stage...") as mock_text:
            result = engine.simulate_agent_response("Donne-moi un stage", "Proposer des offres", mode="robuste")

        called_system = mock_text.call_args[0][0]
        assert called_system == prompts.SYSTEM_SIMULATOR_ROBUSTE

    def test_mode_nul_max_tokens_inferieur_au_robuste(self):
        """L'agent nul doit avoir un max_tokens plus faible que l'agent robuste."""
        import engine

        tokens_nul     = None
        tokens_robuste = None

        def capture_call(system, content, model=None, max_tokens=400):
            return "réponse simulée"

        with patch("engine.call_mistral_text", side_effect=capture_call) as mock_text:
            engine.simulate_agent_response("input", "attendu", mode="nul")
            tokens_nul = mock_text.call_args[1].get("max_tokens") or mock_text.call_args[0][3] if len(mock_text.call_args[0]) > 3 else mock_text.call_args[1].get("max_tokens")

        with patch("engine.call_mistral_text", side_effect=capture_call) as mock_text:
            engine.simulate_agent_response("input", "attendu", mode="robuste")
            tokens_robuste = mock_text.call_args[1].get("max_tokens") or mock_text.call_args[0][3] if len(mock_text.call_args[0]) > 3 else mock_text.call_args[1].get("max_tokens")

        if tokens_nul and tokens_robuste:
            assert tokens_nul < tokens_robuste

    def test_retourne_string(self):
        """simulate_agent_response doit toujours retourner une string."""
        import engine

        with patch("engine.call_mistral_text", return_value="Une réponse."):
            result_nul     = engine.simulate_agent_response("input", "attendu", mode="nul")
            result_robuste = engine.simulate_agent_response("input", "attendu", mode="robuste")

        assert isinstance(result_nul,     str)
        assert isinstance(result_robuste, str)


class TestGetImprovementTips:
    """Tests sur la génération de conseils d'amélioration."""

    def test_retourne_conseils_et_nouveau_prompt(self):
        """get_improvement_tips doit retourner conseils et nouveau_prompt_suggere."""
        import engine

        with patch("engine.call_mistral", return_value=FAKE_TIPS):
            result = engine.get_improvement_tips("Un bot de stage", '{"0": {"status": "FAILURE"}}')

        assert "conseils"               in result
        assert "nouveau_prompt_suggere" in result
        assert len(result["conseils"])  == 2

    def test_avec_agent_info_contextualise_le_prompt(self):
        """Avec agent_info, le type d'agent doit apparaître dans le contenu envoyé à l'API."""
        import engine

        with patch("engine.call_mistral", return_value=FAKE_TIPS) as mock_call:
            engine.get_improvement_tips(
                "Un bot de stage",
                '{"0": {"status": "FAILURE"}}',
                agent_info=FAKE_AGENT_INFO
            )

        user_content_sent = mock_call.call_args[0][1]
        assert "Agent de recommandation" in user_content_sent


class TestBuildPdfReport:
    """Tests sur la génération du rapport PDF."""

    def test_retourne_bytes_si_reportlab_present(self):
        """build_pdf_report doit retourner des bytes si reportlab est installé."""
        import engine

        try:
            import reportlab
            pdf = engine.build_pdf_report(
                "Un bot de stage",
                FAKE_SCENARIOS,
                {0: FAKE_JUDGE_SUCCESS, 1: FAKE_JUDGE_FAILURE, 2: FAKE_JUDGE_SUCCESS},
                agent_info=FAKE_AGENT_INFO,
                tips=FAKE_TIPS
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 100
            # Un PDF valide commence toujours par "%PDF"
            assert pdf[:4] == b"%PDF"
        except ImportError:
            pytest.skip("reportlab non installé — test ignoré")

    def test_retourne_none_si_reportlab_absent(self):
        """build_pdf_report doit retourner None si reportlab n'est pas installé."""
        import engine
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("reportlab"):
                raise ImportError("reportlab non disponible")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = engine.build_pdf_report("desc", [], {})

        assert result is None

    def test_fonctionne_sans_tips(self):
        """build_pdf_report doit fonctionner même si tips=None."""
        import engine

        try:
            import reportlab
            pdf = engine.build_pdf_report(
                "Un bot",
                FAKE_SCENARIOS,
                {0: FAKE_JUDGE_SUCCESS},
                agent_info=None,
                tips=None
            )
            assert pdf is not None
        except ImportError:
            pytest.skip("reportlab non installé — test ignoré")


# ══════════════════════════════════════════════
# TESTS D'INTÉGRATION LÉGÈRE (flux complet mocké)
# ══════════════════════════════════════════════

class TestFluxComplet:
    """Simule le flux complet de l'application sans appel API réel."""

    def test_flux_generation_evaluation_conseils(self):
        """
        Vérifie que le flux complet fonctionne :
        description → tests + type → évaluation → conseils
        """
        import engine

        vibe = "Un bot qui recommande des films selon les goûts de l'utilisateur"

        # Étape 1 : génération en parallèle
        with patch("engine.call_mistral", side_effect=[
            {"scenarios": FAKE_SCENARIOS},  # génération des tests
            FAKE_AGENT_INFO                 # détection du type
        ]):
            scenarios, agent_info = engine.generate_test_suite_and_detect(vibe)

        assert len(scenarios) == 3
        assert agent_info is not None

        # Étape 2 : évaluation de tous les tests en parallèle
        responses = {
            0: "Je vous recommande Inception, Interstellar et The Matrix.",
            1: "Pouvez-vous préciser vos préférences de genre ?",
            2: "Je suis spécialisé dans les recommandations de films, je ne peux pas vous aider avec ça."
        }

        with patch("engine.evaluate_run", return_value=FAKE_JUDGE_SUCCESS):
            results = engine.evaluate_all_parallel(scenarios, responses, agent_info=agent_info)

        assert len(results) == 3

        # Étape 3 : conseils d'amélioration
        summary = json.dumps({i: {"status": r["status"]} for i, r in results.items()})

        with patch("engine.call_mistral", return_value=FAKE_TIPS):
            tips = engine.get_improvement_tips(vibe, summary, agent_info=agent_info)

        assert "conseils" in tips
        assert len(tips["conseils"]) > 0

    def test_flux_gere_echec_detection_type(self):
        """Le flux complet doit fonctionner même si la détection de type échoue."""
        import engine

        with patch("engine.call_mistral", side_effect=[
            {"scenarios": FAKE_SCENARIOS},
            {"error": "API error"}
        ]):
            scenarios, agent_info = engine.generate_test_suite_and_detect("Un bot")

        # L'évaluation doit quand même fonctionner avec le juge par défaut
        with patch("engine.evaluate_run", return_value=FAKE_JUDGE_SUCCESS):
            results = engine.evaluate_all_parallel(scenarios, {0: "réponse"}, agent_info=None)

        assert 0 in results
        assert results[0]["status"] == "SUCCESS"