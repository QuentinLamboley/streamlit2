import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Configuration de la page
st.set_page_config(page_title="Planning de disponibilités", layout="wide")

# Fichier de sauvegarde des disponibilités
DATA_FILE = "disponibilites.csv"

# Fonction pour charger les disponibilités existantes
def charger_disponibilites():
    try:
        return pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["Nom", "Date", "Heure"])

# Fonction pour sauvegarder les disponibilités
def sauvegarder_disponibilites(df):
    df.to_csv(DATA_FILE, index=False)

# Générer les dates du calendrier (hors week-ends)
def generer_dates():
    dates = []
    # Période 1 : 17 au 28 février (hors week-ends)
    start_date1 = datetime(2025, 2, 17)
    end_date1 = datetime(2025, 2, 28)

    # Période 2 : 10 au 31 mars (hors week-ends)
    start_date2 = datetime(2025, 3, 10)
    end_date2 = datetime(2025, 3, 31)

    # Générer les dates en excluant les week-ends
    date = start_date1
    while date <= end_date1:
        if date.weekday() < 5:  # 0 = Lundi, 4 = Vendredi
            dates.append(date.strftime("%Y-%m-%d"))
        date += timedelta(days=1)

    date = start_date2
    while date <= end_date2:
        if date.weekday() < 5:
            dates.append(date.strftime("%Y-%m-%d"))
        date += timedelta(days=1)

    return dates

# Générer les créneaux horaires (de 10h à 20h, toutes les 30 minutes)
def generer_horaires():
    horaires = []
    for heure in range(10, 20):
        horaires.append(f"{heure:02d}:00 - {heure:02d}:30")
        horaires.append(f"{heure:02d}:30 - {heure+1:02d}:00")
    return horaires

# Interface principale
st.title("🗓️ Sélectionnez vos disponibilités")

nom = st.text_input("✏️ Entrez votre nom :", "")

# Chargement des créneaux et des dates
dates = generer_dates()
horaires = generer_horaires()

# Sélection des créneaux
selected_dates = st.multiselect("📅 Sélectionnez vos jours :", dates)
selected_hours = st.multiselect("⏰ Sélectionnez vos horaires :", horaires)

# Sauvegarde des disponibilités
if st.button("✅ Enregistrer mes disponibilités"):
    if nom and selected_dates and selected_hours:
        df = charger_disponibilites()
        new_entries = [{"Nom": nom, "Date": date, "Heure": heure} for date in selected_dates for heure in selected_hours]
        new_data = pd.DataFrame(new_entries)
        df = pd.concat([df, new_data], ignore_index=True)
        sauvegarder_disponibilites(df)
        st.success("📝 Vos disponibilités ont été enregistrées !")
    else:
        st.warning("⚠️ Veuillez remplir tous les champs avant d'enregistrer.")

# Affichage des disponibilités individuelles
if nom:
    st.subheader(f"📋 Vos disponibilités ({nom})")
    df = charger_disponibilites()
    df_user = df[df["Nom"] == nom]
    if not df_user.empty:
        st.dataframe(df_user)
    else:
        st.info("Aucune disponibilité enregistrée pour vous.")

# Section Admin (pour l'organisateur uniquement)
administrateur = st.text_input("🔑 Entrez le mot de passe administrateur :", type="password")
if administrateur == "monmotdepasse":  # Remplace "monmotdepasse" par ton mot de passe
    st.subheader("📊 Disponibilités enregistrées (Admin seulement)")
    df = charger_disponibilites()
    st.dataframe(df)
    st.download_button("📥 Télécharger les disponibilités", df.to_csv(index=False), "disponibilites.csv", "text/csv")
