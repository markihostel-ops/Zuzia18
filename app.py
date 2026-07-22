import base64
import requests
import streamlit as st
import anthropic

st.set_page_config(page_title="Opisywanie zdjęć", layout="centered")

st.title("📸 Generator opisów zdjęć")

# Pobranie klucza z Secrets
anthropic_api_key = st.secrets.get("ANTHROPIC_API_KEY")

if not anthropic_api_key:
    st.error("Brak klucza ANTHROPIC_API_KEY w Streamlit Secrets!")
    st.stop()

# Inicjalizacja klienta Anthropic
client = anthropic.Anthropic(api_key=anthropic_api_key)

# Przesyłanie zdjęcia
uploaded_file = st.file_uploader(
    "Wybierz zdjęcie...", type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="Przesłane zdjęcie", use_column_width=True)

    if st.button("Opisz zdjęcie"):
        with st.spinner("Claude analizuje zdjęcie..."):
            try:
                # Konwersja obrazu na base64
                bytes_data = uploaded_file.getvalue()
                base64_image = base64.b64encode(bytes_data).decode("utf-8")
                media_type = uploaded_file.type

                # Zapytanie do modelu Claude
                message = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": base64_image,
                                    },
                                },
                                {
                                    "type": "text",
                                    "text": "Stwórz ciekawy i zabawny komentarz do tego zdjęcia.",
                                },
                            ],
                        }
                    ],
                )

                opis = message.content[0].text
                st.success("Gotowe!")
                st.write(opis)

            except Exception as e:
                st.error(f"Wystąpił błąd podczas analizy: {e}")
else:
    st.info("Czekamy na pierwsze zdjęcia! Wrzuć coś z listy.")
