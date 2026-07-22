import os
import time
import base64
from io import BytesIO

from PIL import Image
import cloudinary
import cloudinary.api
import cloudinary.uploader
import anthropic
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# 1. Konfiguracja strony
st.set_page_config(page_title="Zuzia 18", layout="wide")

# 2. Pobieranie kluczy
anthropic_key = st.secrets.get("ANTHROPIC_API_KEY", "")
cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")
cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")

st.sidebar.markdown("### Diagnostyka kluczy")
st.sidebar.write("ANTHROPIC_API_KEY:", "OK" if anthropic_key else "BRAK")
st.sidebar.write("CLOUDINARY:", "OK" if cloud_name else "BRAK")
st.sidebar.markdown("---")

if cloud_name and cloudinary_key and cloudinary_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloudinary_key,
        api_secret=cloudinary_secret,
    )

CLOUDINARY_FOLDER = "18_zuzia"

PROMPT_WITH_IMAGE = (
    "Jestes rozbawionym gosciem na 18. urodzinach Zuzi. "
    "Napisz krotki zabawny komentarz do tego zdjecia. Max 2 zdania i emoji. Nie uzywaj cudzyslowow ani gwiazdek."
)

# 3. Trwałe ładowanie galerii z Cloudinary (odporne na restarty!)
def load_gallery():
    if not (cloud_name and cloudinary_key and cloudinary_secret):
        return []
    try:
        resources = cloudinary.api.resources(
            type="upload",
            prefix=CLOUDINARY_FOLDER,
            context=True,
            max_results=500,
        ).get("resources", [])

        # Sortowanie od najstarszych do najnowszych
        resources.sort(key=lambda x: x.get("created_at", ""))

        items = []
        for res in resources:
            url = res.get("secure_url", "")
            context = res.get("context", {}).get("custom", {})
            caption = context.get("caption", "Sto lat Zuzia! 🎉")
            public_id = res.get("public_id", "")
            if url:
                items.append({"url": url, "caption": caption, "public_id": public_id})
        return items
    except Exception as e:
        st.sidebar.error(f"Blad ladowania z Cloudinary: {e}")
        return []


def delete_photo_from_cloudinary(public_id):
    try:
        cloudinary.uploader.destroy(public_id)
    except Exception as e:
        st.error(f"Blad usuwania zdjecia: {e}")


# 4. Generowanie opisu AI z optymalizacją pod tokeny
def generate_caption(img_pil: Image.Image) -> str:
    if not anthropic_key:
        return "BRAK KLUCZA ANTHROPIC"

    buf = BytesIO()
    img_copy = img_pil.copy()
    img_copy.thumbnail((1024, 1024), Image.LANCZOS)
    img_copy.save(buf, format="JPEG", quality=80)
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

        text = message.content[0].text.strip()
        text = text.replace("**", "").replace('"', '').strip()

        if len(text) > 3:
            return text
        return "Sto lat Zuzia! 🎉"

    except Exception as ex:
        st.sidebar.error(f"BLAD AI: {ex}")
        return "Sto lat Zuzia! 🎉"


# 5. Panel nawigacji
st.sidebar.title("Panel Sterowania")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjecie (Goscie)", "Pokaz na Zywo (DJ)")
)

st.sidebar.markdown("---")

if st.sidebar.button("Wyczysc cala galerie"):
    try:
        if cloud_name and cloudinary_key and cloudinary_secret:
            resources = cloudinary.api.resources(
                type="upload", prefix=CLOUDINARY_FOLDER, max_results=500
            )
            public_ids = [res["public_id"] for res in resources.get("resources", [])]
            if public_ids:
                cloudinary.api.delete_resources(public_ids)
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

# --- WIDOK GOŚCI ---
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

                        caption = generate_caption(img)

                        upload_buf = BytesIO()
                        img.save(upload_buf, format="JPEG", quality=92)
                        upload_buf.seek(0)

                        # Zapis w chmurze z przypisanym podpisem (trwały storage)
                        cloudinary.uploader.upload(
                            upload_buf,
                            folder=CLOUDINARY_FOLDER,
                            context={"caption": caption}
                        )

                    except Exception as e:
                        st.error(f"Blad przy zdjeciu {i + 1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                status_text.text("Gotowe! Zdjecia trafiły na ekran.")
                time.sleep(1)
                st.session_state.uploader_key += 1
                st.rerun()

# --- WIDOK PROJEKTORA ---
else:
    st.title("Ekran Projektora - Pokaz na Zywo")
    st_autorefresh(interval=3000, key="dj_autorefresh")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Zarzadnanie zdjeciami")

    items = load_gallery()

    if items:
        for idx, it in enumerate(items):
            col_txt, col_btn = st.sidebar.columns([3, 1])
            col_txt.text(f"#{idx + 1}: {it['caption'][:20]}...")
            if col_btn.button("Skasuj", key=f"del_{idx}"):
                delete_photo_from_cloudinary(it["public_id"])
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

        # Serwowanie LEKKIEJ wersji obrazu dla projektora (w_1200)
        display_url = item["url"].replace("/upload/", "/upload/w_1200,q_auto,f_auto/")

        # Styl na duże zdjęcie na projektorze
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

        col1, col2, col3 = st.columns([0.5, 5, 0.5])
        with col2:
            st.image(display_url, use_container_width=True)
            clean_caption = item["caption"].replace("**", "").replace('"', '').strip()
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
