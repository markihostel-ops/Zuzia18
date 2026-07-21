generation_config = {
                    "temperature": 1.0,  # Zwiększona losowość dla unikalnych podpisów
                    "top_p": 0.95,
                    "top_k": 40,
                }
                safety_settings = [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]

                model = genai.GenerativeModel(
                    "gemini-2.0-flash",
                    generation_config=generation_config,
                    safety_settings=safety_settings
                )

                total_files = len(uploaded_files)
                for i, uploaded_file in enumerate(uploaded_files):
                    status_text.text(f"Analizuję zdjęcie {i+1} z {total_files}...")

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

                        if not image_url:
                            continue

                        caption = f"Zuzia 18! 🔥"
                        success_ai = False

                        # Losowy akcent wymuszający brak powtarzalności w paczce
                        random_angles = [
                            "Skup się na ubraniach i stylu.",
                            "Skup się na minach i ekspresji twarzy.",
                            "Skup się na tym, co trzymają w rękach lub w jakiej są sytuacji.",
                            "Zażartuj z poziomu energii na tym zdjęciu."
                        ]
                        chosen_angle = random.choice(random_angles)

                        for attempt in range(3):
                            try:
                                prompt = (
                                    f"Jesteś złośliwym gościem na 18. urodzinach Zuzi. {chosen_angle} "
                                    "Opisz bezczelnie i uszczypliwie to konkretne zdjęcie. "
                                    "Napisz zabawny komentarz w maksymalnie 2 krótkich zdaniach, dodaj pasujące emoji. "
                                    "Zwróć uwagę na unikalne szczegóły tego kadru i unikaj oklepanych fraz. "
                                    "Zwróć wyłącznie sam tekst, bez żadnych cudzysłowów."
                                )

                                response = model.generate_content([prompt, img])
                                if response and hasattr(response, "text") and response.text:
                                    text_resp = response.text.strip().replace('"', '').replace("'", "")
                                    if len(text_resp) > 3:
                                        caption = text_resp
                                        success_ai = True
                                        break
                            except Exception as ex:
                                time.sleep(0.5)
