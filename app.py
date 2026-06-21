
import json
import random
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
QUESTIONS_FILE = DATA_DIR / "questions.json"
RESULTS_FILE = DATA_DIR / "results.json"

st.set_page_config(
    page_title="Quiz vocabulaire anglais MAALSI",
    page_icon="🎓",
    layout="wide"
)

def load_questions():
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_results():
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("[]", encoding="utf-8")
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_results(results):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def make_options(question, pool):
    candidates = [q["answer"] for q in pool if q["id"] != question["id"] and q["category"] == question["category"]]
    if len(candidates) < 3:
        candidates = [q["answer"] for q in pool if q["id"] != question["id"]]
    wrong = random.sample(candidates, min(3, len(candidates)))
    options = wrong + [question["answer"]]
    random.shuffle(options)
    return options

def grade_label(score_percent):
    # Barème du document : A=100-125, B=75-99, C=50-74, D=0-49 mots validés.
    # Adapté ici en pourcentage.
    if score_percent >= 80:
        return "A"
    if score_percent >= 60:
        return "B"
    if score_percent >= 40:
        return "C"
    return "D"

questions = load_questions()
results = load_results()

st.title("🎓 Quiz vocabulaire anglais — MAALSI")
st.caption("Préparation QCU : mots métier, expressions métier et définitions.")

page = st.sidebar.radio(
    "Navigation",
    ["Lancer un test", "Statistiques", "Erreurs à réviser", "Banque de questions"]
)

categories = ["Toutes"] + sorted({q["category"] for q in questions})

if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "answers" not in st.session_state:
    st.session_state.answers = {}
if "start_time" not in st.session_state:
    st.session_state.start_time = None

if page == "Lancer un test":
    st.header("Lancer un test")

    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.selectbox("Catégorie", categories)
    with col2:
        max_q = len(questions) if category == "Toutes" else len([q for q in questions if q["category"] == category])
        nb_questions = st.slider("Nombre de questions", 5, max_q, min(20, max_q))
    with col3:
        review_only = st.checkbox("Mode révision erreurs")

    available = questions
    if category != "Toutes":
        available = [q for q in available if q["category"] == category]

    if review_only:
        missed_ids = set()
        for r in results:
            for e in r.get("errors", []):
                missed_ids.add(e["question_id"])
        available = [q for q in available if q["id"] in missed_ids]
        if not available:
            st.info("Aucune erreur enregistrée pour cette catégorie. Lance d’abord un test classique.")

    if st.button("Démarrer un nouveau test", type="primary", disabled=not available):
        selected = random.sample(available, min(nb_questions, len(available)))
        quiz = []
        for q in selected:
            quiz.append({**q, "options": make_options(q, questions)})
        st.session_state.quiz = quiz
        st.session_state.answers = {}
        st.session_state.start_time = time.time()
        st.rerun()

    if st.session_state.quiz:
        st.divider()
        st.subheader("Test en cours")

        for idx, q in enumerate(st.session_state.quiz, start=1):
            st.markdown(f"### Question {idx}/{len(st.session_state.quiz)}")
            st.write(f"**Catégorie :** {q['category']}")
            if q["question_type"] == "definition_to_term":
                st.info(q["prompt"])
                st.write("Quel terme anglais correspond à cette définition ?")
            else:
                st.write(f"Traduction anglaise de : **{q['prompt']}**")

            st.radio(
                "Choisis une réponse",
                q["options"],
                key=f"answer_{q['id']}",
                index=None
            )
            st.divider()

        if st.button("Terminer le test", type="primary"):
            quiz = st.session_state.quiz
            answers = {}
            errors = []
            correct = 0

            for q in quiz:
                user_answer = st.session_state.get(f"answer_{q['id']}")
                answers[q["id"]] = user_answer
                is_correct = user_answer == q["answer"]
                if is_correct:
                    correct += 1
                else:
                    errors.append({
                        "question_id": q["id"],
                        "category": q["category"],
                        "prompt": q["prompt"],
                        "user_answer": user_answer or "Aucune réponse",
                        "correct_answer": q["answer"]
                    })

            total = len(quiz)
            score_percent = round(correct / total * 100, 2) if total else 0
            duration_seconds = int(time.time() - st.session_state.start_time)

            session = {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total": total,
                "correct": correct,
                "wrong": total - correct,
                "score_percent": score_percent,
                "grade": grade_label(score_percent),
                "duration_seconds": duration_seconds,
                "categories": sorted(list({q["category"] for q in quiz})),
                "errors": errors
            }
            results.append(session)
            save_results(results)

            st.session_state.last_result = session
            st.session_state.quiz = None
            st.session_state.answers = {}
            st.success("Test terminé.")
            st.rerun()

    if "last_result" in st.session_state:
        r = st.session_state.last_result
        st.subheader("Résultat du dernier test")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score", f"{r['score_percent']} %")
        c2.metric("Bonnes réponses", r["correct"])
        c3.metric("Erreurs", r["wrong"])
        c4.metric("Note estimée", r["grade"])

        if r["errors"]:
            st.error("Questions à revoir")
            st.dataframe(pd.DataFrame(r["errors"]), use_container_width=True)
        else:
            st.balloons()
            st.success("Aucune erreur.")

elif page == "Statistiques":
    st.header("Statistiques")

    if not results:
        st.info("Aucun test terminé pour le moment.")
    else:
        df = pd.DataFrame(results)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tests réalisés", len(df))
        c2.metric("Meilleur score", f"{df['score_percent'].max():.2f} %")
        c3.metric("Score moyen", f"{df['score_percent'].mean():.2f} %")
        c4.metric("Total erreurs", int(df["wrong"].sum()))

        st.subheader("Progression")
        progress = df[["date", "score_percent"]].copy()
        progress = progress.set_index("date")
        st.line_chart(progress)

        st.subheader("Historique")
        st.dataframe(
            df[["date", "total", "correct", "wrong", "score_percent", "grade", "duration_seconds"]],
            use_container_width=True
        )

        st.subheader("Erreurs par catégorie")
        all_errors = [e for r in results for e in r.get("errors", [])]
        if all_errors:
            err_df = pd.DataFrame(all_errors)
            st.bar_chart(err_df["category"].value_counts())
        else:
            st.success("Aucune erreur enregistrée.")

elif page == "Erreurs à réviser":
    st.header("Erreurs à réviser")

    all_errors = [e for r in results for e in r.get("errors", [])]
    if not all_errors:
        st.info("Aucune erreur enregistrée.")
    else:
        err_df = pd.DataFrame(all_errors)
        st.write("Les erreurs les plus récentes sont listées ci-dessous.")
        st.dataframe(err_df, use_container_width=True)

        st.subheader("Fréquence des erreurs")
        freq = err_df.groupby(["question_id", "prompt", "correct_answer"]).size().reset_index(name="nombre_erreurs")
        freq = freq.sort_values("nombre_erreurs", ascending=False)
        st.dataframe(freq, use_container_width=True)

elif page == "Banque de questions":
    st.header("Banque de questions")
    df = pd.DataFrame(questions)
    selected_category = st.selectbox("Filtrer", categories)
    if selected_category != "Toutes":
        df = df[df["category"] == selected_category]
    st.dataframe(df[["id", "category", "prompt", "answer"]], use_container_width=True)

    st.download_button(
        "Télécharger la banque de questions JSON",
        data=json.dumps(questions, ensure_ascii=False, indent=2),
        file_name="questions_vocab_anglais.json",
        mime="application/json"
    )
