import os
import time
import base64
import random
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ExifTags
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

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
QUEUE_FILE = "guest_queue.txt"
QUEUE_LOCK = "guest_queue.lock"
CLOUDINARY_FOLDER = "18_zuzia"
PLACEHOLDER_CAPTION = "Zaraz skomentuje... 👀"
MAX_PHOTOS = 10
MAX_CAPTION_LEN = 150
AI_TIMEOUT_SEC = 55

AI_EXECUTOR = ThreadPoolExecutor(max_workers=5)

ALL_GUESTS = [
    "Zuzia B (solenizantka, 18 lat)",
    "Kinga (mama Zuzi B)",
    "Krzysiek (tata Zuzi B)",
    "Bartek (brat Zuzi B)",
    "Werka (dziewczyna Bartka)",
    "Babcia Hania",
    "Dziadek Kazik",
    "Karolcia (ciocia Zuzi B)",
    "Patryk (wujek, maz Karolci)",
    "Rafal (wujek Zuzi B)",
    "Juda (ciocia, zona Rafala)",
    "Nikola (corka Rafala i Judy)",
    "Kacper (chlopak Nikoli)",
    "Daniel K (syn Rafala i Judy)",
    "Julia (zona Daniela K)",
    "Babcia Malgosia",
    "Mariusz (wujek Zuzi B)",
    "Eliza (ciotka, zona Mariusza)",
    "Natalia (corka Mariusza i Elizy)",
    "Dawid (maz Natalii)",
    "Ola (corka Mariusza i Elizy)",
    "Sebastian (maz Oli)",
    "Aga (ciocia Zuzi B)",
    "Radek (wujek, maz Agi)",
    "Ilona (przyjaciolka rodziny)",
    "Czarek (przyjaciel rodziny, maz Ilony)",
    "Antek (syn Ilony i Czarka)",
    "Klaudia (corka Ilony i Czarka)",
    "Hubert (chlopak Klaudii)",
    "Iwona (przyjaciolka rodziny)",
    "Robert (przyjaciel rodziny, maz Iwony)",
    "Kamil (syn Iwony i Roberta)",
    "Karolina (dziewczyna Kamila)",
    "Olek (syn Iwony i Roberta)",
    "Agata (dziewczyna Olka)",
    "Wioletta (mama Zuzi M)",
    "Marcin (tata Zuzi M)",
    "Zuzia M (najlepsza przyjaciolka Zuzi B)",
    "Oksana (przyjaciolka rodziny)",
    "Marlena (przyjaciolka rodziny)",
    "Daniel (przyjaciel rodziny)",
    "Pati (przyjaciolka rodziny)",
]


def get_next_guest() -> str:
    lock = FileLock(QUEUE_LOCK)
    with lock:
        queue = []
        if os.path.exists(QUEUE_FILE):
            try:
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    queue = [line.strip() for line in f if line.strip()]
            except Exception:
                queue = []
        if not queue:
            queue = ALL_GUESTS.copy()
            random.shuffle(queue)
        guest = queue.pop(0)
        try:
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                for item in queue:
                    f.write(f"{item}\n")
        except Exception:
            pass
    return guest


def get_prompt(guest: str) -> str:
    imie = guest.split("(")[0].strip().split()[0]
    return f"""Jestes dowcipnym konferansjerem na 18. urodzinach Zuzi B.
Napisz JEDEN smieszny komentarz do zdjecia z imprezy.

IMIE DO WPLECENIA: {imie}

ZELAZNA ZASADA KTOREJ NIE WOLNO LAMAC:
Nie wiesz kto jest na zdjeciu. Moze to byc ktokolwiek.
Dlatego komentarz MUSI byc zbudowany tak:
- NAJPIERW opisz sytuacje ze zdjecia (co sie dzieje, jaki nastroj, co widac)
- POTEM dodaj zdanie gdzie {imie} pojawia sie jako ktos kto jest GDZIE INDZIEJ lub cos MOWI Z BOKU

IMIE NIGDY nie moze byc podmiotem opisujacym osobe ze zdjecia.
IMIE moze byc tylko w zdaniu gdzie ta osoba jest poza kadrem.

WZORCE ZDANIA Z IMIENIEM:
- "...a {imie} podobno dopiero szuka miejsca do siedzenia"
- "...{imie} twierdzi ze to nie on/ona zaczal/a"
- "...podobno {imie} juz zamawia nastepna kolejke"
- "...{imie} z boku juz klaszcze"

PRZYKLAD PELNEGO KOMENTARZA:
Zdjecie: ktos tanczy
DOBRZE: "Parkiet sie trzasie w posadach, a {imie} podobno dopiero sciaga buty zeby dolaczyc 🕺"
ZLE: "{imie} tak swietnie tanczy" albo "{imie} wyglada na rozbawionego"

Bez cudzyslowow i gwiazdek. Tylko gotowy tekst."""


