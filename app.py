import streamlit as st
import time

st.set_page_config(page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide")

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
CLOUDINARY_CLOUD_NAME = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = st.secrets.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = st.secrets.get("CLOUDINARY_API_SECRET", "")

import google.generativeai as genai
import cloudinary
import cloudinary.uploader
import cloudinary.api
from PIL import Image
from io import BytesIO

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Panel boczny
st.sidebar.title("Panel Konfiguracji & DJ")
st.sidebar.text_input("Gemini API Key", value=GEMINI_API_KEY, type="password")
st.sidebar.text_input("Cloudinary Cloud Name", value=CLOUDINARY_CLOUD_NAME)
st.sidebar.text_input("Cloudinary API Key", value=CLOUDINARY_API_KEY, type="password")
st.sidebar.text_input("Cloudinary API Secret", value=CLOUDINARY_API_SECRET, type="password")

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjęcie (Goście)", "Pokaz na Projektorze (DJ)")
)

# Inicjalizacja stanu sesji
if "active_items" not in st.session_state:
    st.session_state.active_items = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

# --- WIDOK 1: GOŚCIE ---
if view_mode == "Wgraj Zdjęcie (Goście)":
    st.title("🎂 18. Urodziny Zuzi")
    st.header("Wrzuć fotki na żywo na ekran projektora!")

    if not CLOUDINARY_CLOUD_NAME or not GEMINI_API_KEY:
        st.error("Uzupełnij dane Cloudinary lub Gemini w pliku secrets.toml!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjęcia z telefonu:",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )

        if uploaded_files:
            if st.button("🚀 Wyślij zdjęcia do pokazu"):
                with st.spinner("Wysyłam zdjęcia i generuję odjechane podpisy AI..."):
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            # Upload do Cloudinary
                            upload_result = cloudinary.uploader.upload(uploaded_file)
                            image_url = upload_result.get("secure_url")

                            # Generowanie unikalnego podpisu przez AI
                            caption = "Zuzia 18 lat! 🎉"
                            try:
                                image_bytes = uploaded_file.getvalue()
                                image_obj = Image.open(BytesIO(image_bytes))
                                prompt = "Napisz krótki, bardzo zabawny, imprezowy i luźny podpis po polsku do tego zdjęcia na 18. urodziny Zuzi. Użyj slangu młodzieżowego lub żartu. Tylko 1 krótkie zdanie z emoji."
                                response = model.generate_content([prompt, image_obj])
                                if response and response.text:
                                    caption = response.text.strip()
                            except Exception:
                                # Jeśli limit chwilowo przyblokuje, dajemy zróżnicowane teksty zamiast ciągle tego samego
                                fallbacks = [
                                    "Ale impreza! Sto lat Zuzia! 🥳",
                                    "Klimacik 18-stkowy na propsie! 🔥",
                                    "Zuzia rulez! 👑",
                                    "Niezapomniana noc! 🥂"
                                ]
                                caption = fallbacks[i % len(fallbacks)]

                            st.session_state.active_items.append({"url": image_url, "caption": caption})

                            # Krótka pauza między zdjęciami, żeby chronić limit darmowego API Gemini
                            if len(uploaded_files) > 1:
                                time.sleep(1.5)

                        except Exception as e:
                            st.error(f"Błąd przy pliku: {e}")

                    st.success("Wszystkie zdjęcia zostały wysłane na telebim! 🎉")

# --- WIDOK 2: DJ / PROJEKTOR (Pełna automatyzacja) ---
else:
    st.title("🎬 Ekran Projektora / Pokaz")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Sterowanie Pokazem")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdów (Auto-Play)", value=True)
    slide_delay = st.sidebar.slider("Czas wyświetlania zdjęcia (sekundy)", 3, 15, 7)

    if st.session_state.active_items:
        idx = st.session_state.current_index % len(st.session_state.active_items)
        item = st.session_state.active_items[idx]

        # Wyświetlanie zdjęcia i podpisu
        st.image(item["url"], use_container_width=True)
        st.markdown(f"<h1 style='text-align: center; color: #ff4b4b; text-shadow: 2px 2px 4px #000;'>{item['caption']}</h1>", unsafe_allow_html=True)
        st.caption(f"Zdjęcie {idx + 1} z {len(st.session_state.active_items)}")

        # Automatyczne przełączanie slajdów bez udziału DJ-a
        if auto_play:
            time.sleep(slide_delay)
            st.session_state.current_index = (st.session_state.current_index + 1) % len(st.session_state.active_items)
            st.rerun()
    else:
        st.info("Brak zdjęć do pokazu. Goście mogą wrzucać zdjęcia przez telefon, a pojawią się tutaj automatycznie!")
