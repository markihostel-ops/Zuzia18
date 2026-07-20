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

if "active_items" not in st.session_state:
    st.session_state.active_items = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if view_mode == "Wgraj Zdjęcie (Goście)":
    st.title("🎂 18. Urodziny Zuzi")
    st.header("Wrzuć fotki na żywo na ekran projektora!")

    if not CLOUDINARY_CLOUD_NAME or not GEMINI_API_KEY:
        st.error("Uzupełnij dane Cloudinary lub Gemini!")
    else:
        uploaded_files = st.file_uploader("Wybierz zdjęcia z telefonu:", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        if uploaded_files:
            if st.button("🚀 Wyślij zdjęcia do pokazu"):
                with st.spinner("Wysyłam i generuję podpisy AI..."):
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    for uploaded_file in uploaded_files:
                        try:
                            upload_result = cloudinary.uploader.upload(uploaded_file)
                            image_url = upload_result.get("secure_url")

                            image_bytes = uploaded_file.getvalue()
                            image_obj = Image.open(BytesIO(image_bytes))

                            prompt = "Wymyśl krótki, zabawny, imprezowy podpis w języku polskim do tego zdjęcia na 18. urodziny Zuzi. Maksymalnie 1 zdanie z emoji."
                            response = model.generate_content([prompt, image_obj])
                            caption = response.text.strip() if response and response.text else "Sto lat Zuzia! 🎉"

                            st.session_state.active_items.append({"url": image_url, "caption": caption})
                        except Exception as e:
                            st.error(f"Błąd przy pliku: {e}")

                    st.success("Wszystkie zdjęcia zostały wysłane! 🎉")

else:
    st.title("🎬 Ekran Projektora / Pokaz")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Kontrola Slajdów")
    pause_show = st.sidebar.checkbox("Pauza pokazu")

    if st.session_state.active_items:
        if not pause_show:
            time.sleep(7)
            st.session_state.current_index = (st.session_state.current_index + 1) % len(st.session_state.active_items)
            st.rerun()

        idx = st.session_state.current_index % len(st.session_state.active_items)
        item = st.session_state.active_items[idx]

        st.image(item["url"], use_container_width=True)
        st.markdown(f"<h2 style='text-align: center; color: #ff4b4b;'>{item['caption']}</h2>", unsafe_allow_html=True)
    else:
        st.info("Brak zdjęć do pokazu. Przełącz na 'Wgraj Zdjęcie', aby dodać pierwsze fotki!")
