import streamlit as st
import engine
import json
import math

# ─────────────────────────────────────────────
# HELPER : RADAR CHART
# ─────────────────────────────────────────────
def _render_radar(scores_detail: dict, key: str = ""):
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        labels    = list(scores_detail.keys())
        vals      = [float(scores_detail[k]) for k in labels]
        N         = len(labels)
        angles    = [n / float(N) * 2 * math.pi for n in range(N)]
        angles   += angles[:1]
        vals_plot = vals + vals[:1]

        fig, ax = plt.subplots(figsize=(2.8, 2.8), subplot_kw=dict(polar=True))
        ax.set_facecolor("#0f172a")
        fig.patch.set_facecolor("#0f172a")
        ax.plot(angles, vals_plot, color="#818cf8", linewidth=2)
        ax.fill(angles, vals_plot, color="#818cf8", alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([l.capitalize() for l in labels], color="white", size=8)
        ax.set_ylim(0, 10)
        ax.set_yticks([2, 4, 6, 8, 10])
        ax.set_yticklabels(["2", "4", "6", "8", "10"], color="grey", size=6)
        ax.grid(color="grey", alpha=0.3)
        ax.spines["polar"].set_color("grey")

        st.pyplot(fig, use_container_width=False)
        plt.close(fig)
    except ImportError:
        for k, v in scores_detail.items():
            bar = "█" * int(v) + "░" * (10 - int(v))
            st.caption(f"{k.capitalize()}: {bar} {v}/10")


# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(page_title="Mady.AI", page_icon="🛡️", layout="wide")
st.title("Mady.AI : Tester votre Agent IA !")
st.subheader("Passez de l’intuition à l’agent robuste : testez, évaluez et améliorez vos agents.")

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
for _k, _v in [
    ("tests",      None),
    ("results",    {}),
    ("tips",       None),
    ("ambiguity",  None),
    ("agent_info", None),   # ← type d'agent détecté + critères
    ("history",    []),
    ("vibe_desc",  ""),
]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    vibe_desc = st.text_area(
        "Décrivez votre agent :",
        placeholder="Ex: Un bot qui aide les étudiants à trouver un stage en informatique...",
        height=150
    )

    # Vérification ambiguïté
    if st.button("🔍 Vérifier la description", use_container_width=True):
        if vibe_desc.strip():
            with st.spinner("Analyse des ambiguïtés..."):
                st.session_state.ambiguity = engine.check_ambiguity(vibe_desc)
        else:
            st.warning("Entrez une description d'abord.")

    amb = st.session_state.ambiguity
    if amb and "error" not in amb:
        verdict = amb.get("verdict", "OK")
        score_c = amb.get("score_clarte", "?")
        if verdict == "OK":
            st.success(f"✅ Description claire (clarté : {score_c}/10)")
        elif verdict == "ATTENTION":
            st.warning(f"⚠️ Quelques zones floues (clarté : {score_c}/10)")
        else:
            st.error(f"🚨 Description trop vague (clarté : {score_c}/10)")
        for pb in amb.get("problemes", []):
            st.caption(f"• **{pb.get('type','').upper()}** — {pb.get('description','')}")

    st.divider()

    # Génération (tests + type d'agent en parallèle)
    if st.button("🚀 Générer le Banc d'Essai", use_container_width=True, type="primary"):
        if vibe_desc.strip():
            with st.spinner("Génération des tests et analyse du type d'agent..."):
                scenarios, agent_info = engine.generate_test_suite_and_detect(vibe_desc)
                st.session_state.tests      = scenarios
                st.session_state.agent_info = agent_info
                st.session_state.results    = {}
                st.session_state.tips       = None
                st.session_state.vibe_desc  = vibe_desc
                for j in range(10):
                    st.session_state.pop(f"resp_{j}", None)
            st.success(f"✅ {len(scenarios)} tests générés !")
        else:
            st.warning("Entrez une description d'abord.")

    # Historique
    if st.session_state.history:
        st.divider()
        st.markdown("### 📜 Historique des runs")
        for idx, run in enumerate(reversed(st.session_state.history[-5:])):
            color = "🟢" if run["pct"] == 100 else ("🟡" if run["pct"] >= 50 else "🔴")
            st.caption(
                f"{color} Run #{len(st.session_state.history) - idx} — "
                f"{run['passed']}/{run['total']} ({run['pct']}%) — "
                f"{run['vibe'][:30]}..."
            )


# ─────────────────────────────────────────────
# BADGE TYPE D'AGENT
# ─────────────────────────────────────────────
TYPE_ICONS = {
    "classification": "🏷️",
    "recommandation": "💡",
    "support_client": "🎧",
    "generation":     "✍️",
    "extraction":     "🔎",
    "conversation":   "💬",
    "workflow":       "⚙️",
}

if st.session_state.tests and st.session_state.agent_info:
    ai = st.session_state.agent_info
    type_key  = ai.get("type_agent", "")
    label     = ai.get("label_affichage", type_key)
    icon      = TYPE_ICONS.get(type_key, "🤖")
    explication = ai.get("explication", "")
    criteres    = ai.get("criteres_evaluation", [])

    with st.container():
        st.markdown(f"### {icon} Type d'agent détecté : **{label}**")
        st.caption(explication)
        if criteres:
            cols = st.columns(len(criteres))
            for col, c in zip(cols, criteres):
                col.info(f"**{c['nom'].replace('_',' ').capitalize()}**\n\n{c['description']}")
    st.divider()


# ─────────────────────────────────────────────
# ÉTAPE 2 : BANC D'ESSAI
# ─────────────────────────────────────────────
if st.session_state.tests:
    tests      = st.session_state.tests
    agent_info = st.session_state.agent_info

    st.header("🧪 Banc d'Essai Automatique")

    # Bouton "Tout évaluer en parallèle"
    all_filled = all(
        bool(st.session_state.get(f"resp_{i}", "").strip())
        for i in range(len(tests))
    )

    if all_filled:
        if st.button("⚡ Évaluer TOUS les tests en parallèle", type="primary", use_container_width=True):
            with st.spinner("Évaluation parallèle des 3 tests simultanément..."):
                responses   = {i: st.session_state.get(f"resp_{i}", "") for i in range(len(tests))}
                new_results = engine.evaluate_all_parallel(tests, responses, agent_info=agent_info)
                st.session_state.results.update(new_results)
                # ✅ Mise à jour de l'historique après ÉVALUATION GLOBALE
                passed = sum(1 for r in st.session_state.results.values() if r.get("status") == "SUCCESS")
                total = len(st.session_state.results)
                pct = int(passed / total * 100) if total else 0

                current_run = {
                    "vibe": st.session_state.vibe_desc[:40],
                    "passed": passed,
                    "total": total,
                    "pct": pct
                }

                st.session_state.history.append(current_run)
            st.rerun()
    else:
        st.info("💡 Remplissez toutes les réponses pour activer l'évaluation groupée (3x plus rapide).")

    st.divider()

    # Tests individuels
    for i, test in enumerate(tests):
        badge = {"NOMINAL": "🟦", "LIMITE": "🟨", "CRITIQUE": "🟥"}.get(test.get("type", ""), "⬜")
        with st.expander(f"{badge} Test #{i+1} : {test['nom']} ({test.get('type', '')})", expanded=True):
            col1, col2 = st.columns([1, 1])

            with col1:
                st.info(f"**Contexte :** {test['contexte']}")
                st.write(f"**Entrée utilisateur :** {test['input_utilisateur']}")
                st.write(f"**Attendu :** {test['attendu']}")

            with col2:
                st.markdown("##### 🎭 Simulation de réponse")
                sim_col1, sim_col2 = st.columns([2, 1])

                with sim_col1:
                    simulation_choice = st.selectbox(
                        "Simuler une réponse :",
                        options=["— Aucune simulation —",
                                 "🤖 Agent Nul (hors-sujet)",
                                 "🚀 Agent Robuste (parfait)"],
                        key=f"sim_{i}"
                    )
                with sim_col2:
                    st.write(""); st.write("")
                    if st.button("⚡ Générer", key=f"sim_btn_{i}", use_container_width=True):
                        if "Nul" in simulation_choice:
                            with st.spinner("Simulation agent nul..."):
                                sim_resp = engine.simulate_agent_response(
                                    test["input_utilisateur"], test["attendu"], mode="nul")
                                st.session_state[f"resp_{i}"] = sim_resp
                                st.rerun()
                        elif "Robuste" in simulation_choice:
                            with st.spinner("Simulation agent robuste..."):
                                sim_resp = engine.simulate_agent_response(
                                    test["input_utilisateur"], test["attendu"], mode="robuste")
                                st.session_state[f"resp_{i}"] = sim_resp
                                st.rerun()
                        else:
                            st.warning("Choisissez un type de simulation d'abord.")

                agent_resp = st.text_area(
                    f"Réponse de votre Agent (#{i+1})",
                    key=f"resp_{i}",
                    help="Collez la réponse de votre agent ici, ou utilisez la simulation."
                )

                if st.button(f"🔎 Évaluer Test #{i+1}", key=f"btn_{i}"):
                    if agent_resp.strip():
                        with st.spinner("Le Juge analyse..."):
                            res = engine.evaluate_run(test, agent_resp, agent_info=agent_info)
                            st.session_state.results[i] = res
                        st.rerun()
                    else:
                        st.warning("Entrez une réponse avant d'évaluer.")

                # Résultat
                if i in st.session_state.results:
                    result    = st.session_state.results[i]
                    status    = result.get("status", "—")
                    score     = result.get("score",  "—")
                    feedback  = result.get("feedback", "")
                    points    = result.get("points_faibles", [])
                    confiance = result.get("confiance", "")
                    scores_d  = result.get("scores_detail", {})

                    if status == "SUCCESS":
                        st.success(f"✅ {status} — Score global : {score}")
                    else:
                        st.error(f"❌ {status} — Score global : {score}")

                    st.write(f"**Feedback :** {feedback}")

                    if points:
                        st.markdown("**⚠️ Points faibles détectés :**")
                        for pt in points:
                            st.caption(f"  • {pt}")

                    if confiance:
                        conf_icon = {"Élevée": "🟢", "Moyenne": "🟡", "Faible": "🔴"}.get(confiance, "⚪")
                        st.caption(f"🧑‍⚖️ Confiance du juge : {conf_icon} {confiance}")

                    if scores_d:
                        st.markdown("**📊 Détail des critères :**")
                        _render_radar(scores_d, key=f"radar_{i}")


# ─────────────────────────────────────────────
# SCORE GLOBAL + EXPORT
# ─────────────────────────────────────────────
if st.session_state.tests and len(st.session_state.results) == len(st.session_state.tests):
    st.divider()
    results = st.session_state.results
    total   = len(st.session_state.tests)
    passed  = sum(1 for r in results.values() if r.get("status") == "SUCCESS")
    pct     = int(passed / total * 100) if total else 0
    verdict = "🟢 Robuste" if pct == 100 else ("🟡 Fragile" if pct >= 50 else "🔴 Instable")

    st.header("📊 Score Global")
    g1, g2, g3 = st.columns(3)
    g1.metric("Tests réussis",    f"{passed}/{total}")
    g2.metric("Taux de réussite", f"{pct}%")
    g3.metric("Verdict",          verdict)
    st.progress(pct / 100)
    st.divider()
    st.header("📈 Rapport d'Amélioration")

    adv_col, export_col = st.columns([2, 1])

    with adv_col:
        if st.button("🪄 Générer des conseils d'optimisation", use_container_width=True):
            with st.spinner("Analyse des faiblesses en cours..."):
                summary = json.dumps(
                    {i: {"status": r.get("status"), "score": r.get("score"),
                         "points_faibles": r.get("points_faibles", [])}
                     for i, r in results.items()},
                    ensure_ascii=False
                )
                tips = engine.get_improvement_tips(
                    st.session_state.vibe_desc, summary,
                    agent_info=st.session_state.agent_info
                )
                st.session_state.tips = tips

    if st.session_state.tips:
        tips = st.session_state.tips
        st.write("### 💡 Conseils pour votre agent :")
        for tip in tips.get("conseils", []):
            st.write(f"- {tip}")
        st.code(tips.get("nouveau_prompt_suggere", ""), language="markdown")

    with export_col:
        if st.button("📄 Exporter le rapport PDF", use_container_width=True):
            with st.spinner("Génération du PDF..."):
                pdf_bytes = engine.build_pdf_report(
                    st.session_state.vibe_desc,
                    st.session_state.tests,
                    st.session_state.results,
                    agent_info=st.session_state.agent_info,
                    tips=st.session_state.tips
                )
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Télécharger le rapport",
                    data=pdf_bytes,
                    file_name="MadyIA_rapport.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error("ReportLab non installé : pip install reportlab")