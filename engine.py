import json
import concurrent.futures
from mistralai.client import Mistral
import prompts

MISTRAL_API_KEY = "lYkXVRLEFedkp2CL5ycuRWcZiqtwo3Ms"
MODEL_NAME = "mistral-large-latest"   # Génération, évaluation, conseils (précision max)
MODEL_FAST = "mistral-small-latest"   # Simulation + ambiguïté (vitesse)

client = Mistral(api_key=MISTRAL_API_KEY)

# ─────────────────────────────────────────────
# HELPERS D'APPEL
# ─────────────────────────────────────────────

def call_mistral(system_prompt, user_content, model=None, max_tokens=1024):
    """Appel Mistral avec JSON forcé."""
    model = model or MODEL_NAME
    try:
        response = client.chat.complete(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur API Mistral (JSON) : {e}")
        return {"error": str(e)}

def call_mistral_text(system_prompt, user_content, model=None, max_tokens=400):
    """Appel Mistral en texte libre (simulation)."""
    model = model or MODEL_FAST
    try:
        response = client.chat.complete(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_content}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erreur API Mistral (text) : {e}")
        return f"Erreur lors de la simulation : {str(e)}"

# ─────────────────────────────────────────────
# ÉTAPE 0 : DÉTECTION D'AMBIGUÏTÉS (rapide, small)
# ─────────────────────────────────────────────

def check_ambiguity(vibe_description):
    """Analyse la description pour détecter les zones floues avant génération des tests."""
    return call_mistral(
        prompts.SYSTEM_AMBIGUITY,
        f"Description de l'agent : {vibe_description}",
        model=MODEL_FAST,
        max_tokens=512
    )

# ─────────────────────────────────────────────
# ÉTAPE 1 : GÉNÉRATION DES TESTS
# ─────────────────────────────────────────────

def generate_test_suite(vibe_description):
    """Génère les scénarios de test à partir de la description métier."""
    return call_mistral(
        prompts.SYSTEM_GENERATOR,
        prompts.get_generation_prompt(vibe_description),
        max_tokens=1200
    )

# ─────────────────────────────────────────────
# ÉTAPE 2 : ÉVALUATION (unitaire + parallèle)
# ─────────────────────────────────────────────

def evaluate_run(test_scenario, agent_response):
    """Évalue UN test — appelé unitairement depuis l'UI."""
    user_input = prompts.get_judge_prompt(
        test_scenario['contexte'],
        test_scenario['attendu'],
        agent_response
    )
    return call_mistral(prompts.SYSTEM_JUDGE, user_input, max_tokens=512)

def evaluate_all_parallel(tests, responses: dict):
    """
    Évalue TOUS les tests en parallèle (ThreadPoolExecutor).
    responses = {index: texte_reponse}
    Retourne {index: result_dict}
    """
    results = {}

    def _eval(i):
        return i, evaluate_run(tests[i], responses[i])

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_eval, i): i for i in responses}
        for future in concurrent.futures.as_completed(futures):
            i, result = future.result()
            results[i] = result

    return results

# ─────────────────────────────────────────────
# ÉTAPE 3 : CONSEILS D'AMÉLIORATION
# ─────────────────────────────────────────────

def get_improvement_tips(vibe_description, failed_tests_summary):
    """Propose des corrections basées sur les résultats des tests."""
    user_input = f"Vibe initiale : {vibe_description}\nRésumé des résultats : {failed_tests_summary}"
    return call_mistral(prompts.SYSTEM_ADVISOR, user_input, max_tokens=800)

# ─────────────────────────────────────────────
# SIMULATION AGENT NUL / ROBUSTE
# ─────────────────────────────────────────────

def simulate_agent_response(user_input, attendu, mode="robuste"):
    """
    Simule la réponse d'un agent.
    mode='nul'     → réponse hors-sujet absurde
    mode='robuste' → réponse exemplaire couvrant tous les attendus
    """
    system_prompt = prompts.SYSTEM_SIMULATOR_NUL if mode == "nul" else prompts.SYSTEM_SIMULATOR_ROBUSTE
    user_content  = f"Message de l'utilisateur : {user_input}\nCe qui était attendu : {attendu}"
    max_tok = 250 if mode == "nul" else 500
    return call_mistral_text(system_prompt, user_content, max_tokens=max_tok)

