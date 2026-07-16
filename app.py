import json
import random
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).parent
DATA_DIR = APP_DIR / "data"
QUESTIONS_FILE = DATA_DIR / "questions.json"
RESULTS_FILE = DATA_DIR / "results.json"

TOEIC_CATEGORIES = [
    "TOEIC - Grammaire",
    "TOEIC - Collocations",
    "TOEIC - Conditionnels",
    "TOEIC - Part II",
    "TOEIC - Mots fréquents et prépositions",
]

TOEIC_DISTRIBUTION = {
    "TOEIC - Grammaire": 0.32,
    "TOEIC - Collocations": 0.18,
    "TOEIC - Conditionnels": 0.15,
    "TOEIC - Part II": 0.20,
    "TOEIC - Mots fréquents et prépositions": 0.15,
}

st.set_page_config(
    page_title="Quiz anglais MAALSI et TOEIC",
    page_icon="🎓",
    layout="wide",
)


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not RESULTS_FILE.exists():
        RESULTS_FILE.write_text("[]", encoding="utf-8")


def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        st.error(f"Fichier introuvable : {path}")
        st.stop()
    except json.JSONDecodeError as exc:
        st.error(f"Le fichier {path.name} contient un JSON invalide : {exc}")
        st.stop()
    return default


def load_questions() -> list[dict]:
    questions = load_json(QUESTIONS_FILE, [])
    if not isinstance(questions, list) or not questions:
        st.error("La banque de questions est vide ou invalide.")
        st.stop()
    return questions


def load_results() -> list[dict]:
    results = load_json(RESULTS_FILE, [])
    return results if isinstance(results, list) else []


def save_results(results: list[dict]) -> None:
    with RESULTS_FILE.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)


def question_section(question: dict) -> str:
    if question.get("section"):
        return question["section"]
    return "TOEIC" if question.get("category", "").startswith("TOEIC") else "MAALSI"


def make_options(question: dict, pool: list[dict]) -> list[str]:
    prepared_options = question.get("options")
    if prepared_options:
        options = list(dict.fromkeys(prepared_options))
        if question["answer"] not in options:
            options.append(question["answer"])
        random.shuffle(options)
        return options

    same_category_answers = list(
        dict.fromkeys(
            q["answer"]
            for q in pool
            if q["id"] != question["id"]
            and q.get("category") == question.get("category")
            and q.get("answer") != question.get("answer")
        )
    )

    candidates = same_category_answers
    if len(candidates) < 3:
        candidates = list(
            dict.fromkeys(
                q["answer"]
                for q in pool
                if q["id"] != question["id"]
                and q.get("answer") != question.get("answer")
            )
        )

    wrong_count = min(3, len(candidates))
    wrong_answers = random.sample(candidates, wrong_count)
    options = wrong_answers + [question["answer"]]
    random.shuffle(options)
    return options


def grade_label(score_percent: float) -> str:
    if score_percent >= 90:
        return "Excellent"
    if score_percent >= 75:
        return "Bon niveau"
    if score_percent >= 60:
        return "À consolider"
    return "Révision nécessaire"


def clear_answer_widgets() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("answer_"):
            del st.session_state[key]


def build_quiz(selected: list[dict], all_questions: list[dict]) -> list[dict]:
    quiz = []
    for question in selected:
        quiz.append({**question, "runtime_options": make_options(question, all_questions)})
    return quiz


def start_quiz(selected: list[dict], all_questions: list[dict], mode: str) -> None:
    clear_answer_widgets()
    st.session_state.quiz = build_quiz(selected, all_questions)
    st.session_state.quiz_mode = mode
    st.session_state.start_time = time.time()
    st.session_state.last_result = None
    st.session_state.last_review = None
    st.rerun()


