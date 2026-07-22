import os
import time
import base64
from io import BytesIO

from PIL import Image
import cloudinary
import cloudinary.api
import cloudinary.uploader
from filelock import FileLock
import anthropic
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Zuzia 18", layout="wide")

anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")
cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

st.sidebar.markdown("### Diagnostyka kluczy")
st.sidebar.write("ANTHROPIC_API_KEY:", "OK" if anthropic_key else "BRAK")
st.sidebar.write("Dlugosc klucza:", len(anthropic_key))
st.sidebar.write("CLOUDINARY:", "OK" if cloud_name else "BRAK")
st.sidebar.markdown("---")

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret,
    )

DB_FILE = "galeria_zuzi.txt"
LOCK_FILE = "galeria.lock"
CLOUDINARY_FOLDER = "18_zuzia"

PROMPT_WITH_IMAGE = (
    "Jestes rozbawionym gosciem na 18. urodzinach Zuzi. "
    "Napisz krotki zabawny komentarz do tego zdjecia. Max 2 zdania i emoji."
)


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


def generate_caption(img_pil: Image.Image) -> str:
    if not anthropic_key:
        return "BRAK KLUCZA ANTHROPIC"

    buf = BytesIO()
    img_pil.save(buf, format="JPEG", quality=85)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": PROMPT_WITH_IMAGE,
                        },
                    ],
                }
            ],
        )

        # Pelna diagnostyka odpowiedzi
        st.sidebar.markdown("### Odpowiedz Claude:")
        st.sidebar.write("Liczba content blocks:", len(message.content))
        for i, block in enumerate(message.content):
            st.sidebar.write(f"Block {i} type:", block.type)
            if hasattr(block, "text"):
                st.sidebar.write(f"Block {i} text:", repr(block.text))

        text = message.content[0].text.strip()
        if len(text) > 3:
            return text
        return "Za krotka odpowiedz: " + repr(text)

    except Exception as ex:
        st.sidebar.error(f"BLAD: {ex}")
        return f"Blad: {ex}"


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

for key, default in [
    ("current_index", 0),
    ("last_slide_time", time.time()),
    ("uploader_key", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if view_mode == "Wgraj Zdjecie (Goscie)":
    st.title("18. Urodziny Zuzi")
    st.header("Wrzuc fotki na zywo na ekran projektora!")

    if not cloud_name or not anthropic_key:
        st.error("Brak skonfigurowanych kluczy w Streamlit Secrets!")
    else:
        uploaded_files = st.file_uploader(
            "Wybierz zdjecia z telefonu:",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}",
        )

        if uploaded_files:
            if st.button("Wyslij zdjecia do pokazu"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_files = len(uploaded_files)

                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analizuje zdjecie {i + 1} z {total_files}...")

                    try:
                        image_bytes = uploaded_file.getvalue()
                        img = Image.open(BytesIO(image_bytes))

                        if img.mode in ("RGBA", "P", "CMYK"):
                            img = img.convert("RGB")

                        img.thumbnail((1600, 1600), Image.LANCZOS)

                        upload_buf = BytesIO()
                        img.save(upload_buf, format="JPEG", quality=85)
                        upload_buf.seek(0)

                        upload_result = cloudinary.uploader.upload(
                            upload_buf, folder=CLOUDINARY_FOLDER
                        )
                        image_url = upload_result.get("secure_url")

                        if not image_url:
                            st.warning(f"Zdjecie {i + 1}: blad wgrywania do Cloudinary.")
                            progress_bar.progress((i + 1) / total_files)
                            continue

                        caption = generate_caption(img)
                        save_item(image_url, caption)

                    except Exception as e:
                        st.error(f"Blad przy zdjeciu {i + 1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("Gotowe! Zdjecia trafiły na ekran.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()

else:
    st.title("Ekran Projektora - Pokaz na Zywo")
    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarzadzanie zdjeciami")

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
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdow", value=True)
    slide_delay_sec = st.sidebar.slider("Czas wyswietlania (sekundy)", 3, 15, 5)

    if items:
        if st.session_state.current_index >= len(items):
            st.session_state.current_index = 0

        idx = st.session_state.current_index
        item = items[idx]

        # DODANY STYL: ograniczenie wysokości zdjęcia, aby komentarz zawsze był widoczny
        st.markdown(
            """
            <style>
            .stApp img {
                max-height: 55vh !important;
                width: auto !important;
                margin: 0 auto;
                display: block;
                object-fit: contain;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            st.image(item["url"], use_container_width=True)
            st.markdown(
                f"<h2 style='text-align: center;'>{item['caption']}</h2>",
                unsafe_allow_html=True,
            )
            st.caption(f"Zdjecie {idx + 1} z {len(items)}")

        if auto_play and len(items) > 1:
            now = time.time()
            if now - st.session_state.last_slide_time >= slide_delay_sec:
                st.session_state.current_index = (idx + 1) % len(items)
                st.session_state.last_slide_time = now
                st.rerun()
    else:
        st.info("Czekamy na pierwsze zdjecia! Wrzuc cos ze swojego telefonu.")
