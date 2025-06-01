import streamlit as st
import pandas as pd
import requests
import dropbox
from io import BytesIO
from datetime import datetime, timedelta

# 🔑 Informations pour Dropbox
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
        st.error(f"⚠️ Erreur lors du renouvellement du token Dropbox : {response.json()}")
        return None

# 📌 Générer un Access Token actualisé
DROPBOX_ACCESS_TOKEN = get_dropbox_access_token()

# Vérifier si le token est valide avant de continuer
if not DROPBOX_ACCESS_TOKEN:
    st.error("❌ Impossible de récupérer un Access Token valide. Vérifiez votre configuration Dropbox.")
    st.stop()

# 📌 Connexion à Dropbox avec un token renouvelé
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

DROPBOX_FILE_PATH = "/reservations.xlsx"  # Chemin du fichier dans Dropbox


# ✅ Supprimer une réservation spécifique (uniquement si le créneau est à +48h)
def delete_reservation(email, telephone):
    try:
        df = load_reservations()

        # Vérifier si une réservation existe pour cet email et ce téléphone
        user_reservation = df[(df["Mail"] == email) & (df["Téléphone"] == telephone)]
        if user_reservation.empty:
            st.error("⚠️ Aucune réservation trouvée avec ces informations.")
            return False

        # Vérifier si l'annulation est encore possible (plus de 48h avant)
        reservation_date = pd.to_datetime(user_reservation.iloc[0]["Date"])
        reservation_time = user_reservation.iloc[0]["Créneau"]
        reservation_datetime = datetime.combine(reservation_date, datetime.strptime(reservation_time, "%Hh%M").time())

        if reservation_datetime - datetime.now() < timedelta(hours=48):
            st.error("⚠️ L'annulation n'est plus possible car votre créneau est dans moins de 48 heures. Merci de contacter au plus vite le 06.42.13.69.64 pour lui faire part de votre problème.")
            return False

        # Supprimer la réservation et mettre à jour le fichier
        df = df[(df["Mail"] != email) | (df["Téléphone"] != telephone)]
        save_reservations(df)
        st.success("✅ Votre réservation a été annulée et le créneau est désormais disponible.")
        return True
    except Exception as e:
        st.error(f"⚠️ Erreur lors de la suppression de la réservation : {e}")
        return False

# ✅ Récupérer les créneaux disponibles en fonction des réservations existantes
def get_available_slots():
    try:
        df = load_reservations()
        if "Créneau" not in df.columns:
            return [f"{hour}h{minute:02d}" for hour in range(9, 20) for minute in (0, 30)]  # Tous les créneaux

        reserved_slots = set(df["Créneau"].dropna().unique())  # Liste des créneaux déjà réservés
        all_slots = [f"{hour}h{minute:02d}" for hour in range(9, 20) for minute in (0, 30)]
        available_slots = [slot for slot in all_slots if slot not in reserved_slots]  # Filtrer les créneaux disponibles

        return available_slots
    except Exception as e:
        st.error(f"⚠️ Erreur lors de la récupération des créneaux disponibles : {e}")
        return [f"{hour}h{minute:02d}" for hour in range(9, 20) for minute in (0, 30)]


def load_reservations():
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        df = pd.read_excel(BytesIO(res.content), engine="openpyxl", dtype={"Téléphone": str})  # 🔥 Force le téléphone en str
        return df
    except Exception as e:
        st.error(f"⚠️ Erreur de chargement du fichier : {e}")
        return pd.DataFrame(columns=["Prénom", "Nom", "Date", "Créneau", "Mail", "Téléphone"])