def fix_image_orientation(img: Image.Image) -> Image.Image:
    try:
        exif = img._getexif()
        if exif is None:
            return img
        orientation_key = next(
            (k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None
        )
        if orientation_key is None or orientation_key not in exif:
            return img
        orientation = exif[orientation_key]
        rotations = {
            2: lambda i: i.transpose(Image.FLIP_LEFT_RIGHT),
            3: lambda i: i.rotate(180),
            4: lambda i: i.rotate(180).transpose(Image.FLIP_LEFT_RIGHT),
            5: lambda i: i.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT),
            6: lambda i: i.rotate(-90, expand=True),
            7: lambda i: i.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT),
            8: lambda i: i.rotate(90, expand=True),
        }
        if orientation in rotations:
            img = rotations[orientation](img)
    except Exception:
        pass
    return img


def resize_to(img: Image.Image, max_size: int) -> Image.Image:
    w, h = img.size
    if w <= max_size and h <= max_size:
        return img
    ratio = min(max_size / w, max_size / h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)


def prepare_image(image_bytes: bytes) -> Image.Image:
    img = Image.open(BytesIO(image_bytes))
    if img.mode in ("RGBA", "P", "CMYK", "LA"):
        img = img.convert("RGB")
    img = fix_image_orientation(img)
    return img


def compress_for_projector(img: Image.Image) -> BytesIO:
    img_r = resize_to(img, 1920)
    quality = 88
    while True:
        buf = BytesIO()
        img_r.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() / 1024 <= 800 or quality <= 50:
            break
        quality -= 6
    buf.seek(0)
    return buf


def compress_for_ai(img: Image.Image) -> bytes:
    img_r = resize_to(img, 800)
    quality = 80
    while True:
        buf = BytesIO()
        img_r.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() / 1024 <= 300 or quality <= 40:
            break
        quality -= 6
    return buf.getvalue()


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
    if len(new_caption) > MAX_CAPTION_LEN:
        new_caption = new_caption[:MAX_CAPTION_LEN].rsplit(" ", 1)[0] + "..."
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


def upload_to_cloudinary(upload_buf: BytesIO) -> str:
    for attempt in range(3):
        try:
            upload_buf.seek(0)
            result = cloudinary.uploader.upload(
                upload_buf, folder=CLOUDINARY_FOLDER
            )
            url = result.get("secure_url", "")
            if url:
                return url
        except Exception:
            time.sleep(1)
    return ""


