import json
import os
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

gemini_key = st.secrets.get("GEMINI_API_KEY", "")
cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")
cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret,
    )

if gemini_key:
    genai.configure(api_key=gemini_key)

DB_FILE = "galeria_zuzi.txt"
LOCK_FILE = "galeria.lock"
CLOUDINARY_FOLDER = "18_zuzia"
DEBUG_LOGS_FOLDER = "debug_logs"

SAFETY_OFF = [
    {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH",        "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",  "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT",  "threshold": "BLOCK_NONE"},
]

GEN_CONFIG = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 200,
}

PROMPT_WITH_IMAGE = (
    "Jesteś rozbawionym, lekko złośliwym gościem na 18. urodzinach Zuzi. "
    "Opisz TO KONKRETNE zdjęcie w 1–2 krótkich zdaniach: "
    "co robią osoby, jakie mają miny, co trzymają, co widać w tle. "
    "Napisz zabawny, imprezowy komentarz nawiązujący do konkretnych detali z kadru — "
    "złośliwy, ale absolutnie nieobraźliwy, żeby bohaterowie sami się roześmiali. "
    "Dodaj 1–2 emoji. Zwróć WYŁĄCZNIE tekst komentarza, bez cudzysłowów i wstępów."
)

PROMPT_TEXT_FALLBACK = (
    "Napisz jeden krótki, zabawny komentarz imprezowy na 18. urodziny Zuzi. "
    "Maks 2 zdania, dodaj emoji. Tylko sam tekst, bez cudzysłowów."
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def debug_response(response, label: str, debug: bool):
    """Wyświetla surową strukturę odpowiedzi Gemini jeśli tryb debug włączony."""
    if not debug:
        return
    try:
        st.sidebar.markdown(f"**🔍 DEBUG [{label}]**")
        
        raw_json = json.dumps(response.__dict__, default=lambda o: str(o), ensure_ascii=False)
        
        try:
            os.makedirs(DEBUG_LOGS_FOLDER, exist_ok=True)
            with open(f"{DEBUG_LOGS_FOLDER}/gemini_{label}.json", "w", encoding="utf-8") as f:
                f.write(raw_json)
        except Exception as ex:
            st.sidebar.error(f"Błąd zapisu logu: {ex}")
        
        st.sidebar.json(raw_json)
        
    except Exception as e:
        st.sidebar.error(f"debug_response error: {e}")


def generate_caption(img_pil: Image.Image, debug: bool = False) -> str:
    """
    Generuje opis zdjęcia przez Gemini.
    1. Próba z obrazem (3 razy)
    2. Fallback: zapytanie tekstowe bez obrazu (2 razy)
    3. Ostateczny fallback: stały napis
    """
    if not gemini_key:
        return "Impreza u Zuzi w pełnym biegu! 🥂🔥"

    # Przygotuj JPEG bytes
    buf = BytesIO()
    img_pil.save(buf, format="JPEG", quality=85)
    image_bytes = buf.getvalue()

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=GEN_CONFIG,
        safety_settings=SAFETY_OFF,
    )

    # ── Krok 1: zapytanie z obrazem ──────────────────────────────────────────
    image_part = {"mime_type": "image/jpeg", "data": image_bytes}

    for attempt in range(3):
        try:
            response = model.generate_content(
                contents=[{"role": "user", "parts": [image_part, {"text": PROMPT_WITH_IMAGE}]}]
            )
            debug_response(response, f"obraz_{attempt+1}", debug)

            text = getattr(response, "text", "")
            if text and len(text.strip()) > 3:
                return text.replace('"', '').replace("'", "").strip()

            if debug:
                st.sidebar.warning(f"Próba {attempt+1}: pusta odpowiedź (obraz)")

        except Exception as ex:
            if debug:
                st.sidebar.error(f"Próba {attempt+1} exception (obraz): {ex}")
            time.sleep(0.8)

    # ── Krok 2: fallback tekstowy (bez obrazu) ───────────────────────────────
    if debug:
        st.sidebar.warning("Przechodzę na fallback TEKSTOWY (bez obrazu)...")

    for attempt in range(2):
        try:
            response = model.generate_content(
                contents=[{"role": "user", "parts": [{"text": PROMPT_TEXT_FALLBACK}]}]
            )
            debug_response(response, f"text_{attempt+1}", debug)

            text = getattr(response, "text", "")
            if text and len(text.strip()) > 3:
                return text.replace('"', '').replace("'", "").strip()

        except Exception as ex:
            if debug:
                st.sidebar.error(f"Text fallback exception: {ex}")
            time.sleep(0.5)

    # ── Krok 3: absolutny fallback ───────────────────────────────────────────
    return "Zuzia i ekipa dają czadu! 🎉🔥"


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("Panel Sterowania")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjecie (Goscie)", "Pokaz na Zywo (DJ)")
)

