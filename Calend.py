import streamlit as st
import pandas as pd
import requests
import dropbox
from io import BytesIO
from datetime import datetime, timedelta, date

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

DROPBOX_FILE_PATH = "/reservations.xlsx"           # Fichier des réservations
DROPBOX_BLOCKED_PATH = "/blocked_slots.xlsx"       # Nouveau : fichier des créneaux bloqués (admin)

# 🔧 Génération des créneaux (toutes les 30 minutes, 9h00–19h30, SANS exclure d'heure)
def generate_all_slots():
    return [f"{hour}h{minute:02d}"
            for hour in range(9, 20)
            for minute in (0, 30)]

# ========= GESTION DES RESERVATIONS =========

def load_reservations():
    try:
        _, res = dbx.files_download(DROPBOX_FILE_PATH)
        df = pd.read_excel(BytesIO(res.content), engine="openpyxl", dtype={"Téléphone": str})  # 🔥 Force téléphone en str
        return df
    except Exception as e:
        st.error(f"⚠️ Erreur de chargement du fichier : {e}")
        return pd.DataFrame(columns=["Prénom", "Nom", "Date", "Créneau", "Mail", "Téléphone"])

def save_reservations(df):
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        dbx.files_upload(output.read(), DROPBOX_FILE_PATH, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")

# ========= GESTION DES CRENEAUX BLOQUES (ADMIN) =========

def load_blocked_slots():
    """Charge le tableau des créneaux bloqués (admin)."""
    try:
        _, res = dbx.files_download(DROPBOX_BLOCKED_PATH)
        df = pd.read_excel(BytesIO(res.content), engine="openpyxl")
        # Normalise les colonnes au besoin
        if "Date" not in df.columns or "Créneau" not in df.columns:
            df = pd.DataFrame(columns=["Date", "Créneau"])
        # Cast Date en str (YYYY-MM-DD)
        df["Date"] = df["Date"].astype(str)
        df["Créneau"] = df["Créneau"].astype(str)
        return df
    except Exception:
        # S'il n'existe pas encore, renvoyer un DF vide
        return pd.DataFrame(columns=["Date", "Créneau"])

def save_blocked_slots(df):
    """Sauvegarde le tableau des créneaux bloqués (admin)."""
    try:
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        dbx.files_upload(output.read(), DROPBOX_BLOCKED_PATH, mode=dropbox.files.WriteMode("overwrite"))
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement des créneaux bloqués : {e}")

def block_slot_admin(date_str, slot_str):
    """Ajoute un créneau bloqué pour une date (admin)."""
    dfb = load_blocked_slots()
    exists = ((dfb["Date"] == date_str) & (dfb["Créneau"] == slot_str)).any()
    if not exists:
        dfb = pd.concat([dfb, pd.DataFrame([{"Date": date_str, "Créneau": slot_str}])], ignore_index=True)
        save_blocked_slots(dfb)
        return True
    return False

def unblock_slot_admin(date_str, slot_str):
    """Retire un créneau bloqué pour une date (admin)."""
    dfb = load_blocked_slots()
    before = len(dfb)
    dfb = dfb[~((dfb["Date"] == date_str) & (dfb["Créneau"] == slot_str))].copy()
    if len(dfb) < before:
        save_blocked_slots(dfb)
        return True
    return False

def get_blocked_slots_for_date(date_str):
    dfb = load_blocked_slots()
    if dfb.empty:
        return set()
    return set(dfb.loc[dfb["Date"] == date_str, "Créneau"].dropna().astype(str).unique())

# ✅ Récupérer les créneaux disponibles en fonction des réservations existantes et des créneaux bloqués
def get_available_slots(selected_date=None):
    try:
        df = load_reservations()
        if "Créneau" not in df.columns:
            base = generate_all_slots()
        else:
            reserved_slots = set(df["Créneau"].dropna().astype(str).unique())
            base = [slot for slot in generate_all_slots() if slot not in reserved_slots]

        # Filtre aussi les créneaux bloqués par l'admin si une date est fournie
        if selected_date is not None:
            date_str = str(selected_date)
            blocked = get_blocked_slots_for_date(date_str)
            base = [slot for slot in base if slot not in blocked]

        return base
    except Exception as e:
        st.error(f"⚠️ Erreur lors de la récupération des créneaux disponibles : {e}")
        return generate_all_slots()

# ✅ Sauvegarder une réservation (en vérifiant que l'email et le téléphone ne sont pas déjà enregistrés)
def save_reservation(prenom, nom, date_val, creneau, email, telephone):
    try:
        df = load_reservations()

        # Vérifier si l'email ou le téléphone sont déjà enregistrés
        if ((df["Mail"] == email) | (df["Téléphone"] == telephone)).any():
            st.error("⚠️ Une réservation a déjà été effectuée avec cet e-mail ou ce numéro de téléphone. "
                     "Une seule réservation est autorisée par contact.")
            return False

        # ⛔ Interdire la réservation à moins de 48h
        try:
            res_date = pd.to_datetime(date_val).date()
            res_time = datetime.strptime(creneau, "%Hh%M").time()
            res_dt = datetime.combine(res_date, res_time)
        except Exception as e_parse:
            st.error(f"⚠️ Date/heure invalides ({e_parse}).")
            return False

        if res_dt - datetime.now() < timedelta(hours=48):
            st.error("⛔ La réservation doit être effectuée **au moins 48 heures à l'avance**. "
                     "Veuillez choisir un autre créneau.")
            return False

        # ⛔ Empêcher la réservation sur un créneau bloqué (sécurité côté serveur)
        if creneau in get_blocked_slots_for_date(str(res_date)):
            st.error("⛔ Ce créneau a été bloqué par l'organisation. Veuillez en choisir un autre.")
            return False

        new_row = pd.DataFrame([[prenom, nom, date_val, creneau, email, telephone]],
                               columns=["Prénom", "Nom", "Date", "Créneau", "Mail", "Téléphone"])
        df = pd.concat([df, new_row], ignore_index=True)

        df["Téléphone"] = df["Téléphone"].astype(str)  # 🔥 Assure que tout est en str avant de sauvegarder

        save_reservations(df)
        return True
    except Exception as e:
        st.error(f"⚠️ Erreur lors de l'enregistrement : {e}")
        return False

# ✅ Supprimer une réservation spécifique (UI - première définition)
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

# ✅ Supprimer une réservation spécifique (version UI existante - redéfinition)
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

# 🔒 Liste des jours fériés en France pour 2025 (inchangée)
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
        date(2025, 7, 8),
        date(2025, 7, 14),
        date(2025, 8, 15),
        date(2025, 11, 1),
        date(2025, 11, 11),
        date(2025, 12, 25),
    ])