def balanced_toeic_sample(toeic_questions: list[dict], total: int) -> list[dict]:
    by_category = {
        category: [q for q in toeic_questions if q.get("category") == category]
        for category in TOEIC_CATEGORIES
    }

    requested = {
        category: int(total * TOEIC_DISTRIBUTION[category])
        for category in TOEIC_CATEGORIES
    }

    allocated = sum(requested.values())
    remaining = total - allocated
    category_order = sorted(
        TOEIC_CATEGORIES,
        key=lambda category: TOEIC_DISTRIBUTION[category],
        reverse=True,
    )

    for category in category_order:
        if remaining <= 0:
            break
        requested[category] += 1
        remaining -= 1

    selected: list[dict] = []
    unused: list[dict] = []

    for category in TOEIC_CATEGORIES:
        available = by_category[category]
        take = min(requested[category], len(available))
        selected.extend(random.sample(available, take))
        selected_ids = {q["id"] for q in selected}
        unused.extend(q for q in available if q["id"] not in selected_ids)

    if len(selected) < total:
        selected_ids = {q["id"] for q in selected}
        remaining_pool = [q for q in toeic_questions if q["id"] not in selected_ids]
        selected.extend(random.sample(remaining_pool, min(total - len(selected), len(remaining_pool))))

    random.shuffle(selected)
    return selected[:total]


def render_question(question: dict, index: int, total: int) -> None:
    st.markdown(f"### Question {index}/{total}")

    meta_col1, meta_col2 = st.columns([3, 1])
    with meta_col1:
        st.caption(question.get("category", "Sans catégorie"))
    with meta_col2:
        st.caption(question.get("difficulty", "Non précisé"))

    question_type = question.get("question_type")
    prompt = question.get("prompt", "")

    if question_type == "definition_to_term":
        st.info(prompt)
        st.write("Quel terme anglais correspond à cette définition ?")
    elif question_type == "fr_to_en":
        st.write(f"Traduction anglaise de : **{prompt}**")
    elif question_type == "toeic_part2":
        st.info(prompt)
        st.write("Choisis la réponse la plus logique.")
    else:
        st.info(prompt)
        st.write("Choisis la meilleure réponse.")

    st.radio(
        "Réponse",
        question["runtime_options"],
        key=f"answer_{index}_{question['id']}",
        index=None,
        label_visibility="collapsed",
    )
    st.divider()


def finish_current_quiz(results: list[dict]) -> None:
    quiz = st.session_state.quiz
    review_rows = []
    errors = []
    correct = 0

    for index, question in enumerate(quiz, start=1):
        user_answer = st.session_state.get(f"answer_{index}_{question['id']}")
        is_correct = user_answer == question["answer"]
        if is_correct:
            correct += 1

        review_row = {
            "question_id": question["id"],
            "category": question.get("category", ""),
            "prompt": question.get("prompt", ""),
            "user_answer": user_answer or "Aucune réponse",
            "correct_answer": question["answer"],
            "correct": is_correct,
            "explanation": question.get("explanation", ""),
        }
        review_rows.append(review_row)

        if not is_correct:
            errors.append(review_row)

    total = len(quiz)
    score_percent = round(correct / total * 100, 2) if total else 0
    duration_seconds = int(time.time() - st.session_state.start_time)
    sections = sorted({question_section(q) for q in quiz})

    session = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": st.session_state.get("quiz_mode", "Quiz libre"),
        "sections": sections,
        "total": total,
        "correct": correct,
        "wrong": total - correct,
        "score_percent": score_percent,
        "grade": grade_label(score_percent),
        "duration_seconds": duration_seconds,
        "categories": sorted({q.get("category", "") for q in quiz}),
        "errors": errors,
    }

    results.append(session)
    save_results(results)

    st.session_state.last_result = session
    st.session_state.last_review = review_rows
    st.session_state.quiz = None
    clear_answer_widgets()
    st.rerun()


