import streamlit as st
import time
import os
import random

st.set_page_config(page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide")

st.sidebar.title("Panel Konfiguracji & DJ")

s_gemini = st.secrets.get("GEMINI_API_KEY", "")
s_cloud = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
s_ckey = st.secrets.get("CLOUDINARY_API_KEY", "")
s_csec = st.secrets.get("CLOUDINARY_API_SECRET", "")

gemini_key = st.sidebar.text_input("Gemini API Key", value=s_gemini, type="password")
cloud_name = st.sidebar.text_input("Cloudinary Cloud Name", value=s_cloud)
cloudinary_key = st.sidebar.text_input("Cloudinary API Key", value=s_ckey, type="password")
cloudinary_secret = st.sidebar.text_input("Cloudinary API Secret", value=s_csec, type="password")

import google.generativeai as genai
import cloudinary
import cloudinary.uploader
import cloudinary.api
from PIL import Image
from io import BytesIO

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret
    )

if gemini_key:
    genai.configure(api_key=gemini_key)

DB_FILE = "galeria_zuzi.txt"

def load_gallery():
    if not os.path.exists(DB_FILE):
        return []
    items = []
    with open(DB_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if "|" in line:
                parts = line.strip().split("|", 1)
                items.append({"url": parts[0], "caption": parts[1]})
    return items

def save_item(url, caption):
    with open(DB_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}|{caption}\n")

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjęcie (Goście)", "Pokaz na Projektorze (DJ)")
)

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Wyczyść całą galerię (Reset)"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    st.sidebar.success("Galeria wyczyszczona!")
    st.rerun()

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if view_mode == "Wgraj Zdjęcie (Goście)":
    st.title("🎂 18. Urodziny Zuzi")
    st.header("Wrzuć fotki na żywo na ekran projektora!")

    if not cloud_name or not gemini_key:
        st.error("Uzupełnij klucze Cloudinary i Gemini w panelu po lewej!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjęcia z telefonu:",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )

        if uploaded_files:
            if st.button("🚀 Wyślij zdjęcia do pokazu"):
                with st.spinner("Przesyłam foty i generuję teksty..."):
                    model = genai.GenerativeModel("gemini-2.0-flash")

                    fallbacks = [
                        "Kto rano wstaje, ten ma największego kaca! 💀",
                        "Tu miało być kulturalnie, ale wyszło jak zwykle! 🥂",
                        "Fotka za miliony, dowody zostaną rano zniszczone! 📸",
                        "Zuzia nie bierze jeńców, impreza życia! 🔥"
                    ]

                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            upload_result = cloudinary.uploader.upload(uploaded_file)
                            image_url = upload_result.get("secure_url")

                            caption = ""
                            try:
                                image_bytes = uploaded_file.getvalue()
                                image_obj = Image.open(BytesIO(image_bytes))
                                prompt = "Jesteś bezczelnym komikiem na 18. urodzinach Zuzi. Wymyśl ULTRA ŚMIESZNY, ironiczny podpis po polsku do 1 zdania z emoji."
                                response = model.generate_content([prompt, image_obj])
                                if response and response.text:
                                    caption = response.text.strip()
                            except Exception:
                                pass

                            if not caption:
                                caption = random.choice(fallbacks)

                            save_item(image_url, caption)
                            time.sleep(2)
                        except Exception as e:
                            st.error(f"Błąd: {e}")
                    st.success("Wszystkie zdjęcia wysłane! 🎉")
else:
    st.title("🎬 Ekran Projektora / Pokaz na Żywo")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Sterowanie Pokazem")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdów", value=True)
    slide_delay = st.sidebar.slider("Czas wyświetlania (sekundy)", 3, 15, 7)

    items = load_gallery()

    if items:
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        st.image(item["url"], use_container_width=True)
        st.markdown(f"<h1 style='text-align: center; color: #ff4b4b;'>{item['caption']}</h1>", unsafe_allow_html=True)
        st.caption(f"Zdjęcie {idx + 1} z {len(items)}")

        if auto_play:
            time.sleep(slide_delay)
            st.session_state.current_index = (st.session_state.current_index + 1) % len(items)
            st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjęcia! Wrzuć coś z telefonu.")
        time.sleep(5)
        st.rerun()