# 📆 Filtrer les jours valides (J+2 dynamiquement)
french_holidays = get_french_holidays_2025()
START_DATE = (datetime.now().date() + timedelta(days=2))

def is_valid_booking_date(d):
    return (
        d >= START_DATE and
        d.weekday() < 5 and  # 0=Monday, 6=Sunday
        d not in french_holidays
    )

# Fenêtre de 365 jours à partir de J+2
valid_dates = [START_DATE + timedelta(days=i) for i in range(365)]
valid_dates = [d for d in valid_dates if is_valid_booking_date(d)]

# 🗓️ Sélection de la date
selected_date = st.selectbox("📅 Choisissez votre date de disponibilité", valid_dates)

# ⏳ Créneaux disponibles (tiennent compte des réservations ET des créneaux bloqués)
creneau = st.selectbox("⏳ Choisissez votre créneau horaire", get_available_slots(selected_date))

email = st.text_input("📧 Entrez votre adresse e-mail", placeholder="exemple@domaine.com")
telephone = st.text_input("📞 Entrez votre numéro de téléphone", placeholder="+33XXXXXXXXX")

if st.button("✅ Réserver", help="Réserver votre créneau"):
    if not prenom or not nom or not email or not telephone:
        st.error("⚠️ Veuillez remplir tous les champs.")
    else:
        confirmation = st.warning(f"🔔 Vous êtes sur le point de réserver le créneau **{creneau}** le **{selected_date}**.")
        if confirmation:
            success = save_reservation(prenom, nom, str(selected_date), creneau, email, telephone)
            if success:
                st.success(f"✅ Réservation confirmée pour {prenom} {nom} à {creneau} le {selected_date} !")

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

# ================== NOUVEAU : GESTION DES CRENEAUX (ADMIN SEULEMENT) ==================
st.markdown("---")
st.markdown("### 🔒 **Bloquer / Débloquer des créneaux** (Accès restreint)")

admin_password_slots = st.text_input("🔑 Mot de passe administrateur (créneaux)", type="password", key="admin_pw_slots")
admin_date = st.selectbox("📅 Date à gérer (admin)", valid_dates, key="admin_date_slots")
blocked_now = sorted(list(get_blocked_slots_for_date(str(admin_date))))

colA, colB = st.columns(2)
with colA:
    slot_to_block = st.selectbox("⏳ Créneau à bloquer", generate_all_slots(), key="slot_block")
    if st.button("🚫 Bloquer ce créneau"):
        if admin_password_slots == "DeleteAll":
            ok = block_slot_admin(str(admin_date), slot_to_block)
            if ok:
                st.success(f"✅ Créneau {slot_to_block} bloqué le {admin_date}.")
            else:
                st.info("ℹ️ Ce créneau est déjà bloqué pour cette date.")
        else:
            st.error("❌ Mot de passe incorrect.")

with colB:
    slot_to_unblock = st.selectbox("⏳ Créneau à débloquer", blocked_now if blocked_now else ["(aucun)"], key="slot_unblock")
    if st.button("♻️ Débloquer ce créneau"):
        if admin_password_slots == "DeleteAll":
            if blocked_now and slot_to_unblock != "(aucun)":
                ok = unblock_slot_admin(str(admin_date), slot_to_unblock)
                if ok:
                    st.success(f"✅ Créneau {slot_to_unblock} débloqué le {admin_date}.")
                else:
                    st.info("ℹ️ Ce créneau n'était pas bloqué.")
            else:
                st.info("ℹ️ Aucun créneau à débloquer pour cette date.")
        else:
            st.error("❌ Mot de passe incorrect.")

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
