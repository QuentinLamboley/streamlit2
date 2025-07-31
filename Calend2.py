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
        return df
    except Exception:
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

# ✅ Enregistrer la réservation (anti-doublon)
def save_reservation(prenom, nom, date, plage):
    df = load_reservations()
    # Vérifie si la réservation existe déjà
    already_reserved = (
        (df["Prénom"] == prenom) & 
        (df["Nom"] == nom) & 
        (df["Date"] == date) & 
        (df["Plage"] == plage)
    ).any()
    if already_reserved:
        return False  # Doublon
    new_row = pd.DataFrame([[prenom, nom, date, plage]], columns=["Prénom", "Nom", "Date", "Plage"])
    df = pd.concat([df, new_row], ignore_index=True)
    save_reservations(df)
    return True

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
date_selected_str = st.selectbox("📅 Sélectionnez une date", date_str_options)
date_selected = date_selected_str  # Directement sous forme de string pour la table

plage_selected = st.radio("⏳ Choisissez votre plage horaire", CRENEAUX, horizontal=True)

if st.button("✅ Valider la réservation"):
    if not prenom or not nom or not date_selected or not plage_selected:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        saved = save_reservation(prenom, nom, date_selected, plage_selected)
        if saved:
            st.success(f"✅ Réservation confirmée pour {prenom} {nom} le {date_selected} ({plage_selected}) !")
        else:
            st.warning("⚠️ Vous avez déjà réservé ce créneau.")

# ✅ Affichage des réservations existantes
st.markdown("---")
st.markdown("### 📊 **Réservations existantes**")

df_reservations = load_reservations()

if not df_reservations.empty:
    df_reservations["NomComplet"] = df_reservations["Prénom"] + " " + df_reservations["Nom"]
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


