# Quiz vocabulaire anglais MAALSI

Application Streamlit générée à partir du document **Consignes - Vocabulaire anglais - MAALSI A4.pdf**.

## Fonctionnalités

- Quiz QCU avec 4 propositions
- Mots métier : français → anglais
- Expressions métier : français → anglais
- Définitions : définition anglaise → terme anglais
- Score à la fin de chaque test
- Historique des tests
- Statistiques de réussite
- Liste détaillée des erreurs
- Mode révision des erreurs

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Données

- `data/questions.json` : banque de questions
- `data/results.json` : historique local des résultats

Pour remettre les statistiques à zéro, vide le fichier `data/results.json` et remplace son contenu par :

```json
[]
```
