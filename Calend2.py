import streamlit as st
import pandas as pd
import requests
import dropbox
from io import BytesIO
from datetime import datetime, timedelta

# 🔑 Connexion Dropbox (à changer avant prod)
DROPBOX_APP_KEY = "siecwy4rj0ijazf"
DROPBOX_APP_SECRET = "o66gnhdiu214b1c"
DROPBOX_REFRESH_TOKEN = "RryShEoBZ6oAAAAAAAAAAT8ZxBNJh6eM2RhROBKI61AxFnD-6wBOh2nLYbpsNk68"

def get_dropbox_access_token():
    url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": DROPBOX_REFRESH_TOKEN,
        "client_id": DROPBOX_APP_KEY,
        "client_secret": DROPBOX_APP_SECRET,
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        st.error(f"⚠️ Erreur de renouvellement du token Dropbox : {response.json()}")

DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
if not DROPBOX_ACCESS_TOKEN:
    st.error("❌ Impossible de récupérer un Access Token valide.")
    st.stop()

dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
DROPBOX_FILE_PATH = "/Creneau.xlsx"

def load_reservations():
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        df = pd.read_excel(BytesIO(res.content), engine="openpyxl", dtype={"Téléphone": str})  
        # S'assure que les colonnes existent
        for col in ["Prénom", "Nom", "Date", "Plage"]:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception:
        # Toujours créer un df avec les bonnes colonnes
        return pd.DataFrame(columns=["Prénom", "Nom", "Date", "Plage"])

def save_reservations(df):
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        dbx.files_upload(output.read(), DROPBOX_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")

# ✅ Générer les week-ends d'août 2025 (hors 2 et 9 août)
def get_august_2025_weekends():
    weekends = []
    start = datetime(2025, 8, 1)
    end = datetime(2025, 8, 31)
    delta = timedelta(days=1)
    exclude_dates = [datetime(2025, 8, 2).date(), datetime(2025, 8, 9).date()]
    while start <= end:
        if start.weekday() in [5, 6] and start.date() not in exclude_dates:
            weekends.append(start.date())
        start += delta
    return weekends

# ✅ Créneaux midi/soir
CRENEAUX = ["midi", "soir"]

# ✅ Enregistrer plusieurs réservations (anti-doublon)
def save_reservations_multi(prenom, nom, selections):
    df = load_reservations()
    nb_ajoute = 0
    doublons = []
    for date, plage in selections:
        # On vérifie les doublons exacts
        mask = (
            (df["Prénom"] == prenom) &
            (df["Nom"] == nom) &
            (df["Date"] == date) &
            (df["Plage"] == plage)
        )
        if mask.any():
            doublons.append(f"{date} ({plage})")
            continue
        # Ajout dans le DataFrame
        new_row = pd.DataFrame([[prenom, nom, date, plage]], columns=["Prénom", "Nom", "Date", "Plage"])
        df = pd.concat([df, new_row], ignore_index=True)
        nb_ajoute += 1
    save_reservations(df)
    return nb_ajoute, doublons

# ✅ Supprimer une réservation spécifique
def delete_reservation(prenom, nom, date, plage):
    df = load_reservations()
    df = df[~((df["Prénom"] == prenom) & (df["Nom"] == nom) & (df["Date"] == date) & (df["Plage"] == plage))]
    save_reservations(df)

# ✅ Réinitialiser toutes les réservations (Admin)
def delete_all_reservations(password):
    if password == "DeleteAll":
        save_reservations(pd.DataFrame(columns=["Prénom", "Nom", "Date", "Plage"]))
        st.success("✅ Toutes les réservations ont été supprimées avec succès.")
    else:
        st.error("❌ Mot de passe incorrect.")

st.set_page_config(page_title="Calendar Tool", layout="centered")
st.markdown("""<h1 style='text-align: center; background-color: #004466; padding: 15px; border-radius: 10px; color: white;'>
📆 Reservations tool</h1>""", unsafe_allow_html=True)
st.markdown("### **Créneau pour la cousinade** 📝")

col1, col2 = st.columns(2)
prenom = col1.text_input("👩 Prénom")
nom = col2.text_input("👤 Nom")

dates_options = get_august_2025_weekends()
date_str_options = [date.strftime("%Y-%m-%d") for date in dates_options]

# Sélection multiple (combinaisons date/plage)
options = []
for date in date_str_options:
    for plage in CRENEAUX:
        options.append(f"{date} - {plage}")

selections = st.multiselect("📅 Sélectionnez un ou plusieurs créneaux (date + plage)", options)

# Conversion des sélections en tuples (date, plage)
selections_tuples = []
for sel in selections:
    try:
        date, plage = sel.split(" - ")
        selections_tuples.append((date, plage))
    except:
        pass

if st.button("✅ Valider la réservation"):
    if not prenom or not nom or not selections_tuples:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        nb_ajoute, doublons = save_reservations_multi(prenom, nom, selections_tuples)
        msg = ""
        if nb_ajoute:
            msg += f"✅ {nb_ajoute} réservation(s) ajoutée(s) pour {prenom} {nom} !\n"
        if doublons:
            msg += "⚠️ Créneau(x) déjà réservé(s) (pas ajoutés) : " + ", ".join(doublons)
        st.success(msg if msg else "Aucune réservation ajoutée.")

# ✅ Affichage des réservations existantes
st.markdown("---")
st.markdown("### 📊 **Réservations existantes**")

df_reservations = load_reservations()

if not df_reservations.empty:
    df_reservations["NomComplet"] = df_reservations["Prénom"].astype(str) + " " + df_reservations["Nom"].astype(str)
    st.dataframe(df_reservations[["NomComplet", "Date", "Plage"]])

# ✅ Suppression des créneaux individuels
st.markdown("---")
st.markdown("### ❌ **Supprimer un créneau réservé**")

if not df_reservations.empty:
    user = st.text_input("Entrez votre prénom et nom", placeholder="Ex: Jean Dupont")
    user_reservations = df_reservations[df_reservations["NomComplet"] == user]
    if not user_reservations.empty:
        user_res_list = user_reservations["Date"] + " - " + user_reservations["Plage"]
        selected_reservations = st.multiselect("📅 Sélectionnez les créneaux à supprimer", user_res_list)
        if st.button("🗑️ Supprimer les créneaux sélectionnés"):
            for reservation in selected_reservations:
                jour, plage = reservation.split(" - ")
                delete_reservation(*user.split(), jour, plage)
            st.success("✅ Créneaux supprimés.")

# ✅ Réinitialisation des créneaux (Admin)
st.markdown("---")
admin_password = st.text_input("🔑 Mot de passe admin", type="password")
if st.button("❌ Supprimer TOUTES les réservations"):
    delete_all_reservations(admin_password)


