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

@st.cache_resource
def get_gemini_model():
    generation_config = {
        "temperature": 1.3,
        "top_p": 0.95,
        "top_k": 40
    }
    return genai.GenerativeModel("gemini-2.0-flash", generation_config=generation_config)

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

def is_good_caption(text):
    if not text:
        return False
    clean = text.strip().lower()
    if len(clean) < 15:
        return False
    forbidden = [
        "nie mogę rozpoznać", "wydaje się", "prawdopodobnie",
        "nie jestem w stanie", "jako model", "przepraszam"
    ]
    for word in forbidden:
        if word in clean:
            return False
    return True

def get_dynamic_fallback(img):
    width, height = img.size
    ratio = width / height

    vertical_fallbacks = [
        "Ktoś tu dumnie pozuje w pełnej okazałości! 📸",
        "Pionowe ujęcie, idealnie uchwycona sylwetka! 🔥",
        "Stylówa na tym zdjęciu nie do przebicia! ✨",
        "Tak się pozuje na 18-ce Zuzi! 🥂",
        "Wysoko wysoko, obiektyw skierowany na gwiazdę wieczoru! ⭐",
        "Kadr pionowy, a emocje maksymalne! 💥",
        "Ktoś tu ewidentnie skradł show! 👑",
        "Elegancka poza, pełna koncentracja przed obiektywem! 🎭",
        "Takie ujęcia zostają w pamięci na zawsze! 💫",
        "Model / modelka gotowa na wybieg! 💃",
        "Z bliska widać każdy szczegół tej stylizacji! 🕶️",
        "Nawet bez AI widać, że tu się dzieje magia! 🔮",
        "Kadr na medal, bez dwóch zdań! 🎯",
        "Uśmiech do kamery i lecimy dalej z imprezą! 😄",
        "Takie pamiątki z urodzin Zuzi są bezcenne! 💎",
        "Baczność! Kadr pod kontrolą! 🫡",
        "Oto definicja dobrej zabawy w pionie! 🚀",
        "Taka fotka to czysty złoty materiał! 🏆",
        "Klimat rodem z czerwonego dywanu! 🎬",
        "Kto tu próbuje ukryć uśmiech? 🤭",
        "Zadziorne spojrzenie prosto w obiektyw! 👀",
        "Styl i klasa na jednym, pionowym kadrze! 🍸",
        "Niezapomniane chwilerka z osiemnastki! 🥳",
        "Widać, że energia dopisuje od samego początku! ⚡",
        "Takie ujęcia budują tę imprezę! 🏗️"
    ]

    horizontal_fallbacks = [
        "Szeroki kadr, żeby zmieścić całą tę ekipę! 🌍",
        "Impreza rozkręca się na pełnej szerokości ekranu! 🚀",
        "Pełen kadr, pełen spontan! 📸",
        "Tu się dzieje więcej, niż obiektyw zdoła objąć! 🔥",
        "Szerokokątne szaleństwo u Zuzi! 🎉",
        "Wszystkich nas nie zmieścicie, a jednak się udało! 🥳",
        "Panoramka warta każdej sekundnika! ⏳",
        "Tego widoku nie da się zapomnieć! 🌅",
        "Kadr poziomy, a emocje wystrzeliły w kosmos! 🌌",
        "Ekipa w komplecie, klimat nie do podrobienia! 🍻",
        "Szeroki horyzont i czysta radość! 🌈",
        "Tak wygląda pełna integracja towarzyska! 🤝",
        "Ujęcie z perspektywy centrali dowodzenia! 🎛️",
        "Wszystko pod kontrolą, chociaż parkiet płonie! 🔥",
        "Szeroki uśmiech dla całej widowni! 😄",
        "Taki krajobraz imprezowy to my rozumiemy! 🌆",
        "Kadr pełen życia, energii i dobrego humoru! 🎈",
        "Z tej perspektywy widać znacznie więcej! 🔭",
        "Gromadka w natarciu, kto ich zatrzyma? 🏃‍♂️",
        "Szeroko, głośno i absolutnie legalnie! 🎶",
        "Wspomnienia uwiecznione w pełnej szerokości! 🖼️",
        "Imprezowy kadr panoramiczny! 🎪",
        "Tutaj nikt nie stoi w kącie! 🕺",
        "Pełna panorama radości na osiemnastce! 🌟",
        "Złote proporcje dla najlepszych momentów! 🥇"
    ]

    if ratio < 1.0:
        return random.choice(vertical_fallbacks)
    else:
        return random.choice(horizontal_fallbacks)

def generate_unique_caption(img):
    model = get_gemini_model()

    # KROK 1: Analiza wizualna (Opis elementów)
    step1_prompt = (
        "Przeanalizuj to zdjęcie z 18. urodzin. Wypisz w 1 krótkim zdaniu po polsku detale: "
        "kto/co na nim jest, kolory ubrań, rekwizyty w rękach, emocje lub otoczenie."
    )

    image_description = ""
    for attempt in range(1, 6):
        try:
            response = model.generate_content([step1_prompt, img])
            if response and hasattr(response, "text") and response.text:
                image_description = response.text.strip()
                if len(image_description) > 5:
                    break
        except Exception as e:
            sleep_time = 2 ** (attempt - 1)
            time.sleep(sleep_time)

    # KROK 2: Generowanie podpisu złośliwego komika na podstawie opisu
    step2_prompt = (
        f"Na podstawie tego opisu zdjęcia: '{image_description}', "
        "jesteś bezczelnym, zabawnym komikiem na 18. urodzinach. "
        "Napisz złośliwy, dowcipny i ironiczny komentarz (1-2 zdania z emoji), odnoszący się do tych detali. "
        "ZAKAZ ogólników. Zwróć absolutnie tylko sam tekst podpisu, bez cudzysłowów."
    )

    for attempt in range(1, 6):
        try:
            response = model.generate_content([step2_prompt, img])
            if response and hasattr(response, "text") and response.text:
                caption = response.text.strip().replace('"', '').replace("'", "")
                if is_good_caption(caption):
                    return caption
        except Exception as e:
            sleep_time = 2 ** (attempt - 1)
            time.sleep(sleep_time)

    # Jeśli AI zawiedzie, zwracamy unikalny fallback oparty o geometrię zdjęcia
    return get_dynamic_fallback(img)

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

                total_files = len(uploaded_files)
                pending_items = []

                # ETAP 1: Błyskawiczny upload i zapis z szybkim fallbackiem, żeby zdjęcia pojawiły się natychmiast
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Przesyłam zdjęcie {i+1} z {total_files}...")
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

                        if image_url:
                            initial_caption = get_dynamic_fallback(img)
                            save_item(image_url, initial_caption)
                            # Zapisujemy referencję do analizy w tle
                            pending_items.append({"url": image_url, "img_obj": img})
                    except Exception as e:
                        st.error(f"Błąd przesyłania zdjęcia {i+1}: {e}")

                    progress_bar.progress((i + 1) / total_files)

                # ETAP 2: Analiza AI w tle i aktualizacja wpisów w pliku
                status_text.text("Zdjęcia na ekranie! Trwa inteligentna analiza AI w tle...")

                current_items = load_gallery()
                for pending in pending_items:
                    ai_caption = generate_unique_caption(pending["img_obj"])
                    # Podmieniamy wstępny fallback na docelowy opis AI w liście elementów
                    for item in current_items:
                        if item["url"] == pending["url"]:
                            item["caption"] = ai_caption

                save_full_gallery(current_items)

                status_text.text("Gotowe! Wszystkie zdjęcia wgrane i przeanalizowane.")
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

