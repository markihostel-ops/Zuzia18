import streamlit as st

st.set_page_config(page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide")

# Automatyczne pobieranie kluczy z pliku secrets.toml (bez wpisywania ręcznego)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
CLOUDINARY_CLOUD_NAME = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = st.secrets.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = st.secrets.get("CLOUDINARY_API_SECRET", "")

import google.generativeai as genai
import cloudinary
import cloudinary.uploader
import cloudinary.api
from PIL import Image, ImageFilter
import requests
from io import BytesIO
import time
from concurrent.futures import ThreadPoolExecutor

# Konfiguracja Cloudinary i Gemini w tle
if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Panel boczny (pola są wypełniane automatycznie ukrytymi wartościami z secrets)
st.sidebar.title("Panel Konfiguracji & DJ")
st.sidebar.text_input("Gemini API Key", value=GEMINI_API_KEY, type="password")
st.sidebar.text_input("Cloudinary Cloud Name", value=CLOUDINARY_CLOUD_NAME)
st.sidebar.text_input("Cloudinary API Key", value=CLOUDINARY_API_KEY, type="password")
st.sidebar.text_input("Cloudinary API Secret", value=CLOUDINARY_API_SECRET, type="password")

st.sidebar.subheader("Wybierz widok:")
view_mode = st.sidebar.radio(
    "",
    ("Pokaz na Projektorze (DJ)", "Wgraj Zdjęcie (Goście)"),
    label_visibility="collapsed"
)

if "comments" not in st.session_state:
    st.session_state.comments = {}

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

# Główna logika aplikacji
if view_mode == "Wgraj Zdjęcie (Goście)":
    st.title("🎂 18. Urodziny Zuzi")
    st.header("Wrzuć fotkę na żywo na ekran projektora!")

    if not CLOUDINARY_CLOUD_NAME or not GEMINI_API_KEY:
        st.error("Uzupełnij dane Cloudinary w panelu bocznym lub pliku secrets!")
    else:
        uploaded_file = st.file_uploader("Wybierz zdjęcie z telefonu:", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            if st.button("🚀 Wyślij zdjęcie do pokazu"):
                with st.spinner("Wysyłam na telebim..."):
                    try:
                        upload_result = cloudinary.uploader.upload(uploaded_file)
                        image_url = upload_result.get("secure_url")

                        # Zapisujemy w sesji (jeśli masz listę zdjęć)
                        if "active_urls" not in st.session_state:
                            st.session_state.active_urls = []
                        st.session_state.active_urls.append(image_url)

                        st.success("Zdjęcie zostało wysłane na pokaz! 🎉")
                    except Exception as e:
                        st.error(f"Błąd wysyłania: {e}")

else:
    st.title("🎬 Ekran Projektora / Pokaz")
    if "active_urls" in st.session_state and st.session_state.active_urls:
        idx = st.session_state.current_index % len(st.session_state.active_urls)
        st.image(st.session_state.active_urls[idx], use_container_width=True)
    else:
        st.info("Brak zdjęć do pokazu. Przełącz na 'Wgraj Zdjęcie', aby dodać pierwsze fotki!")