def generate_caption_for_url(image_url: str, img_pil: Image.Image):
    if not anthropic_key:
        update_caption(image_url, "Ekipa bawi sie wysmienicie! 🎉🔥")
        return
    start = time.time()
    image_bytes_ai = compress_for_ai(img_pil)
    image_b64 = base64.standard_b64encode(image_bytes_ai).decode("utf-8")
    guest = get_next_guest()
    prompt = get_prompt(guest)
    for attempt in range(3):
        if time.time() - start > AI_TIMEOUT_SEC:
            break
        try:
            client = anthropic.Anthropic(api_key=anthropic_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
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
                            {"type": "text", "text": prompt},
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
    update_caption(image_url, "Ekipa bawi sie wysmienicie! 🎉🔥")


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("Panel Sterowania")
view_mode = st.sidebar.radio(
    "Wybierz widok:",
    ("Wgraj Zdjecie (Goscie)", "Pokaz na Zywo (DJ)"),
    key="view_mode_radio"
)
st.sidebar.markdown("---")

if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

if not st.session_state.confirm_clear:
    if st.sidebar.button("Wyczysc cala galerie", key="btn_wyczysc"):
        st.session_state.confirm_clear = True
        st.rerun()
else:
    st.sidebar.warning("Na pewno chcesz wyczyścić całą galerię?")
    col_yes, col_no = st.sidebar.columns(2)
    if col_yes.button("TAK, czysc", key="btn_yes"):
        try:
            lock = FileLock(LOCK_FILE)
            with lock:
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
            if os.path.exists(QUEUE_FILE):
                os.remove(QUEUE_FILE)
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
        except Exception as e:
            st.sidebar.error(f"Blad: {e}")
        st.session_state.confirm_clear = False
        st.rerun()
    if col_no.button("NIE, anuluj", key="btn_no"):
        st.session_state.confirm_clear = False
        st.rerun()

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
    st.title("18. Urodziny Zuzi 🎉")
    st.header("Wrzuc fotki na zywo na ekran projektora!")
    st.info(f"📸 Wrzucaj maksymalnie {MAX_PHOTOS} zdjec na raz — jak sie wyswietla, mozesz wrzucic kolejne!")

    # Sprawdz klucze i pokaz co brakuje
    brakujace = []
    if not anthropic_key:
        brakujace.append("ANTHROPIC_API_KEY")
    if not cloud_name:
        brakujace.append("CLOUDINARY_CLOUD_NAME")
    if not cloudinary_key:
        brakujace.append("CLOUDINARY_API_KEY")
    if not cloudinary_secret:
        brakujace.append("CLOUDINARY_API_SECRET")

    if brakujace:
        st.error(f"Brak kluczy w Streamlit Secrets: {', '.join(brakujace)}")
    else:
        uploaded_files = st.file_uploader(
            f"Wybierz maksymalnie {MAX_PHOTOS} zdjec z telefonu:",
            type=["jpg", "jpeg", "png", "heic"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.uploader_key}",
        )

        if uploaded_files:
            if len(uploaded_files) > MAX_PHOTOS:
                st.error(f"Wybrales {len(uploaded_files)} zdjec — za duzo! Odznacz kilka, mozna max {MAX_PHOTOS} na raz.")
                uploaded_files = None
            else:
                st.write(f"Wybrano: {len(uploaded_files)} z {MAX_PHOTOS} zdjec")

        if uploaded_files:
            if st.button("Wyslij zdjecia do pokazu 🚀", key="btn_wyslij"):
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_files = len(uploaded_files)
                success_count = 0

                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Wgrywam zdjecie {i + 1} z {total_files}...")
                    try:
                        image_bytes = uploaded_file.getvalue()
                        img = prepare_image(image_bytes)
                        upload_buf = compress_for_projector(img)
                        image_url = upload_to_cloudinary(upload_buf)

                        if not image_url:
                            st.warning(f"Zdjecie {i + 1}: blad wgrywania, pomijam.")
                            progress_bar.progress((i + 1) / total_files)
                            continue

                        save_item(image_url, PLACEHOLDER_CAPTION)
                        AI_EXECUTOR.submit(
                            generate_caption_for_url,
                            image_url,
                            img.copy()
                        )
                        success_count += 1

                    except Exception as e:
                        st.warning(f"Zdjecie {i + 1}: blad — {e}")

                    progress_bar.progress((i + 1) / total_files)

                if success_count > 0:
                    status_text.text(f"✅ Gotowe! {success_count} zdjec trafiło na ekran projektora!")
                else:
                    status_text.text("❌ Nie udalo sie wgrac zadnego zdjecia. Sprobuj ponownie.")

                time.sleep(2)
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
    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdow", value=True, key="auto_play")
    slide_delay_sec = st.sidebar.slider("Czas wyswietlania (sekundy)", 3, 15, 5, key="slide_delay")

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

        next_idx = (idx + 1) % len(items)
        next_url = items[next_idx]["url"].replace("/upload/", "/upload/w_1200,q_auto,f_auto/")
        st.markdown(f'<link rel="prefetch" href="{next_url}">', unsafe_allow_html=True)

        col1, col2, col3 = st.columns([0.5, 5, 0.5])
        with col2:
            st.image(display_url, use_container_width=True)
            clean_caption = item["caption"].replace("**", "").replace('"', '').strip()
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