st.sidebar.markdown("---")

# Tryb debugowania — włącz żeby zobaczyć surowe odpowiedzi Gemini
debug_mode = st.sidebar.checkbox("🔍 Tryb DEBUG (Gemini)", value=False)

st.sidebar.markdown("---")
if st.sidebar.button("Wyczysc cala galerie"):
    try:
        lock = FileLock(LOCK_FILE)
        with lock:
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
        if cloud_name and cloudinary_key and cloudinary_secret:
            try:
                resources = cloudinary.api.resources(
                    type="upload", prefix=CLOUDINARY_FOLDER, max_results=500
                )
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

# ─── Session state ─────────────────────────────────────────────────────────────

for key, default in [
    ("current_index", 0),
    ("last_slide_time", time.time()),
    ("uploader_key", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Widok: Wgrywanie zdjęć ───────────────────────────────────────────────────

if view_mode == "Wgraj Zdjecie (Goscie)":
    st.title("18. Urodziny Zuzi 🎂")
    st.header("Wrzuć fotki na żywo na ekran projektora!")

    if not cloud_name or not gemini_key:
        st.error("Brak skonfigurowanych kluczy w Streamlit Secrets!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjęcia z telefonu:",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}",
        )

        if uploaded_files:
            if st.button("Wyślij zdjęcia do pokazu"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_files = len(uploaded_files)

                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analizuję zdjęcie {i + 1} z {total_files}...")

                    try:
                        image_bytes = uploaded_file.getvalue()
                        img = Image.open(BytesIO(image_bytes))

                        if img.mode in ("RGBA", "P", "CMYK"):
                            img = img.convert("RGB")

                        img.thumbnail((1600, 1600), Image.LANCZOS)

                        # Wgraj do Cloudinary
                        upload_buf = BytesIO()
                        img.save(upload_buf, format="JPEG", quality=85)
                        upload_buf.seek(0)

                        upload_result = cloudinary.uploader.upload(
                            upload_buf, folder=CLOUDINARY_FOLDER
                        )
                        image_url = upload_result.get("secure_url")

                        if not image_url:
                            st.warning(f"Zdjęcie {i + 1}: błąd wgrywania do Cloudinary.")
                            progress_bar.progress((i + 1) / total_files)
                            continue

                        # Generuj opis AI
                        caption = generate_caption(img, debug=debug_mode)
                        save_item(image_url, caption)

                        if debug_mode:
                            st.sidebar.success(f"#{i+1} caption: {caption}")

                    except Exception as e:
                        st.error(f"Błąd przy zdjęciu {i + 1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("✅ Gotowe! Zdjęcia trafiły na ekran.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()

# ─── Widok: Projektor (DJ) ────────────────────────────────────────────────────

else:
    st.title("Ekran Projektora / Pokaz na Żywo 🎉")
    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarządzanie zdjęciami")

    items = load_gallery()

    if items:
        for idx, it in enumerate(items):
            col_txt, col_btn = st.sidebar.columns([3, 1])
            col_txt.text(f"#{idx + 1}: {it['caption'][:20]}...")
            if col_btn.button("Skasuj", key=f"del_{idx}"):
                items.pop(idx)
                save_full_gallery(items)
                st.session_state.current_index = 0
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Ustawienia Pokazu")
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdów", value=True)
    slide_delay_sec = st.sidebar.slider("Czas wyświetlania (sekundy)", 3, 15, 5)

    if items:
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        st.image(item["url"], use_container_width=True)
        st.markdown(
            f"<h2 style='text-align: center;'>{item['caption']}</h2>",
            unsafe_allow_html=True,
        )
        st.caption(f"Zdjęcie {idx + 1} z {len(items)}")

        if auto_play and len(items) > 1:
            now = time.time()
            if now - st.session_state.last_slide_time >= slide_delay_sec:
                st.session_state.current_index = (idx + 1) % len(items)
                st.session_state.last_slide_time = now
                st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjęcia! Wrzuć coś z telefonu")
