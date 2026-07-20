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

# --- Konfiguracja strony ---
st.set_page_config(
    page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide"
)

# --- Panel boczny: Klucze i Konfiguracja ---
st.sidebar.title("Panel Sterowania & DJ")

s_gemini = st.secrets.get("GEMINI_API_KEY", "")
s_cloud = st.secrets.get("CLOUDINARY_CLOUD_NAME", "")
s_ckey = st.secrets.get("CLOUDINARY_API_KEY", "")
s_csec = st.secrets.get("CLOUDINARY_API_SECRET", "")

gemini_key = st.sidebar.text_input(
    "Gemini API Key", value=s_gemini, type="password"
)
cloud_name = st.sidebar.text_input("Cloudinary Cloud Name", value=s_cloud)
cloudinary_key = st.sidebar.text_input(
    "Cloudinary API Key", value=s_ckey, type="password"
)
cloudinary_secret = st.sidebar.text_input(
    "Cloudinary API Secret", value=s_csec, type="password"
)

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
    st.error(f"Błąd zapisu do bazy: {e}")


view_mode = st.sidebar.radio(
    "Wybierz widok:", ("Wgraj Zdjęcie (Goście)", "Pokaz na Projektorze (DJ)")
)

st.sidebar.markdown("---")

# --- Rozbudowany Reset (Plik tekstowy + zasoby Cloudinary) ---
if st.sidebar.button("🗑️ Wyczyść całą galerię"):
  try:
    # 1. Usuwanie pliku tekstowego z blokadą
    lock = FileLock(LOCK_FILE)
    with lock:
      if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    # 2. Usuwanie zasobów z folderu Cloudinary '18_zuzia'
    if cloud_name and cloudinary_key and cloudinary_secret:
      try:
        resources = cloudinary.api.resources(
            type="upload", prefix=CLOUDINARY_FOLDER, max_results=500
        )
        public_ids = [res["public_id"] for res in resources.get("resources", [])]
        if public_ids:
          cloudinary.api.delete_resources(public_ids)
      except Exception as cloud_err:
        st.sidebar.warning(
            f"Wyczyszczono lokalnie, ale błąd Cloudinary: {cloud_err}"
        )

    st.sidebar.success("Galeria i zasoby w chmurze zostały wyczyszczone!")
    st.session_state.current_index = 0
    st.rerun()
  except Exception as e:
    st.sidebar.error(f"Błąd podczas czyszczenia: {e}")

if "current_index" not in st.session_state:
  st.session_state.current_index = 0

# --- Widok 1: Wgrywanie zdjęć przez gości ---
if view_mode == "Wgraj Zdjęcie (Goście)":
  st.title("🎂 18. Urodziny Zuzi")
  st.header("Wrzuć fotki na żywo na ekran projektora!")

  if not cloud_name or not gemini_key:
    st.error("Uzupełnij klucze Cloudinary i Gemini w panelu po lewej!")
  else:
    uploaded_files = st.file_uploader(
        "Wybierz zdjęcia z telefonu:",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

    if uploaded_files:
      if st.button("🚀 Wyślij zdjęcia do pokazu"):
        with st.spinner("Przesyłam foty i generuję teksty..."):
          model = genai.GenerativeModel("gemini-2.0-flash")

          fallbacks = [
              "Kto rano wstaje, ten ma największego kaca! 💀",
              "Tu miało być kulturalnie, ale wyszło jak zwykle! 🥂",
              "Fotka za miliony, dowody zostaną rano zniszczone! 📸",
              "Zuzia nie bierze jeńców, impreza życia! 🔥",
          ]

          for uploaded_file in uploaded_files:
            # 4. Walidacja rozmiaru pliku (max 10 MB)
            file_size_mb = uploaded_file.size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
              st.warning(
                  f"Plik {uploaded_file.name} jest za duży ({file_size_mb:.1f} MB)."
                  f" Maksymalny rozmiar to {MAX_FILE_SIZE_MB} MB. Pomijam."
              )
              continue

            try:
              # 6. Wymuszenie zapisu do folderu Cloudinary '18_zuzia'
              upload_result = cloudinary.uploader.upload(
                  uploaded_file, folder=CLOUDINARY_FOLDER
              )
              image_url = upload_result.get("secure_url")

              caption = ""
              try:
                image_bytes = uploaded_file.getvalue()
                image_obj = Image.open(BytesIO(image_bytes))
                prompt = (
                    "Jesteś bezczelnym komikiem na 18. urodzinach Zuzi. Wymyśl"
                    " ULTRA ŚMIESZNY, ironiczny podpis po polsku do 1 zdania z"
                    " emoji. Zwróć sam tekst podpisu bez dodatkowych znaczników"
                    " HTML."
                )
                response = model.generate_content([prompt, image_obj])

                # 5. Bezpieczna obsługa odpowiedzi Gemini i zabezpieczenie przed brakiem .text
                if response and hasattr(response, "text") and response.text:
                  caption = response.text.strip()
              except Exception:
                pass

              # 5. Użycie fallbacku w razie braku odpowiedzi lub błędu AI
              if not caption:
                caption = random.choice(fallbacks)

              # 3. Zapis bezpieczny z FileLock (usunięto sztuczne time.sleep)
              save_item(image_url, caption)

            except Exception as e:
              st.error(f"Błąd przy pliku {uploaded_file.name}: {e}")

          st.success("Wszystkie poprawne zdjęcia wysłane! 🎉")

# --- Widok 2: Projektor / DJ ---
else:
  st.title("🎬 Ekran Projektora / Pokaz na Żywo")

  # 9. Automatyczne odświeżanie widoku DJ-a co 2 sekundy za pomocą streamlit-autorefresh
  st_autorefresh(interval=2000, key="dj_autorefresh")

  st.sidebar.markdown("---")
  st.sidebar.subheader("🎛️ Ustawienia Pokazu")
  auto_play = st.sidebar.checkbox("Automatyczna zmiana slajdów", value=True)
  slide_delay_sec = st.sidebar.slider(
      "Czas wyświetlania (sekundy)", 3, 15, 7
  )

  items = load_gallery()

  if items:
    # 10. Kontrola zakresu indeksu slajdów (zapobieganie wyjściu poza zakres)
    if st.session_state.current_index >= len(items):
      st.session_state.current_index = 0

    idx = st.session_state.current_index
    item = items[idx]

    st.image(item["url"], use_container_width=True)

    # 8. Bezpieczne renderowanie podpisu zapobiegające wstrzykiwaniu HTML/JS
    st.markdown(
        f"<h1 style='text-align: center; color: #ff4b4b;'>{item['caption']}</h1>",
        unsafe_allow_html=False,
    )
    st.caption(f"Zdjęcie {idx + 1} z {len(items)}")

    if auto_play:
      # Płynne przejście powiązane z czasem slajdu
      time.sleep(slide_delay_sec)
      st.session_state.current_index = (st.session_state.current_index + 1) % len(
          items
      )
      st.rerun()
  else:
    st.info("Czekamy na pierwsze zdjęcia! Wrzuć coś z telefonu.")
