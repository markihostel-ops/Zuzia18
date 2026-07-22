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

gemini_key = st.secrets.get("GEMINI_API_KEY", "")
cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")
cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret
    )

if gemini_key:
    genai.configure(api_key=gemini_key)

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


def extract_text_from_response(response) -> str:
    """
    Bezpiecznie wyciąga tekst z obiektu odpowiedzi Gemini,
    niezależnie od struktury zwróconej przez SDK.
    """
    # Metoda 1: bezpośrednie .text
    try:
        if response.text and len(response.text.strip()) > 3:
            return response.text.strip()
    except Exception:
        pass

    # Metoda 2: przez .parts
    try:
        for part in response.parts:
            t = getattr(part, "text", None)
            if t and len(t.strip()) > 3:
                return t.strip()
    except Exception:
        pass

    # Metoda 3: przez candidates → content → parts
    try:
        for candidate in response.candidates:
            for part in candidate.content.parts:
                t = getattr(part, "text", None)
                if t and len(t.strip()) > 3:
                    return t.strip()
    except Exception:
        pass

    return ""


def generate_caption(img_pil: Image.Image) -> str:
    """
    Generuje śmieszny, imprezowy opis zdjęcia przez Gemini.
    Zwraca tekst opisu lub awaryjny napis jeśli coś pójdzie nie tak.
    """
    if not gemini_key:
        return "Impreza u Zuzi w pełnym biegu! 🥂🔥"

    # Przygotuj obraz jako JPEG w pamięci
    buf = BytesIO()
    img_pil.save(buf, format="JPEG", quality=85)
    image_bytes = buf.getvalue()

    # Przekaż jako surowe bajty przez genai.types.Part
    image_part = {
        "mime_type": "image/jpeg",
        "data": image_bytes,
    }

    prompt = (
        "Jesteś rozbawionym, lekko złośliwym gościem na 18. urodzinach Zuzi. "
        "Twoje zadanie: opisać TO KONKRETNE zdjęcie w jednym lub dwóch krótkich zdaniach. "
        "Skoncentruj się wyłącznie na tym, co faktycznie widzisz w kadrze: "
        "co robią osoby, jakie mają miny, co trzymają w rękach, jakie gesty wykonują, "
        "gdzie stoją lub siedzą, co dzieje się w tle. "
        "Napisz żart lub komentarz nawiązujący KONKRETNIE do tych detali — nie pisz ogólników o imprezie. "
        "Ton: luźny, imprezowy, zabawny, odrobinę złośliwy, ale absolutnie nieobraźliwy — "
        "tak żeby bohaterowie zdjęcia sami się roześmiali. "
        "Dodaj 1-2 pasujące emoji. "
        "Zwróć WYŁĄCZNIE sam tekst komentarza — bez cudzysłowów, bez wstępów, bez wyjaśnień."
    )

    generation_config = {
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 200,
    }
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=generation_config,
        safety_settings=safety_settings,
    )

    last_error = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                contents=[
                    {"role": "user", "parts": [image_part, {"text": prompt}]}
                ]
            )

            text = extract_text_from_response(response)
            if text:
                # Usuń ewentualne cudzysłowy
                text = text.replace('"', '').replace("'", "").strip()
                return text

        except Exception as ex:
            last_error = ex
            time.sleep(0.8)

    # Jeśli wszystkie próby się nie powiodły — pokaż błąd w sidebarze dla DJ-a
    if last_error:
        st.sidebar.warning(f"Gemini error (zdjęcie): {last_error}")

    return "Zuzia i ekipa w akcji! 🎉🔥"


# ─── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("Panel Sterowania")
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

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "last_slide_time" not in st.session_state:
    st.session_state.last_slide_time = time.time()

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

# ─── Widok: Wgrywanie zdjęć (goście) ──────────────────────────────────────────

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

                        # Zachowaj rozsądny rozmiar
                        img.thumbnail((1600, 1600), Image.LANCZOS)

                        # Wgraj oryginał (po przeskalowaniu) do Cloudinary
                        upload_buf = BytesIO()
                        img.save(upload_buf, format="JPEG", quality=85)
                        upload_buf.seek(0)

                        upload_result = cloudinary.uploader.upload(
                            upload_buf, folder=CLOUDINARY_FOLDER
                        )
                        image_url = upload_result.get("secure_url")

                        if not image_url:
                            st.warning(f"Zdjęcie {i + 1}: nie udało się wgrać do Cloudinary.")
                            progress_bar.progress((i + 1) / total_files)
                            continue

                        # Generuj opis AI
                        caption = generate_caption(img)
                        save_item(image_url, caption)

                    except Exception as e:
                        st.error(f"Błąd przy zdjęciu {i + 1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("✅ Gotowe! Zdjęcia trafiły na ekran.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()

# ─── Widok: Ekran projektora (DJ) ─────────────────────────────────────────────

else:
    st.title("Ekran Projektora / Pokaz na Żywo 🎉")

    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarządzanie pojedynczymi zdjęciami")

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
            current_time = time.time()
            if current_time - st.session_state.last_slide_time >= slide_delay_sec:
                st.session_state.current_index = (
                    st.session_state.current_index + 1
                ) % len(items)
                st.session_state.last_slide_time = current_time
                st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjęcia! Wrzuć coś ze swojego telefonu.")
