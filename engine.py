import os
import json
from mistralai.client import Mistral
import prompts

# Remplace par ta clé API Mistral ou utilise une variable d'environnement
MISTRAL_API_KEY = "lYkXVRLEFedkp2CL5ycuRWcZiqtwo3Ms"
MODEL_NAME = "mistral-large-latest"

client = Mistral(api_key=MISTRAL_API_KEY)

def call_mistral(system_prompt, user_content):
    """Fonction générique pour appeler Mistral et récupérer du JSON propre."""
    try:
        response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erreur API Mistral : {e}")
        return {"error": str(e)}

def call_mistral_text(system_prompt, user_content):
    """Appel Mistral en mode texte libre (pas de JSON forcé) — utilisé pour la simulation."""
    try:
        response = client.chat.complete(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Erreur API Mistral : {e}")
        return f"Erreur lors de la simulation : {str(e)}"

def generate_test_suite(vibe_description):
    """Étape 1 : Générer les scénarios de test à partir de l'idée de l'utilisateur."""
    user_input = prompts.get_generation_prompt(vibe_description)
    return call_mistral(prompts.SYSTEM_GENERATOR, user_input)

def evaluate_run(test_scenario, agent_response):
    """Étape 2 : Faire juger la performance de l'agent par Mistral."""
    user_input = prompts.get_judge_prompt(
        test_scenario['contexte'], 
        test_scenario['attendu'], 
        agent_response
    )
    return call_mistral(prompts.SYSTEM_JUDGE, user_input)

def get_improvement_tips(vibe_description, failed_tests_summary):
    """Étape 3 : Proposer des corrections basées sur les échecs."""
    user_input = f"Vibe initiale : {vibe_description}\nRésumé des échecs : {failed_tests_summary}"
    return call_mistral(prompts.SYSTEM_ADVISOR, user_input)

def simulate_agent_response(user_input, attendu, mode="robuste"):
    """
    Simule la réponse d'un agent selon le mode choisi.
    
    - mode="nul"     : répond quelque chose de complètement hors-sujet.
    - mode="robuste" : répond de manière parfaite, en couvrant tous les attendus.
    """
    if mode == "nul":
        system_prompt = prompts.SYSTEM_SIMULATOR_NUL
    else:
        system_prompt = prompts.SYSTEM_SIMULATOR_ROBUSTE

    user_content = f"""
Message de l'utilisateur : {user_input}
Ce qui était attendu de l'agent : {attendu}
"""
    return call_mistral_text(system_prompt, user_content)