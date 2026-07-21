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
                        if parts[0].startswith("http"):
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

def save_full_gallery(items):
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                for it in items:
                    f.write(f"{it['url']}|{it['caption']}\n")
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

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if view_mode == "Wgraj Zdjecie (Goscie)":
    st.title("18. Urodziny Zuzi")
    st.header("Wrzuc fotki na zywo na ekran projektora!")

    if not st.session_state.cloud_name or not st.session_state.gemini_key:
        st.error("Uzupełnij klucze w panelu bocznym!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjecia z telefonu:",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}"
        )

        if uploaded_files:
            if st.button("Wyslij zdjecia do pokazu"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                generation_config = {"temperature": 1.2}
                model = genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)

                total_files = len(uploaded_files)
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analizuję zdjęcie {i+1} z {total_files}...")

                    try:
                        image_bytes = uploaded_file.getvalue()
                        img = Image.open(BytesIO(image_bytes))
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        img.thumbnail((1600, 1600))

                        byte_arr = BytesIO()
                        img.save(byte_arr, format='JPEG', quality=85)
                        byte_arr.seek(0)

                        upload_result = cloudinary.uploader.upload(byte_arr, folder=CLOUDINARY_FOLDER)
                        image_url = upload_result.get("secure_url")

                        if not image_url:
                            continue

                        caption = "Zuzia 18! 🔥"
                        success_ai = False

                        for attempt in range(3):
                            try:
                                unique_seed = str(time.time() + random.random())
                                prompt = (
                                    f"[ID: {unique_seed}] "
                                    "Jesteś bezczelnym, złośliwym komikiem prowadzącym 18. urodziny. "
                                    "Musisz bezwzględnie opisać dokładnie to, co widzisz na tym zdjęciu: "
                                    "kto dokładnie na nim jest, w co są ubrani, jaką mają minę, jak się ustawili lub co trzymają. "
                                    "Zabronione jest używanie ogólnikowych haseł typu 'impreza', 'super zabawa' czy 'osiemnastka' bez odniesienia do konkretu z kadru! "
                                    "Skomentuj to złośliwie, uszczypliwie lub mocno żartobliwie w maksymalnie 2 krótkich zdaniach, dodaj pasujące emoji. "
                                    "Zwróć wyłącznie sam tekst komentarza, bez żadnych cudzysłowów i wstępów."
                                )

                                response = model.generate_content([prompt, img])
                                if response and hasattr(response, "text") and response.text:
                                    text_resp = response.text.strip().replace('"', '').replace("'", "")
                                    if len(text_resp) > 5:
                                        caption = text_resp
                                        success_ai = True
                                        break
                            except Exception:
                                time.sleep(1)

                        if not success_ai:
                            caption = f"Ujęcie #{i+1} z osiemnastki Zuzi! 📸🔥"

                        save_item(image_url, caption)
                    except Exception as e:
                        st.error(f"Błąd przy zdjęciu {i+1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("Gotowe! Zdjęcia trafiły na ekran.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()
else:
    st.title("Ekran Projektora / Pokaz na Zywo")

    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarzadzanie pojedynczymi zdjeciami")

    items = load_gallery()

    if items:
        for idx, it in enumerate(items):
            col_txt, col_btn = st.sidebar.columns([3, 1])
            col_txt.text(f"#{idx+1}: {it['caption'][:15]}...")
            if col_btn.button("Skasuj", key=f"del_{idx}"):
                items.pop(idx)
                save_full_gallery(items)
                st.session_state.current_index = 0
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Ustawienia Pokazu")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdow", value=True)
    slide_delay_sec = st.sidebar.slider("Czas wyswietlania (sekundy)", 3, 15, 5)

    if items:
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        st.image(item["url"], use_container_width=True)
        st.markdown(f"<h2 style='text-align: center;'>{item['caption']}</h2>", unsafe_allow_html=True)
        st.caption(f"Zdjecie {idx + 1} z {len(items)}")

        if auto_play and len(items) > 1:
            current_time = time.time()
            if current_time - st.session_state.last_slide_time >= slide_delay_sec:
                st.session_state.current_index = (st.session_state.current_index + 1) % len(items)
                st.session_state.last_slide_time = current_time
                st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjecia! Wrzuc coś ze swojego telefonu.")
