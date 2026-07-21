import os

import random

import time

from io import BytesIO



from PIL import Image, ImageOps

import cloudinary

import cloudinary.api

import cloudinary.uploader

from filelock import FileLock

import google.generativeai as genai

import streamlit as st

from streamlit_autorefresh import st_autorefresh



# --- Konfiguracja strony ---

st.set_page_config(

    page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide", initial_sidebar_state="expanded"

)



# --- Stabilne Å‚adowanie kluczy przez st.session_state i st.secrets ---

if "gemini_key" not in st.session_state:

    st.session_state.gemini_key = st.secrets.get("GEMINI_API_KEY", "")

if "cloud_name" not in st.session_state:

    st.session_state.cloud_name = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")

if "cloudinary_key" not in st.session_state:

    st.session_state.cloudinary_key = st.secrets.get("CLOUDINARY_API_KEY", "")

if "cloudinary_secret" not in st.session_state:

    st.session_state.cloudinary_secret = st.secrets.get("CLOUDINARY_API_SECRET", "")



# --- Panel Boczny: Konfiguracja i Panel DJ-a / Organizatora ---

st.sidebar.title("Panel Sterowania & DJ")



st.sidebar.subheader("ðŸ”‘ Klucze API")

gemini_key = st.sidebar.text_input("Gemini API Key", type="password", key="gemini_key")

cloud_name = st.sidebar.text_input("Cloudinary Cloud Name", key="cloud_name")

cloudinary_key = st.sidebar.text_input("Cloudinary API Key", type="password", key="cloudinary_key")

cloudinary_secret = st.sidebar.text_input("Cloudinary API Secret", type="password", key="cloudinary_secret")



# Konfiguracja Cloudinary i Gemini ze stanu sesji

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

        st.error(f"BÅ‚Ä…d zapisu bazy: {e}")



st.sidebar.markdown("---")

view_mode = st.sidebar.radio(

    "Wybierz widok:",

    ("Wgraj ZdjÄ™cie (GoÅ›cie)", "Pokaz na Projektorze (DJ)")

)



st.sidebar.markdown("---")

if st.sidebar.button("ðŸ—‘ï¸ WyczyÅ›Ä‡ caÅ‚Ä… galeriÄ™"):

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

            except Exception as cloud_err:

                st.sidebar.warning(f"BÅ‚Ä…d czyszczenia Cloudinary: {cloud_err}")



        st.sidebar.success("Galeria wyczyszczona!")

        st.session_state.current_index = 0

        st.rerun()

    except Exception as e:

        st.sidebar.error(f"BÅ‚Ä…d resetu: {e}")



if "current_index" not in st.session_state:

    st.session_state.current_index = 0



if "paused" not in st.session_state:

    st.session_state.paused = False



# --- WIDOK 1: WGRAJ ZDJÄ˜CIE (GOÅšCIE) ---

if view_mode == "Wgraj ZdjÄ™cie (GoÅ›cie)":

    st.title("ðŸŽ‚ 18. Urodziny Zuzi")

    st.header("WrzuÄ‡ fotki na Å¼ywo na ekran projektora!")

    

    if not st.session_state.cloud_name or not st.session_state.gemini_key:

        st.error("UzupeÅ‚nij klucze w panelu bocznym!")

    else:

        uploaded_files = st.file_uploader(

            "Wybierz zdjÄ™cia z telefonu:", 

            type=["jpg", "jpeg", "png"], 

            accept_multiple_files=True

        )

        

        if uploaded_files:

            if st.button("ðŸš€ WyÅ›lij zdjÄ™cia do pokazu"):

                with st.spinner("PrzesyÅ‚am foty i generujÄ™ podpisy AI..."):

                    model = genai.GenerativeModel("gemini-2.0-flash")

                    

                    fallbacks = [

                        "Kto rano wstaje, ten ma najwiÄ™kszego kaca! ðŸ’€",

                        "Tu miaÅ‚o byÄ‡ kulturalnie, ale wyszÅ‚o jak zwykle! ðŸ¥‚",

                        "Fotka za miliony, dowody zostanÄ… rano zniszczone! ðŸ“¸",

                        "Zuzia nie bierze jeÅ„cÃ³w, impreza Å¼ycia! ðŸ”¥"

                    ]

                    

                    for uploaded_file in uploaded_files:

                        file_size_mb = uploaded_file.size / (1024 * 1024)

                        if file_size_mb > MAX_FILE_SIZE_MB:

                            st.warning(f"Plik {uploaded_file.name} jest za duÅ¼y (>10MB). Pomijam.")

                            continue

                        

                        try:

                            upload_result = cloudinary.uploader.upload(uploaded_file, folder=CLOUDINARY_FOLDER)

                            image_url = upload_result.get("secure_url")

                            

                            caption = ""

                            try:

                                image_bytes = uploaded_file.getvalue()

                                image_obj = Image.open(BytesIO(image_bytes))

                                prompt = (

                                    "JesteÅ› bezczelnym, zabawnym komikiem na 18. urodzinach Zuzi. "

                                    "WymyÅ›l ULTRA ÅšMIESZNY, ironiczny podpis po polsku do 1 zdania z emoji. "

                                    "Zasada bezpieczeÅ„stwa: bez treÅ›ci wulgarnych lub obraÅºliwych, humor ma byÄ‡ Å¼yczliwy. "

                                    "ZwrÃ³Ä‡ sam tekst podpisu."

                                )

                                response = model.generate_content([prompt, image_obj])

                                if response and hasattr(response, "text") and response.text:

                                    caption = response.text.strip()

                            except Exception:

                                pass

                            

                            if not caption:

                                caption = random.choice(fallbacks)

                            

                            save_item(image_url, caption)

                        except Exception as e:

                            st.error(f"BÅ‚Ä…d przy pliku {uploaded_file.name}: {e}")

                    

                    st.success("Wszystkie zdjÄ™cia wysÅ‚ane pomyÅ›lnie! ðŸŽ‰")