# ─────────────────────────────────────────────
# EXPORT PDF
# ─────────────────────────────────────────────

def build_pdf_report(vibe_desc, tests, results, tips=None):
    """
    Génère un rapport PDF en mémoire (bytes) avec ReportLab.
    Retourne les bytes du PDF ou None si ReportLab absent.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        )
        from io import BytesIO

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles    = getSampleStyleSheet()
        t_style   = ParagraphStyle("t",  parent=styles["Title"],   fontSize=18, spaceAfter=6)
        h2_style  = ParagraphStyle("h2", parent=styles["Heading2"],fontSize=13, spaceAfter=4)
        b_style   = ParagraphStyle("b",  parent=styles["Normal"],  fontSize=10, spaceAfter=4)
        cap_style = ParagraphStyle("c",  parent=styles["Normal"],  fontSize=9,
                                   textColor=colors.grey, spaceAfter=2)

        story = []
        story.append(Paragraph("VibeGuard — Rapport d'Évaluation", t_style))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#6366f1")))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f"<b>Description de l'agent :</b> {vibe_desc}", b_style))
        story.append(Spacer(1, 0.4*cm))

        # Score global
        total   = len(tests)
        passed  = sum(1 for r in results.values() if r.get("status") == "SUCCESS")
        pct     = int(passed / total * 100) if total else 0
        verdict = "Robuste" if pct == 100 else ("Fragile" if pct >= 50 else "Instable")
        story.append(Paragraph(
            f"<b>Score global :</b> {passed}/{total} tests réussis ({pct}%) — {verdict}", h2_style))
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Détail des tests", h2_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        story.append(Spacer(1, 0.2*cm))

        for i, test in enumerate(tests):
            result   = results.get(i, {})
            status   = result.get("status",   "—")
            score    = result.get("score",    "—")
            feedback = result.get("feedback", "—")
            points_faibles = result.get("points_faibles", [])
            confiance      = result.get("confiance", "")
            scores_detail  = result.get("scores_detail", {})

            color_hex = "#16a34a" if status == "SUCCESS" else "#dc2626"
            story.append(Paragraph(
                f'<font color="{color_hex}"><b>Test #{i+1} — {test["nom"]} | {status} ({score})</b></font>',
                b_style))
            story.append(Paragraph(f"<b>Contexte :</b> {test['contexte']}", cap_style))
            story.append(Paragraph(f"<b>Entrée :</b> {test['input_utilisateur']}", cap_style))
            story.append(Paragraph(f"<b>Attendu :</b> {test['attendu']}", cap_style))
            story.append(Paragraph(f"<b>Feedback :</b> {feedback}", b_style))
            if points_faibles:
                story.append(Paragraph(
                    f"<b>Points faibles :</b> {' | '.join(points_faibles)}", cap_style))
            if scores_detail:
                detail_str = "  ".join(
                    [f"{k}: {v}/10" for k, v in scores_detail.items()])
                story.append(Paragraph(f"<b>Détail scores :</b> {detail_str}", cap_style))
            if confiance:
                story.append(Paragraph(f"<b>Confiance du juge :</b> {confiance}", cap_style))
            story.append(Spacer(1, 0.3*cm))

        if tips:
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph("Conseils d'amélioration", h2_style))
            for conseil in tips.get("conseils", []):
                story.append(Paragraph(f"• {conseil}", b_style))
            nouveau_prompt = tips.get("nouveau_prompt_suggere", "")
            if nouveau_prompt:
                story.append(Spacer(1, 0.2*cm))
                story.append(Paragraph("<b>Prompt amélioré suggéré :</b>", b_style))
                story.append(Paragraph(nouveau_prompt, cap_style))

        doc.build(story)
        return buf.getvalue()

    except ImportError:
        return None