# ✅ Sauvegarder les réservations dans Dropbox
def save_reservations(df):
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        dbx.files_upload(output.read(), DROPBOX_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")


# ✅ Sauvegarder une réservation (en vérifiant que l'email et le téléphone ne sont pas déjà enregistrés)
def save_reservation(prenom, nom, date, creneau, email, telephone):
    try:
        df = load_reservations()

        # Vérifier si l'email ou le téléphone sont déjà enregistrés
        if ((df["Mail"] == email) | (df["Téléphone"] == telephone)).any():
            st.error("⚠️ Une réservation a déjà été effectuée avec cet e-mail ou ce numéro de téléphone. "
                     "Une seule réservation est autorisée par contact.")
            return False

        new_row = pd.DataFrame([[prenom, nom, date, creneau, email, telephone]],
                               columns=["Prénom", "Nom", "Date", "Créneau", "Mail", "Téléphone"])
        df = pd.concat([df, new_row], ignore_index=True)

        df["Téléphone"] = df["Téléphone"].astype(str)  # 🔥 Assure que tout est en str avant de sauvegarder

        save_reservations(df)
        return True
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")
        return False

# ✅ Supprimer une réservation spécifique
def delete_reservation(email, telephone):
    try:
        df = load_reservations()

        # Vérifier si une réservation existe pour cet email et ce téléphone
        user_reservation = df[(df["Mail"] == email) & (df["Téléphone"] == telephone)]
        if user_reservation.empty:
            st.error("⚠️ Aucune réservation trouvée avec ces informations.")
            return False

        # Vérifier si l'annulation est encore possible (plus de 48h avant)
        reservation_date = pd.to_datetime(user_reservation.iloc[0]["Date"])
        reservation_time = user_reservation.iloc[0]["Créneau"]
        reservation_datetime = datetime.combine(reservation_date, datetime.strptime(reservation_time, "%Hh%M").time())

        if reservation_datetime - datetime.now() < timedelta(hours=48):
            st.error("⚠️ L'annulation n'est plus possible car votre créneau est dans moins de 48 heures. Merci de contacter au plus vite le 06.42.13.69.64 pour lui faire part de votre problème.")
            return  # 🔥 Ne retourne rien pour éviter le deuxième message d'erreur


        # Supprimer la réservation
        df = df[(df["Mail"] != email) | (df["Téléphone"] != telephone)]
        save_reservations(df)
        return True
    except Exception as e:
        st.error(f"⚠️ Erreur lors de la suppression de la réservation : {e}")
        return False

# ✅ Interface utilisateur Streamlit
st.set_page_config(page_title="Calendrier RESOLVE", layout="centered")

st.markdown("""
    <h1 style='text-align: center; color: black; background-color: #004466; padding: 15px; border-radius: 10px; color: white;'>
        📆 Réservations pour entretiens RESOLVE
    </h1>
""", unsafe_allow_html=True)

st.markdown("### **Réservez un créneau** 📝")

col1, col2 = st.columns(2)
prenom = col1.text_input("🧑 Prénom")
nom = col2.text_input("👤 Nom")

from datetime import date

# 🔒 Liste des jours fériés en France pour 2025
def get_french_holidays_2025():
    return set([
        date(2025, 1, 1),
        date(2025, 4, 21),
        date(2025, 5, 1),
        date(2025, 5, 8),
        date(2025, 5, 29),
        date(2025, 6, 5),
        date(2025, 6, 6),
        date(2025, 6, 9),
        date(2025, 6, 10),
        date(2025, 6, 19),
        date(2025, 7, 14),
        date(2025, 8, 15),
        date(2025, 11, 1),
        date(2025, 11, 11),
        date(2025, 12, 25),
    ])

# 📆 Filtrer les jours valides
french_holidays = get_french_holidays_2025()

def is_valid_booking_date(d):
    return (
        d >= date(2025, 5, 26) and
        d.weekday() < 5 and  # 0=Monday, 6=Sunday
        d not in french_holidays
    )

valid_dates = [date(2025, 5, 26) + timedelta(days=i) for i in range(365)]
valid_dates = [d for d in valid_dates if is_valid_booking_date(d)]

# 🗓️ Remplace le date_input par une selectbox filtrée
date = st.selectbox("📅 Choisissez votre date de disponibilité", valid_dates)

creneau = st.selectbox("⏳ Choisissez votre créneau horaire", get_available_slots())

email = st.text_input("📧 Entrez votre adresse e-mail", placeholder="exemple@domaine.com")
telephone = st.text_input("📞 Entrez votre numéro de téléphone", placeholder="+33XXXXXXXXX")

if st.button("✅ Réserver", help="Réserver votre créneau"):
    if not prenom or not nom or not email or not telephone:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        confirmation = st.warning(f"🔔 Vous êtes sur le point de réserver le créneau **{creneau}** le **{date}**.")
        if confirmation:
            success = save_reservation(prenom, nom, str(date), creneau, email, telephone)
            if success:
                st.success(f"✅ Réservation confirmée pour {prenom} {nom} à {creneau} le {date} !")

# ✅ Suppression d'une réservation spécifique
st.markdown("---")
st.markdown("### ❌ **Annuler votre réservation**")

cancel_email = st.text_input("📧 E-mail utilisé pour la réservation")
cancel_telephone = st.text_input("📞 Numéro de téléphone utilisé pour la réservation")

result = None  # 🔥 Initialisation de la variable pour éviter l'erreur

if st.button("🗑️ Annuler ma réservation"):
    if cancel_email and cancel_telephone:
        result = delete_reservation(cancel_email, cancel_telephone)

# 🔥 Vérification de `result` uniquement si elle a été définie
if result is True:  # ✅ Uniquement si la suppression a bien eu lieu
    st.success("✅ Votre réservation a été annulée avec succès.")
elif result is False:  # ❌ Ne rien afficher si c'est un blocage 48h
    st.error("⚠️ Veuillez entrer l'e-mail et le numéro de téléphone associés à votre réservation.")

# ✅ Suppression totale des réservations (admin)
st.markdown("---")
st.markdown("### 🔥 **Supprimer toutes les réservations** (Accès restreint)")

admin_password = st.text_input("🔑 Entrez le mot de passe administrateur", type="password")
# ✅ Supprimer toutes les réservations (nécessite un mot de passe administrateur)
def delete_all_reservations(password):
    if password == "DeleteAll":
        try:
            empty_df = pd.DataFrame(columns=["Prénom", "Nom", "Date", "Créneau", "Mail", "Téléphone"])
            save_reservations(empty_df)
            st.success("✅ Toutes les réservations ont été supprimées avec succès.")
        except Exception as e:
            st.error(f"⚠️ Erreur lors de la suppression des réservations : {e}")
    else:
        st.error("❌ Mot de passe incorrect. Suppression annulée.")

if st.button("❌ Supprimer TOUTES les réservations"):
    delete_all_reservations(admin_password)


