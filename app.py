import streamlit as st
import google.generativeai as genai
import cloudinary
import cloudinary.uploader
import cloudinary.api
from PIL import Image, ImageFilter
import requests
from io import BytesIO
import time
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="18. Urodziny Zuzi - Foto Pokaz", layout="wide")

if "comments" not in st.session_state:
    st.session_state.comments = {}

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "hidden_urls" not in st.session_state:
    st.session_state.hidden_urls = set()

if "executor" not in st.session_state:
    st.session_state.executor = ThreadPoolExecutor(max_workers=3)

st.sidebar.title("⚙️ Panel Konfiguracji & DJ")

gemini_key = st.sidebar.text_input("Gemini API Key", type="password")
cloud_name = st.sidebar.text_input("Cloudinary Cloud Name")
cloud_api_key = st.sidebar.text_input("Cloudinary API Key")
cloud_api_secret = st.sidebar.text_input("Cloudinary API Secret", type="password")

mode = st.sidebar.radio("Wybierz widok:", ["🎉 Pokaz na Projektor (DJ)", "📸 Wgraj Zdjęcie (Goście)"])

if gemini_key:
    genai.configure(api_key=gemini_key)

if cloud_name and cloud_api_key and cloud_api_secret:
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=cloud_api_key,
        api_secret=cloud_api_secret,
        secure=True
    )

def _async_gemini_worker(img_url, key):
    try:
        genai.configure(api_key=key)
        response = requests.get(img_url, timeout=10)
        img = Image.open(BytesIO(response.content))
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            "Jesteś dowcipnym, genialnym konferansjerem na 18. urodzinach Zuzi. "
            "Przeanalizuj to zdjęcie i wygeneruj krótki (1-2 zdania), bardzo śmieszny, "
            "młodzieżowy, ale kulturalny i życzliwy komentarz do sytuacji ze zdjęcia."
        )
        res = model.generate_content([prompt, img])
        return res.text.strip()
    except Exception:
        return "Zuzia i goście tworzą historię tej nocy! 🥳"

def trigger_ai_comment(img_url):
    if not gemini_key:
        st.session_state.comments[img_url] = "Brak klucza Gemini API."
        return

    st.session_state.comments[img_url] = "GENERATING"
    
    def callback(future):
        try:
            st.session_state.comments[img_url] = future.result()
        except Exception:
            st.session_state.comments[img_url] = "Impreza rozkręca się do czerwoności! 🎉"

    future = st.session_state.executor.submit(_async_gemini_worker, img_url, gemini_key)
    future.add_done_callback(callback)

@st.cache_data(show_spinner=False)
def process_image_with_blur(img_url):
    try:
        response = requests.get(img_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        
        target_w, target_h = 1280, 720
        bg = img.resize((target_w, target_h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
        
        img.thumbnail((target_w, target_h))
        offset = ((target_w - img.width) // 2, (target_h - img.height) // 2)
        bg.paste(img, offset)
        return bg
    except Exception:
        return None

if mode == "📸 Wgraj Zdjęcie (Goście)":
    st.title("🎂 18. Urodziny Zuzi")
    st.subheader("Wrzuć fotkę na żywo na ekran projektora!")
    
    uploaded_file = st.file_uploader("Wybierz zdjęcie z telefonu:", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        if st.button("🚀 Wyślij zdjęcie do pokazu"):
            if not cloud_name:
                st.error("Uzupełnij dane Cloudinary w panelu bocznym!")
            else:
                with st.spinner("Wysyłanie zdjęcia..."):
                    cloudinary.uploader.upload(uploaded_file)
                    st.balloons()
                    st.success("Gotowe! Twoje zdjęcie za chwilę pojawi się na wielkim ekranie!")

elif mode == "🎉 Pokaz na Projektor (DJ)":
    st.sidebar.markdown("---")
    st.sidebar.subheader("🎛️ Kontrola Slajdów")
    
    is_paused = st.sidebar.checkbox("⏸️ Pauza pokazu", value=False)
    interval = st.sidebar.slider("Czas slajdu (sekundy):", 3, 15, 6)
    
    try:
        resources = cloudinary.api.resources(type="upload", max_results=100)["resources"]
        all_urls = [r["secure_url"] for r in resources]
        active_urls = [u for u in all_urls if u not in st.session_state.hidden_urls]
        
        if active_urls:
            if st.session_state.current_index >= len(active_urls):
                st.session_state.current_index = 0
                
            current_url = active_urls[st.session_state.current_index]
            
            col_dj1, col_dj2 = st.sidebar.columns(2)
            if col_dj1.button("🗑️ Usuń zdjęcie"):
                st.session_state.hidden_urls.add(current_url)
                st.rerun()
            if col_dj2.button("🔄 Odśwież AI"):
                trigger_ai_comment(current_url)

            if current_url not in st.session_state.comments:
                trigger_ai_comment(current_url)
            
            img_processed = process_image_with_blur(current_url)
            if img_processed:
                st.image(img_processed, use_container_width=True)
            
            comment_status = st.session_state.comments.get(current_url, "GENERATING")
            
            if comment_status == "GENERATING":
                display_text = "🤖 AI analizuje fotkę i układa ripostę..."
            else:
                display_text = comment_status

            st.markdown(
                f"""
                <div style="background-color: rgba(15, 15, 25, 0.85); color: #ffffff; 
                            padding: 18px; border-radius: 12px; text-align: center; 
                            font-size: 26px; font-weight: bold; margin-top: -20px; 
                            border: 2px solid #ff4b4b; box-shadow: 0px 4px 15px rgba(255, 75, 75, 0.3);">
                    💬 {display_text}
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            if not is_paused:
                time.sleep(interval)
                st.session_state.current_index = (st.session_state.current_index + 1) % len(active_urls)
                st.rerun()
        else:
            st.info("Czekam na zdjęcia od gości...")
            
    except Exception:
        st.warning("Uzupełnij klucze w panelu bocznym po lewej stronie.")
