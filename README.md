# 🎵 Song Finder

Type a few lines of lyrics (any language or script, even Roman Urdu / Hindi) and get the
song's details: title, singer, writer, composer, producer, album/playlist, release date,
language, genre, label, a short summary and sources.

Built with **Streamlit** (UI) and **Google Gemini Flash** (AI). It works on the **free
Gemini tier**. If you have a paid plan, tick "Use Google Search" in the sidebar for more
accurate answers with source links.

## Features
- Works with lyrics in any language
- Tolerates spelling mistakes and transliteration
- Shows a confidence level (and source links when Google Search is used)
- Automatic fallback to other Gemini models if one is out of quota
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
- Default model is `gemini-3.8-flash`. If it is out of quota or unavailable, the app
  automatically tries `gemini-3.6-flash` and then `gemini-3.5-flash-lite`.
  Google retires older models over time; if you see a 404 NOT_FOUND error, type a
  current model name in the sidebar (https://ai.google.dev/gemini-api/docs/models).
- **429 RESOURCE_EXHAUSTED** means you used up your quota. The free tier has small
  per-minute and per-day limits. Wait a minute, or check usage at https://ai.dev/rate-limit.
- **Google Search grounding is not part of the free tier.** It is therefore OFF by default.
  Without it, the model answers from its own knowledge, so lesser-known songs may be
  wrong or "Unknown". Tick the sidebar option only if your plan supports it.
- AI can be wrong. Always check the confidence level and verify important details.
- The app does not display or store song lyrics.

## License
MIT
