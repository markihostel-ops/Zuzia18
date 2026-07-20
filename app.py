import streamlit as st
import time
import os

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

# Plik bazy danych na serwerze, żeby telefony i projektor widziały dokładnie to samo
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

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

# --- WIDOK 1: GOŚCIE (Telefon / QR) ---
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
                with st.spinner("Wysyłam na telebim i angażuję AI do wymyślenia haseł..."):
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    for i, uploaded_file in enumerate(uploaded_files):
                        try:
                            # 1. Upload do Cloudinary
                            upload_result = cloudinary.uploader.upload(uploaded_file)
                            image_url = upload_result.get("secure_url")

                            # 2. Mocny, bezwzględnie śmieszny prompt dla AI
                            caption = "Ale impreza! 🔥"
                            try:
                                image_bytes = uploaded_file.getvalue()
                                image_obj = Image.open(BytesIO(image_bytes))
                                prompt = (
                                    "Jesteś bezczelnym, zabawnym imprezowiczem na 18. urodzinach Zuzi. "
                                    "Spojrzyj na to zdjęcie i wymyśl KRÓTKI, bardzo śmieszny, wręcz ironiczny lub slangowy podpis po polsku "
                                    "nawiązujący do tego, co dokładnie robią ludzie na zdjęciu. Zero grzeczności, ma być bekowa szpila lub super mocny żart z emoji. "
                                    "Maksymalnie jedno zdanie."
                                )
                                response = model.generate_content([prompt, image_obj])
                                if response and response.text:
                                    caption = response.text.strip()
                            except Exception:
                                fallbacks = [
                                    "Kto rano wstaje, ten ma kaca po osiemnastce Zuzi! 🍻",
                                    "Tu się dzieje historia... albo kolejna dramka! 😂",
                                    "Zuzia dziękuje za ten sztos! 🔥",
                                    "Klimat gęstszy niż tort urodzinowy! 🎂"
                                ]
                                caption = fallbacks[i % len(fallbacks)]

                            # Zapis do pliku tekstowego na serwerze (widoczny dla każdego)
                            save_item(image_url, caption)

                            if len(uploaded_files) > 1:
                                time.sleep(1)

                        except Exception as e:
                            st.error(f"Błąd przy pliku: {e}")

                    st.success("Wszystkie zdjęcia dotarły na telebim! 🎉")

# --- WIDOK 2: DJ / PROJEKTOR (Pełna automatyzacja) ---
else:
    st.title("🎬 Ekran Projektora / Pokaz na Żywo")

    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Sterowanie Pokazem")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdów (Auto-Play)", value=True)
    slide_delay = st.sidebar.slider("Czas wyświetlania zdjęcia (sekundy)", 3, 15, 7)

    # Pobieramy aktualną listę bezpośrednio z pliku serwerowego
    items = load_gallery()

    if items:
        # Zabezpieczenie indeksu, jeśli usunięto pliki
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        st.image(item["url"], use_container_width=True)
        st.markdown(f"<h1 style='text-align: center; color: #ff4b4b; text-shadow: 2px 2px 4px #000;'>{item['caption']}</h1>", unsafe_allow_html=True)
        st.caption(f"Zdjęcie {idx + 1} z {len(items)} (Synchronizacja w czasie rzeczywistym)")

        if auto_play:
            time.sleep(slide_delay)
            st.session_state.current_index = (st.session_state.current_index + 1) % len(items)
            st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjęcia! Goście mogą wrzucać fotki przez telefon (kod QR), a pokażą się tutaj automatycznie.")
        # Odświeżaj widok projektora co 5 sekund, żeby sprawdzić, czy ktoś coś wrzucił
        time.sleep(5)
        st.rerun()