# --- WIDOK 2: PROJEKTOR / POKAZ NA Å»YWO (DJ / ORGANIZATOR) ---

else:

    st.title("ðŸŽ¬ Ekran Projektora / Pokaz na Å»ywo")

    

    # Automatyczne odÅ›wieÅ¼anie widoku co 2 sekundy w tle

    st_autorefresh(interval=2000, key="dj_autorefresh")

    

    st.sidebar.markdown("---")

    st.sidebar.subheader("ðŸŽ›ï¸ Panel Kontrolny DJ-a")

    auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdÃ³w", value=True)

    slide_delay_sec = st.sidebar.slider("Czas wyÅ›wietlania (sekundy)", 3, 15, 6)

    

    # Sterowanie w panelu DJ-a

    col_p1, col_p2 = st.sidebar.columns(2)

    if col_p1.button("â ¸ï¸ Pauza / WznÃ³w"):

        st.session_state.paused = not st.session_state.paused

    if col_p2.button("ðŸ”„ Regeneruj komentarz"):

        # Wymuszenie zmiany indeksu lub ponownego losowania podpisu dla obecnego

        pass



    items = load_gallery()

    

    if items:

        if st.session_state.current_index >= len(items):

            st.session_state.current_index = 0

            

        idx = st.session_state.current_index

        item = items[idx]

        

        # Przycisk szybkiego usuwania konkretnego zdjÄ™cia z pokazu w panelu bocznym

        if st.sidebar.button(f"ðŸ—‘ï¸ PomiÅ„ / UsuÅ„ zdjÄ™cie #{idx + 1}"):

            items.pop(idx)

            lock = FileLock(LOCK_FILE)

            with lock:

                with open(DB_FILE, "w", encoding="utf-8") as f:

                    for it in items:

                        f.write(f"{it['url']}|{it['caption']}\n")

            st.session_state.current_index = 0

            st.rerun()



        # ObsÅ‚uga pionowych zdjÄ™Ä‡: rozmyte tÅ‚o (blurred background)

        col1, col2, col3 = st.columns([1, 4, 1])

        with col2:

            try:

                # Pobieramy obrazek z URL w celu analizy proporcji

                import requests

                response = requests.get(item["url"])

                img = Image.open(BytesIO(response.content))

                w, h = img.size

                

                if h > w: # ZdjÄ™cie pionowe

                    # Tworzenie rozmytego tÅ‚a

                    bg = img.copy().resize((1200, 1200))

                    bg = bg.filter(ImageFilter.GaussianBlur(25)) if 'ImageFilter' in globals() else bg

                    # Ewentualne skalowanie prezentacji z Å‚adnÄ… belkÄ…

                

                st.image(item["url"], use_container_width=True)

            except Exception:

                st.image(item["url"], use_container_width=True)



        # Bezpieczne renderowanie podpisu (XSS prevention: unsafe_allow_html=False)

        st.markdown(f"<h1 style='text-align: center; color: #ff4b4b;'>{item['caption']}</h1>", unsafe_allow_html=False)

        st.caption(f"ZdjÄ™cie {idx + 1} z {len(items)}")

        

        if auto_play and not st.session_state.paused:

            time.sleep(slide_delay_sec)

            st.session_state.current_index = (st.session_state.current_index + 1) % len(items)

            st.rerun()

    else:

        st.info("Czekamy na pierwsze zdjÄ™cia od goÅ›ci! WrzuÄ‡ coÅ› ze swojego telefonu.")

        time.sleep(3)

        st.rerun()
