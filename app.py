import streamlit as st
import engine
import json
import math

# ─────────────────────────────────────────────
# HELPER : RADAR CHART (défini en premier)
# ─────────────────────────────────────────────
def _render_radar(scores_detail: dict, key: str = ""):
    """Affiche un mini radar chart des 3 critères d'évaluation."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np

        labels     = list(scores_detail.keys())
        vals       = [float(scores_detail[k]) for k in labels]
        N          = len(labels)
        angles     = [n / float(N) * 2 * math.pi for n in range(N)]
        angles    += angles[:1]
        vals_plot  = vals + vals[:1]

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
        # Fallback texte si matplotlib absent
        for k, v in scores_detail.items():
            bar = "█" * int(v) + "░" * (10 - int(v))
            st.caption(f"{k.capitalize()}: {bar} {v}/10")


# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(page_title="VibeGuard IA", page_icon="🛡️", layout="wide")

st.title("🛡️ VibeGuard : Sécurisez votre 'Vibe Coding'")
st.subheader("Passez du prototype à l'application robuste sans toucher au code.")

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
for _key, _default in [
    ("tests",      None),
    ("results",    {}),
    ("tips",       None),
    ("ambiguity",  None),
    ("history",    []),
    ("vibe_desc",  ""),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    vibe_desc = st.text_area(
        "Décrivez votre agent (votre 'vibe') :",
        placeholder="Ex: Un bot qui aide les étudiants à trouver un stage en informatique...",
        height=150
    )

    # ── Vérification ambiguïté ──
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

    # ── Génération des tests ──
    if st.button("🚀 Générer le Banc d'Essai", use_container_width=True, type="primary"):
        if vibe_desc.strip():
            with st.spinner("Mistral génère vos scénarios de test..."):
                response = engine.generate_test_suite(vibe_desc)
                st.session_state.tests     = response.get("scenarios", [])
                st.session_state.results   = {}
                st.session_state.tips      = None
                st.session_state.vibe_desc = vibe_desc
                for j in range(10):
                    st.session_state.pop(f"resp_{j}", None)
            st.success(f"✅ {len(st.session_state.tests)} tests générés !")
        else:
            st.warning("Entrez une description d'abord.")

    # ── Historique ──
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
# ÉTAPE 2 : BANC D'ESSAI
# ─────────────────────────────────────────────
if st.session_state.tests:
    tests = st.session_state.tests
    st.header("🧪 Banc d'Essai Automatique")

    # ── Bouton "Tout évaluer en parallèle" ──
    all_filled = all(
        bool(st.session_state.get(f"resp_{i}", "").strip())
        for i in range(len(tests))
    )

    if all_filled:
        if st.button("⚡ Évaluer TOUS les tests en parallèle", type="primary", use_container_width=True):
            with st.spinner("Évaluation parallèle des 3 tests simultanément..."):
                responses   = {i: st.session_state.get(f"resp_{i}", "") for i in range(len(tests))}
                new_results = engine.evaluate_all_parallel(tests, responses)
                st.session_state.results.update(new_results)
            st.rerun()
    else:
        st.info("💡 Remplissez toutes les réponses pour activer l'évaluation groupée (3x plus rapide).")

    st.divider()

    # ── Tests individuels ──
    for i, test in enumerate(tests):
        badge = {"NOMINAL": "🟦", "LIMITE": "🟨", "CRITIQUE": "🟥"}.get(test.get("type", ""), "⬜")
        with st.expander(f"{badge} Test #{i+1} : {test['nom']} ({test.get('type', '')})", expanded=True):
            col1, col2 = st.columns([1, 1])

            with col1:
                st.info(f"**Contexte :** {test['contexte']}")
                st.write(f"**Entrée utilisateur :** {test['input_utilisateur']}")
                st.write(f"**Attendu :** {test['attendu']}")

            with col2:
                # ── Simulation ──
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
                    st.write("")
                    st.write("")
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

                # ── Zone de réponse ──
                agent_resp = st.text_area(
                    f"Réponse de votre Agent (#{i+1})",
                    key=f"resp_{i}",
                    help="Collez la réponse de votre agent ici, ou utilisez la simulation."
                )

                # ── Évaluation individuelle ──
                if st.button(f"🔎 Évaluer Test #{i+1}", key=f"btn_{i}"):
                    if agent_resp.strip():
                        with st.spinner("Le Juge analyse..."):
                            res = engine.evaluate_run(test, agent_resp)
                            st.session_state.results[i] = res
                        st.rerun()
                    else:
                        st.warning("Entrez une réponse avant d'évaluer.")

                # ── Résultat ──
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

                    # Points faibles
                    if points:
                        st.markdown("**⚠️ Points faibles détectés :**")
                        for pt in points:
                            st.caption(f"  • {pt}")

                    # Confiance du juge
                    if confiance:
                        conf_icon = {"Élevée": "🟢", "Moyenne": "🟡", "Faible": "🔴"}.get(confiance, "⚪")
                        st.caption(f"🧑‍⚖️ Confiance du juge : {conf_icon} {confiance}")

                    # Radar chart
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

    # Sauvegarde historique (évite doublons consécutifs)
    current_run = {
        "vibe":   st.session_state.vibe_desc[:40],
        "passed": passed, "total": total, "pct": pct
    }
    if not st.session_state.history or st.session_state.history[-1] != current_run:
        st.session_state.history.append(current_run)

    # ── Amélioration + Export ──
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
                tips = engine.get_improvement_tips(st.session_state.vibe_desc, summary)
                st.session_state.tips = tips

    if st.session_state.tips:
        tips = st.session_state.tips
        st.write("### 💡 Conseils pour votre agent :")
        for tip in tips.get("conseils", []):
            st.write(f"- {tip}")
        st.code(tips.get("nouveau_prompt_suggere", ""), language="markdown")
        st.balloons()

    with export_col:
        if st.button("📄 Exporter le rapport PDF", use_container_width=True):
            with st.spinner("Génération du PDF..."):
                pdf_bytes = engine.build_pdf_report(
                    st.session_state.vibe_desc,
                    st.session_state.tests,
                    st.session_state.results,
                    tips=st.session_state.tips
                )
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Télécharger le rapport",
                    data=pdf_bytes,
                    file_name="vibeguard_rapport.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.error("ReportLab non installé. Lancez : pip install reportlab --break-system-packages")