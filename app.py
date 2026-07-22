import os
import time
import base64
import threading
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

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret,
    )

DB_FILE = "galeria_zuzi.txt"
LOCK_FILE = "galeria.lock"
CLOUDINARY_FOLDER = "18_zuzia"
PENDING_FILE = "pending_captions.txt"
PENDING_LOCK = "pending.lock"

PROMPT_WITH_IMAGE = (
    "Jestes rozbawionym gosciem na 18. urodzinach Zuzi. "
    "Napisz krotki zabawny komentarz do tego zdjecia. Max 2 zdania i emoji. "
    "Nie uzywaj cudzyslowow ani gwiazdek."
)

PLACEHOLDER_CAPTION = "Zaraz skomentuje... 👀"


def load_gallery():
    """Wczytuje galerie - najnowsze zdjecia na poczatku."""
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
    items.reverse()
    return items


def save_item(url, caption):
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            with open(DB_FILE, "a", encoding="utf-8") as f:
                f.write(f"{url}|{caption}\n")
    except Exception as e:
        st.error(f"Blad zapisu: {e}")


def update_caption(url, new_caption):
    """Aktualizuje komentarz dla konkretnego URL w pliku."""
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            if not os.path.exists(DB_FILE):
                return
            with open(DB_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(DB_FILE, "w", encoding="utf-8") as f:
                for line in lines:
                    if "|" in line and line.startswith(url):
                        f.write(f"{url}|{new_caption}\n")
                    else:
                        f.write(line)
    except Exception:
        pass


def save_full_gallery(items):
    lock = FileLock(LOCK_FILE)
    try:
        with lock:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                for it in reversed(items):
                    f.write(f"{it['url']}|{it['caption']}\n")
    except Exception as e:
        st.error(f"Blad zapisu: {e}")


def generate_caption_for_url(image_url: str, img_pil: Image.Image):
    """
    Generuje komentarz w tle i aktualizuje plik.
    Uruchamiane w osobnym watku.
    """
    if not anthropic_key:
        return

    buf = BytesIO()
    img_copy = img_pil.copy()
    img_copy.thumbnail((1024, 1024), Image.LANCZOS)
    img_copy.save(buf, format="JPEG", quality=80)
    image_b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")

    for attempt in range(3):
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
            text = message.content[0].text.strip()
            text = text.replace("**", "").replace('"', '').strip()
            if len(text) > 3:
                update_caption(image_url, text)
                return
        except Exception:
            time.sleep(2)

    # Jesli wszystkie proby zawiodly - zostaw placeholder zastepczy
    update_caption(image_url, "Zuzia i ekipa daja czadu! 🎉🔥")


# ─── Sidebar ──────────────────────────────────────────────────────────────────

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
        st.session_state.last_known_count = 0
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Blad: {e}")

# ─── Session state ─────────────────────────────────────────────────────────────

for key, default in [
    ("current_index", 0),
    ("last_slide_time", time.time()),
    ("uploader_key", 0),
    ("last_known_count", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ─── Widok: Wgrywanie zdjec ───────────────────────────────────────────────────

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
                    status_text.text(f"Wgrywam zdjecie {i + 1} z {total_files}...")

                    try:
                        image_bytes = uploaded_file.getvalue()
                        img = Image.open(BytesIO(image_bytes))

                        if img.mode in ("RGBA", "P", "CMYK"):
                            img = img.convert("RGB")

                        # Wgraj oryginał do Cloudinary
                        upload_buf = BytesIO()
                        img.save(upload_buf, format="JPEG", quality=92)
                        upload_buf.seek(0)

                        upload_result = cloudinary.uploader.upload(
                            upload_buf, folder=CLOUDINARY_FOLDER
                        )
                        image_url = upload_result.get("secure_url")

                        if not image_url:
                            st.warning(f"Zdjecie {i + 1}: blad wgrywania.")
                            progress_bar.progress((i + 1) / total_files)
                            continue

                        # Zapisz od razu z placeholderem - zdjecie pojawia sie natychmiast
                        save_item(image_url, PLACEHOLDER_CAPTION)

                        # Uruchom komentowanie w tle (osobny watek)
                        t = threading.Thread(
                            target=generate_caption_for_url,
                            args=(image_url, img.copy()),
                            daemon=True
                        )
                        t.start()

                    except Exception as e:
                        st.error(f"Blad przy zdjeciu {i + 1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("Gotowe! Zdjecia sa juz na ekranie, komentarze dochodzą za chwile.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()

# ─── Widok: Projektor (DJ) ────────────────────────────────────────────────────

else:
    st.title("Ekran Projektora - Pokaz na Zywo")
    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarzadzanie zdjeciami")

    items = load_gallery()
    current_count = len(items)

    # Jesli pojawily sie nowe zdjecia - wróc na poczatek
    if current_count > st.session_state.last_known_count:
        st.session_state.current_index = 0
        st.session_state.last_known_count = current_count

    if items:
        for idx, it in enumerate(items):
            col_txt, col_btn = st.sidebar.columns([3, 1])
            col_txt.text(f"#{idx + 1}: {it['caption'][:20]}...")
            if col_btn.button("Skasuj", key=f"del_{idx}"):
                items.pop(idx)
                save_full_gallery(items)
                st.session_state.current_index = 0
                st.session_state.last_known_count = len(items)
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

        display_url = item["url"].replace("/upload/", "/upload/w_1200,q_auto,f_auto/")

        st.markdown(
            """
            <style>
            .stApp img {
                max-height: 70vh !important;
                width: auto !important;
                margin: 0 auto;
                display: block;
                object-fit: contain;
                border-radius: 12px;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        # Prefetch kolejnego zdjecia
        next_idx = (idx + 1) % len(items)
        next_url = items[next_idx]["url"].replace("/upload/", "/upload/w_1200,q_auto,f_auto/")
        st.markdown(
            f'<link rel="prefetch" href="{next_url}">',
            unsafe_allow_html=True,
        )

        col1, col2, col3 = st.columns([0.5, 5, 0.5])
        with col2:
            st.image(display_url, use_container_width=True)
            clean_caption = item["caption"].replace("**", "").replace('"', '').strip()

            # Jesli komentarz jeszcze nie gotowy - pokaz animowany napis
            if clean_caption == PLACEHOLDER_CAPTION:
                st.markdown(
                    "<h2 style='text-align: center; margin-top: 15px; color: #aaa;'>✍️ Zaraz skomentuje...</h2>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<h2 style='text-align: center; margin-top: 15px;'>{clean_caption}</h2>",
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