def render_last_result() -> None:
    result = st.session_state.get("last_result")
    review = st.session_state.get("last_review")
    if not result:
        return

    st.subheader("Résultat du dernier test")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Score", f"{result['score_percent']} %")
    c2.metric("Bonnes réponses", result["correct"])
    c3.metric("Erreurs", result["wrong"])
    c4.metric("Durée", f"{result['duration_seconds']} s")
    c5.metric("Niveau", result["grade"])

    if review:
        errors_only = st.checkbox("Afficher uniquement les erreurs", value=True, key="last_errors_only")
        rows = [row for row in review if not row["correct"]] if errors_only else review

        if rows:
            for number, row in enumerate(rows, start=1):
                status = "✅" if row["correct"] else "❌"
                with st.expander(f"{status} {number}. {row['prompt']}"):
                    st.write(f"**Ta réponse :** {row['user_answer']}")
                    st.write(f"**Bonne réponse :** {row['correct_answer']}")
                    if row.get("explanation"):
                        st.info(row["explanation"])
        else:
            st.success("Aucune erreur dans ce test.")


def safe_results_dataframe(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    defaults = {
        "mode": "Quiz libre",
        "sections": [[] for _ in range(len(df))],
        "total": 0,
        "correct": 0,
        "wrong": 0,
        "score_percent": 0.0,
        "grade": "",
        "duration_seconds": 0,
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
    return df


ensure_data_files()
questions = load_questions()
results = load_results()

if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "quiz_mode" not in st.session_state:
    st.session_state.quiz_mode = "Quiz libre"
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "last_review" not in st.session_state:
    st.session_state.last_review = None

st.title("🎓 Quiz anglais — MAALSI et préparation TOEIC")
st.caption("Vocabulaire métier, grammaire TOEIC, collocations, conditionnels et entraînement Part II.")

page = st.sidebar.radio(
    "Navigation",
    [
        "Lancer un quiz",
        "Simulation TOEIC",
        "Statistiques",
        "Erreurs à réviser",
        "Fiches TOEIC",
        "Banque de questions",
    ],
)

if st.session_state.quiz and page not in {"Lancer un quiz", "Simulation TOEIC"}:
    st.sidebar.warning("Un test est en cours. Retourne sur la page du test pour le terminer.")

if page == "Lancer un quiz":
    st.header("Lancer un quiz personnalisé")

    family = st.selectbox(
        "Type de préparation",
        ["Toutes les questions", "Vocabulaire MAALSI", "Préparation TOEIC"],
    )

    filtered = questions
    if family == "Vocabulaire MAALSI":
        filtered = [q for q in questions if question_section(q) == "MAALSI"]
    elif family == "Préparation TOEIC":
        filtered = [q for q in questions if question_section(q) == "TOEIC"]

    available_categories = ["Toutes"] + sorted({q.get("category", "") for q in filtered})

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        category = st.selectbox("Catégorie", available_categories)
    with col2:
        difficulties = ["Toutes"] + sorted({q.get("difficulty", "Non précisé") for q in filtered})
        difficulty = st.selectbox("Difficulté", difficulties)
    with col3:
        review_only = st.checkbox("Réviser seulement mes erreurs")
    with col4:
        random_order = st.checkbox("Ordre aléatoire", value=True)

    available = filtered
    if category != "Toutes":
        available = [q for q in available if q.get("category") == category]
    if difficulty != "Toutes":
        available = [q for q in available if q.get("difficulty", "Non précisé") == difficulty]

    if review_only:
        missed_ids = {
            error.get("question_id")
            for result in results
            for error in result.get("errors", [])
        }
        available = [q for q in available if q.get("id") in missed_ids]

    if available:
        min_questions = 1 if len(available) < 5 else 5
        default_questions = min(20, len(available))
        nb_questions = st.slider(
            "Nombre de questions",
            min_value=min_questions,
            max_value=len(available),
            value=max(min_questions, default_questions),
        )
    else:
        nb_questions = 0
        st.info("Aucune question ne correspond à ces filtres.")

    if st.button("Démarrer le quiz", type="primary", disabled=not available):
        selected = random.sample(available, nb_questions) if random_order else available[:nb_questions]
        start_quiz(selected, questions, "Quiz personnalisé")

    if st.session_state.quiz and st.session_state.quiz_mode == "Quiz personnalisé":
        st.divider()
        st.subheader("Test en cours")
        elapsed = int(time.time() - st.session_state.start_time)
        st.caption(f"Temps écoulé au dernier affichage : {elapsed} secondes")

        for idx, question in enumerate(st.session_state.quiz, start=1):
            render_question(question, idx, len(st.session_state.quiz))

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Terminer et corriger", type="primary"):
                finish_current_quiz(results)
        with c2:
            if st.button("Annuler le test"):
                st.session_state.quiz = None
                clear_answer_widgets()
                st.rerun()

    render_last_result()

elif page == "Simulation TOEIC":
    st.header("Simulation TOEIC")
    st.write(
        "Cette simulation mélange les cinq catégories TOEIC selon une répartition équilibrée. "
        "Le score est un indicateur de préparation et non une conversion officielle du score TOEIC."
    )

    toeic_questions = [q for q in questions if question_section(q) == "TOEIC"]
    available_sizes = [size for size in [20, 40, 60, 100] if size <= len(toeic_questions)]
    simulation_size = st.select_slider(
        "Nombre de questions",
        options=available_sizes,
        value=available_sizes[0] if available_sizes else 20,
    )

    expected_minutes = max(10, round(simulation_size * 0.75))
    st.info(f"Temps conseillé : environ {expected_minutes} minutes.")

    distribution_preview = {
        category.replace("TOEIC - ", ""): round(simulation_size * weight)
        for category, weight in TOEIC_DISTRIBUTION.items()
    }
    st.write("Répartition approximative :", distribution_preview)

    if st.button("Démarrer la simulation", type="primary", disabled=not toeic_questions):
        selected = balanced_toeic_sample(toeic_questions, simulation_size)
        start_quiz(selected, questions, "Simulation TOEIC")

    if st.session_state.quiz and st.session_state.quiz_mode == "Simulation TOEIC":
        st.divider()
        st.subheader("Simulation en cours")
        elapsed = int(time.time() - st.session_state.start_time)
        st.caption(f"Temps écoulé au dernier affichage : {elapsed} secondes")

        for idx, question in enumerate(st.session_state.quiz, start=1):
            render_question(question, idx, len(st.session_state.quiz))

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Terminer la simulation", type="primary"):
                finish_current_quiz(results)
        with c2:
            if st.button("Annuler la simulation"):
                st.session_state.quiz = None
                clear_answer_widgets()
                st.rerun()

    render_last_result()

elif page == "Statistiques":
    st.header("Statistiques")
    df = safe_results_dataframe(results)

    if df.empty:
        st.info("Aucun test terminé pour le moment.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tests réalisés", len(df))
        c2.metric("Meilleur score", f"{df['score_percent'].max():.2f} %")
        c3.metric("Score moyen", f"{df['score_percent'].mean():.2f} %")
        c4.metric("Total erreurs", int(df["wrong"].sum()))

        st.subheader("Progression")
        progress = df[["date", "score_percent"]].copy()
        progress["date"] = pd.to_datetime(progress["date"], errors="coerce")
        progress = progress.dropna().set_index("date")
        st.line_chart(progress)

        st.subheader("Historique")
        display_columns = [
            "date",
            "mode",
            "total",
            "correct",
            "wrong",
            "score_percent",
            "grade",
            "duration_seconds",
        ]
        st.dataframe(df[display_columns], use_container_width=True, hide_index=True)

        all_errors = [error for result in results for error in result.get("errors", [])]
        st.subheader("Erreurs par catégorie")
        if all_errors:
            error_df = pd.DataFrame(all_errors)
            st.bar_chart(error_df["category"].value_counts())
        else:
            st.success("Aucune erreur enregistrée.")

elif page == "Erreurs à réviser":
    st.header("Erreurs à réviser")
    all_errors = [error for result in results for error in result.get("errors", [])]

    if not all_errors:
        st.info("Aucune erreur enregistrée.")
    else:
        error_df = pd.DataFrame(all_errors)
        selected_error_category = st.selectbox(
            "Filtrer par catégorie",
            ["Toutes"] + sorted(error_df["category"].dropna().unique().tolist()),
        )
        if selected_error_category != "Toutes":
            error_df = error_df[error_df["category"] == selected_error_category]

        st.dataframe(
            error_df[
                [
                    "category",
                    "prompt",
                    "user_answer",
                    "correct_answer",
                    "explanation",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Questions les plus souvent ratées")
        frequency = (
            error_df.groupby(["question_id", "prompt", "correct_answer"], dropna=False)
            .size()
            .reset_index(name="nombre_erreurs")
            .sort_values("nombre_erreurs", ascending=False)
        )
        st.dataframe(frequency, use_container_width=True, hide_index=True)

elif page == "Fiches TOEIC":
    st.header("Fiches de révision TOEIC")

    with st.expander("Part II — éviter les pièges", expanded=True):
        st.markdown(
            """
- Écoute le premier mot : **Who, Where, When, Why, How, Which**.
- Ne choisis pas une réponse uniquement parce qu'elle répète un mot de la question.
- Méfie-toi des mots proches : **coffee/copy**, **flu/flew**, **waste/waist**.
- Une réponse indirecte peut être correcte : *Do you know when he will arrive? — His flight was delayed.*
            """
        )

    with st.expander("Conditionnels"):
        st.markdown(
            """
- **Zero** : if + présent → présent. Fait toujours vrai.
- **First** : if + présent → will + verbe. Futur possible.
- **Second** : if + prétérit → would + verbe. Situation hypothétique.
- **Third** : if + past perfect → would have + participe passé. Passé impossible à changer.
            """
        )

    with st.expander("Collocations à connaître"):
        st.markdown(
            """
- make a decision
- reach an agreement
- hold / attend / schedule a meeting
- meet / miss a deadline
- launch a product
- have an impact
- build partnerships
- submit a report
- take measures
- resolve an issue
            """
        )

    with st.expander("Prépositions fréquentes"):
        st.markdown(
            """
- responsible **for**
- interested **in**
- familiar **with**
- capable **of**
- satisfied **with**
- concerned **about**
- involved **in**
- available **for**
- comply **with**
- committed **to + -ing**
            """
        )

    with st.expander("Pièges de grammaire"):
        st.markdown(
            """
- plan / promise / decide **to do**
- avoid / imagine / mind **doing**
- **stop doing** = arrêter une activité ; **stop to do** = s'arrêter pour faire quelque chose
- information, furniture, advice, equipment : noms indénombrables au singulier
- interested = sentiment ; interesting = ce qui provoque le sentiment
- by = au plus tard ; until = jusqu'à
            """
        )

elif page == "Banque de questions":
    st.header("Banque de questions")

    bank_family = st.selectbox(
        "Type",
        ["Toutes", "MAALSI", "TOEIC"],
        key="bank_family",
    )
    bank_questions = questions
    if bank_family != "Toutes":
        bank_questions = [q for q in questions if question_section(q) == bank_family]

    bank_categories = ["Toutes"] + sorted({q.get("category", "") for q in bank_questions})
    bank_category = st.selectbox("Catégorie", bank_categories, key="bank_category")
    if bank_category != "Toutes":
        bank_questions = [q for q in bank_questions if q.get("category") == bank_category]

    bank_df = pd.DataFrame(bank_questions)
    columns = [column for column in ["id", "section", "category", "difficulty", "prompt", "answer", "explanation"] if column in bank_df.columns]
    st.dataframe(bank_df[columns], use_container_width=True, hide_index=True)

    st.write(f"**{len(bank_questions)} question(s) affichée(s) sur {len(questions)}.**")

    st.download_button(
        "Télécharger toute la banque JSON",
        data=json.dumps(questions, ensure_ascii=False, indent=2),
        file_name="questions.json",
        mime="application/json",
    )
