import os
import random
import time
from io import BytesIO

from PIL import Image
import cloudinary
import cloudinary.api
import cloudinary.uploader
from filelock import FileLock
import google.generativeai as genai
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Zuzia 18", layout="wide")

if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = st.secrets.get("GEMINI_API_KEY", "")
if "cloud_name" not in st.session_state:
    st.session_state.cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
if "cloudinary_key" not in st.session_state:
    st.session_state.cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")
if "cloudinary_secret" not in st.session_state:
    st.session_state.cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

st.sidebar.title("Panel Sterowania")

gemini_key = st.sidebar.text_input("Gemini API Key", type="password", key="gemini_key")
cloud_name = st.sidebar.text_input("Cloudinary Cloud Name", key="cloud_name")
cloudinary_key = st.sidebar.text_input("Cloudinary API Key", type="password", key="cloudinary_key")
cloudinary_secret = st.sidebar.text_input("Cloudinary API Secret", type="password", key="cloudinary_secret")

if st.session_state.cloud_name and st.session_state.cloudinary_key and st.session_state.cloudinary_secret:
    cloudinary.config(
        cloud_name=st.session_state.cloud_name,
        api_key=st.session_state.cloudinary_key,
        api_secret=st.session_state.cloudinary_secret
    )

if st.session_state.gemini_key:
    genai.configure(api_key=st.session_state.gemini_key)

DB_FILE = "galeria_zuzi.txt"
LOCK_FILE = "galeria.lock"
CLOUDINARY_FOLDER = "18_zuzia"
MAX_FILE_SIZE_MB = 10

def load_gallery():
    if not os.path.exists(DB_FILE):
        return []
    items = []
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if "|" in line:
                        parts = line.strip().split("|", 1)
                        items.append({"url": parts[0], "caption": parts[1]})
    except Exception:
        pass
    return items

def save_item(url, caption):
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            with open(DB_FILE, "a", encoding="utf-8") as f:
                f.write(f"{url}|{caption}\n")
    except Exception as e:
        st.error(f"Blad zapisu: {e}")

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjecie (Goscie)", "Pokaz na Zywo (DJ)")
)

st.sidebar.markdown("---")
if st.sidebar.button("Wyczysc cala galerie"):
    try:
        lock = FileLock(LOCK_FILE)
        with lock:
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)

        if st.session_state.cloud_name and st.session_state.cloudinary_key and st.session_state.cloudinary_secret:
            try:
                resources = cloudinary.api.resources(type="upload", prefix=CLOUDINARY_FOLDER, max_results=500)
                public_ids = [res["public_id"] for res in resources.get("resources", [])]
                if public_ids:
                    cloudinary.api.delete_resources(public_ids)
            except Exception:
                pass

        st.sidebar.success("Galeria wyczyszczona!")
        st.session_state.current_index = 0
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Blad: {e}")

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "last_slide_time" not in st.session_state:
    st.session_state.last_slide_time = time.time()

if view_mode == "Wgraj Zdjecie (Goscie)":
    st.title("18. Urodziny Zuzi")
    st.header("Wrzuc fotki na zywo na ekran projektora!")

    if not st.session_state.cloud_name or not st.session_state.gemini_key:
        st.error("Uzupełnij klucze w panelu bocznym!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjecia z telefonu:",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True
        )

        if uploaded_files:
            if st.button("Wyslij zdjecia do pokazu"):
                with st.spinner("Przesylam zdjecia i generuje podpisy AI..."):
                    model = genai.GenerativeModel("gemini-2.0-flash")

                    fallbacks = [
                        "Impreza roku! 💀",
                        "Pozdrowienia dla Zuzi! 🥂",
                        "Niezapomniany klimat! 📸",
                        "Ale dym! 🔥"
                    ]

                    for uploaded_file in uploaded_files:
                        if (uploaded_file.size / (1024 * 1024)) > MAX_FILE_SIZE_MB:
                            continue

                        try:
                            upload_result = cloudinary.uploader.upload(uploaded_file, folder=CLOUDINARY_FOLDER)
                            image_url = upload_result.get("secure_url")

                            caption = ""
                            try:
                                image_bytes = uploaded_file.getvalue()
                                image_obj = Image.open(BytesIO(image_bytes))
                                prompt = "Jesteś bezczelnym komikiem na 18. urodzinach Zuzi. Wymyśl krótki, śmieszny podpis po polsku do 1 zdania z emoji. Zwróć tylko czysty tekst podpisu bez żadnego formatowania i bez znaczników HTML."
                                response = model.generate_content([prompt, image_obj])
                                if response and hasattr(response, "text") and response.text:
                                    caption = response.text.strip().replace('"', '').replace("'", "")
                            except Exception:
                                pass

                            if not caption:
                                caption = random.choice(fallbacks)

                            save_item(image_url, caption)
                        except Exception:
                            pass

                    st.success("Wszystkie zdjecia wyslane!")
else:
    st.title("Ekran Projektora / Pokaz na Zywo")

    # Odświeżanie strony co 2 sekundy
    st_autorefresh(interval=2000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Ustawienia Pokazu")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdow", value=True)
    slide_delay_sec = st.sidebar.slider("Czas wyswietlania (sekundy)", 3, 15, 5)

    items = load_gallery()

    if items:
        # Zabezpieczenie przed wyjściem poza zakres
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        st.image(item["url"], use_container_width=True)

        # Bezpieczne wyświetlenie tekstu przez zwykły header zamiast surowego HTML
        st.markdown(f"<h2 style='text-align: center;'>{item['caption']}</h2>", unsafe_allow_html=True)
        st.caption(f"Zdjecie {idx + 1} z {len(items)}")

        # Płynna zmiana slajdów w oparciu o czas (bez blokowania wątku przez time.sleep)
        if auto_play and len(items) > 1:
            current_time = time.time()
            if current_time - st.session_state.last_slide_time >= slide_delay_sec:
                st.session_state.current_index = (st.session_state.current_index + 1) % len(items)
                st.session_state.last_slide_time = current_time
                st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjecia! Wrzuc coś ze swojego telefonu.")



