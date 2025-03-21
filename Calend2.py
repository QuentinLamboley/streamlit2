import streamlit as st
import pandas as pd
import requests
import dropbox
from io import BytesIO
from datetime import datetime, timedelta
import plotly.express as px

# 🔑 Connexion Dropbox
DROPBOX_APP_KEY = "siecwy4rj0ijazf"
DROPBOX_APP_SECRET = "o66gnhdiu214b1c"
DROPBOX_REFRESH_TOKEN = "RryShEoBZ6oAAAAAAAAAAT8ZxBNJh6eM2RhROBKI61AxFnD-6wBOh2nLYbpsNk68"

def get_dropbox_access_token():
    """Renouvelle l'Access Token en utilisant le Refresh Token"""
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

# 📌 Générer un Access Token actualisé
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()
if not DROPBOX_ACCESS_TOKEN:
    st.error("❌ Impossible de récupérer un Access Token valide.")
    st.stop()

# 📌 Connexion Dropbox
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
DROPBOX_FILE_PATH = "/Creneau.xlsx"

# ✅ Charger les réservations
def load_reservations():
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        df = pd.read_excel(BytesIO(res.content), engine="openpyxl", dtype={"Téléphone": str})  
        return df
    except Exception:
        return pd.DataFrame(columns=["Prénom", "Nom", "Date", "Créneau"])

# ✅ Sauvegarder les réservations
def save_reservations(df):
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        dbx.files_upload(output.read(), DROPBOX_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")

# ✅ Liste des créneaux disponibles
def get_available_slots():
    return [f"{hour}h{minute:02d}" for hour in range(9, 20) for minute in (0, 30)]

# ✅ Enregistrer plusieurs créneaux
def save_reservation(prenom, nom, date, creneaux):
    df = load_reservations()
    for creneau in creneaux:
        new_row = pd.DataFrame([[prenom, nom, date, creneau]], columns=["Prénom", "Nom", "Date", "Créneau"])
        df = pd.concat([df, new_row], ignore_index=True)
    save_reservations(df)
    return True

# ✅ Supprimer une réservation spécifique
def delete_reservation(prenom, nom, date, creneau):
    df = load_reservations()
    df = df[~((df["Prénom"] == prenom) & (df["Nom"] == nom) & (df["Date"] == date) & (df["Créneau"] == creneau))]
    save_reservations(df)

# ✅ Réinitialiser toutes les réservations (Admin)
def delete_all_reservations(password):
    if password == "DeleteAll":
        save_reservations(pd.DataFrame(columns=["Prénom", "Nom", "Date", "Créneau"]))
        st.success("✅ Toutes les réservations ont été supprimées avec succès.")
    else:
        st.error("❌ Mot de passe incorrect.")

# ✅ Interface utilisateur
st.set_page_config(page_title="Calendar Tool", layout="centered")

st.markdown("""<h1 style='text-align: center; background-color: #004466; padding: 15px; border-radius: 10px; color: white;'>
📆 Reservations tool</h1>""", unsafe_allow_html=True)

st.markdown("### **Réservez vos créneaux** 📝")

# Infos utilisateur
col1, col2 = st.columns(2)
prenom = col1.text_input("👩 Prénom")
nom = col2.text_input("👤 Nom")
date = st.date_input("📅 Sélectionnez une date", min_value=datetime(2025, 4, 1))

# Sélection multiple des créneaux
creneaux_selectionnes = st.multiselect("⏳ Choisissez vos créneaux", get_available_slots())

if st.button("✅ Valider la réservation"):
    if not prenom or not nom or not creneaux_selectionnes:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        save_reservation(prenom, nom, str(date), creneaux_selectionnes)
        st.success(f"✅ Réservation confirmée pour {prenom} {nom} à {', '.join(creneaux_selectionnes)} le {date} !")

# ✅ Affichage des créneaux réservés sous forme de graphiques
st.markdown("---")
st.markdown("### 📊 **Disponibilités par jour**")

df_reservations = load_reservations()

if not df_reservations.empty:
    # 🔹 Ajouter la colonne NomComplet
    df_reservations["NomComplet"] = df_reservations["Prénom"] + " " + df_reservations["Nom"]
    all_users = sorted(df_reservations["NomComplet"].unique())
    selected_users = st.multiselect("👥 Filtrer par personne(s)", all_users)

    # 🔹 Initialiser df_filtered
    df_filtered = df_reservations

    # 🔹 Filtrer les créneaux communs à toutes les personnes sélectionnées
    if selected_users:
        grouped = df_reservations.groupby(["Date", "Créneau"])["NomComplet"].nunique()
        common_slots = grouped[grouped == len(selected_users)].index
        df_filtered = df_reservations.set_index(["Date", "Créneau"]).loc[common_slots].reset_index()

    # 🔹 Si aucun créneau commun trouvé, afficher un message
    if df_filtered.empty:
        st.info("Aucun créneau commun trouvé pour les personnes sélectionnées.")
    else:
        for jour, df_jour in df_filtered.groupby("Date"):
            st.markdown(f"#### 📅 {jour}")

            counts = df_jour["Créneau"].value_counts().sort_values(ascending=False)
            noms_par_creneau = df_jour.groupby("Créneau")["Prénom"].apply(lambda x: ', '.join(x))

            df_plot = pd.DataFrame({"Créneaux": counts.index, "Nombre de réservations": counts.values})
            df_plot["Noms"] = df_plot["Créneaux"].map(noms_par_creneau)

            fig = px.bar(
                df_plot,
                x="Créneaux",
                y="Nombre de réservations",
                text="Nombre de réservations",
                labels={'Créneaux': "Créneaux", 'Nombre de réservations': "Nombre de réservations"},
                title=f"Disponibilités le {jour}",
                color="Créneaux",
                hover_data={"Noms": True},
            )
            fig.update_traces(texttemplate='%{text}', textposition='outside')
            fig.update_yaxes(dtick=1)
            st.plotly_chart(fig, use_container_width=True)

# ✅ Suppression des créneaux individuels
st.markdown("---")
st.markdown("### ❌ **Supprimer un créneau réservé**")

if not df_reservations.empty:
    user = st.text_input("Entrez votre prénom et nom", placeholder="Ex: Jean Dupont")
    user_reservations = df_reservations[df_reservations["NomComplet"] == user]

    if not user_reservations.empty:
        selected_reservations = st.multiselect("📅 Sélectionnez les créneaux à supprimer", user_reservations["Date"] + " - " + user_reservations["Créneau"])
        if st.button("🗑️ Supprimer les créneaux sélectionnés"):
            for reservation in selected_reservations:
                jour, creneau = reservation.split(" - ")
                delete_reservation(*user.split(), jour, creneau)
            st.success("✅ Créneaux supprimés.")

# ✅ Réinitialisation des créneaux (Admin)
st.markdown("---")
admin_password = st.text_input("🔑 Mot de passe admin", type="password")
if st.button("❌ Supprimer TOUTES les réservations"):
    delete_all_reservations(admin_password)


