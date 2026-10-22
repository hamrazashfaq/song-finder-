# song-finder-
# 🎵 Song Finder

Type a few lines of lyrics (any language or script, even Roman Urdu / Hindi) and get the
song's details: title, singer, writer, composer, producer, album/playlist, release date,
language, genre, label, a short summary and sources.

Built with **Streamlit** (UI) and **Google Gemini Flash** (AI) with **Google Search
grounding**, so answers come from live web results instead of only the model's memory.

## Features
- Works with lyrics in any language
- Tolerates spelling mistakes and transliteration
- Shows a confidence level and source links
- Download result as JSON

## Project structure
```
song-finder/
├── app.py
├── requirements.txt
└── README.md
```

## Run locally
1. Install Python 3.10+.
2. Get a free Gemini API key from https://aistudio.google.com/apikey
3. Install and run:
   ```bash
   python -m venv venv
   # Windows:  venv\Scripts\activate
   # Mac/Linux: source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Provide your key, either way:
   - Paste it in the app sidebar, **or**
   - Create `.streamlit/secrets.toml` containing:
     ```toml
     GEMINI_API_KEY = "your_key_here"
     ```
     (Never commit this file. Add `.streamlit/secrets.toml` to `.gitignore`.)
5. Start the app:
   ```bash
   streamlit run app.py
   ```

## Deploy on Streamlit Community Cloud
1. Push this project to a public GitHub repository.
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, choose your repo, branch `main`, main file `app.py`.
4. Open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "your_key_here"
   ```
5. Click **Deploy**. You get a public URL like `https://your-app.streamlit.app`.

## Notes
- Default model is `gemini-2.5-flash`. You can change the model name in the sidebar
  (for example if Google releases a newer Flash model).
- AI can be wrong. Always check the confidence level and the sources.
- The app does not display or store song lyrics.

## License
MIT
