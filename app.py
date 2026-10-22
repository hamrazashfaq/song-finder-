"""Song Finder - identify a song from a few lyrics (any language) using Google Gemini.

Run locally:  streamlit run app.py
"""

import json
import os
import re

import streamlit as st
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.8-flash"
# Tried automatically (in order) if the chosen model is out of quota or unavailable.
# Each model has its own quota, so this often rescues a "429" error.
FALLBACK_MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite"]

# Fields we ask Gemini to return, with the label shown in the UI.
FIELDS = [
    ("title", "Song title"),
    ("artist", "Singer / Artist"),
    ("writers", "Lyrics written by"),
    ("composers", "Composed by"),
    ("producers", "Produced by"),
    ("album", "Album / Movie / Playlist"),
    ("release_date", "Release date"),
    ("language", "Language"),
    ("genre", "Genre"),
    ("label", "Record label"),
    ("duration", "Duration"),
]


# ----------------------------------------------------------------------------
# Helper functions (kept separate from the UI so they are easy to test)
# ----------------------------------------------------------------------------
def build_prompt(lyrics: str, grounded: bool = False) -> str:
    """Create the instruction we send to Gemini."""
    if grounded:
        method = (
            "Use Google Search to find which song these lyrics come from, then "
            "report verified details."
        )
    else:
        method = (
            "Identify which song these lyrics come from using your own knowledge "
            "(you have no internet access)."
        )
    return f"""You are a music expert. A user typed a fragment of song lyrics.
The lyrics may be in ANY language or script (English, Urdu, Hindi, Pashto,
Arabic, Spanish, Korean, ...), may be transliterated (Roman Urdu etc.), and may
contain small mistakes.

{method} Do NOT guess: if you are not sure, say so in "confidence"
and use "Unknown" for missing fields. Never invent names or dates.
Do NOT quote the song's lyrics in your answer.

User lyrics:
\"\"\"{lyrics}\"\"\"

Reply with ONLY one JSON object (no markdown, no extra text) using exactly
these keys:
{{
  "found": true or false,
  "confidence": "high" | "medium" | "low",
  "title": string,
  "artist": string,
  "writers": string,
  "composers": string,
  "producers": string,
  "album": string (album, EP, movie or soundtrack the song belongs to),
  "release_date": string (YYYY-MM-DD if known, otherwise year),
  "language": string,
  "genre": string,
  "label": string,
  "duration": string,
  "summary": string (2-4 sentences: meaning/theme and background of the song),
  "trivia": string (one interesting fact, or "Unknown"),
  "other_matches": [string] (other possible songs if unsure, else [])
}}
If the song cannot be identified, set "found" to false and explain in "summary"."""


def extract_json(text: str) -> dict:
    """Pull a JSON object out of the model's reply (handles ```json fences)."""
    if not text:
        raise ValueError("Empty response from the model.")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("The model did not return JSON.")
    return json.loads(cleaned[start : end + 1])


def get_sources(response) -> list[tuple[str, str]]:
    """Collect (title, url) pairs from Google Search grounding metadata."""
    sources, seen = [], set()
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in (meta.grounding_chunks or []):
            web = getattr(chunk, "web", None)
            if web and web.uri and web.uri not in seen:
                seen.add(web.uri)
                sources.append((web.title or web.uri, web.uri))
    except (AttributeError, IndexError, TypeError):
        pass
    return sources


def is_retryable(error: Exception) -> bool:
    """True for quota / model-unavailable / temporary errors worth trying another way."""
    msg = str(error)
    return any(
        code in msg
        for code in ("429", "RESOURCE_EXHAUSTED", "404", "NOT_FOUND", "503", "UNAVAILABLE")
    )


def identify_song(api_key: str, model: str, lyrics: str, use_search: bool = False):
    """Ask Gemini to identify the song.

    Tries the chosen model first, then the fallback models. If ``use_search`` is on,
    each model is tried WITH Google Search first and then WITHOUT it (Google Search
    grounding is not available on the free tier and causes 429 errors there).

    Returns (data_dict, sources, info) where info = {"model": ..., "grounded": ...}.
    """
    client = genai.Client(api_key=api_key)
    models = [model] + [m for m in FALLBACK_MODELS if m != model]
    last_error = None

    for name in models:
        for grounded in ([True, False] if use_search else [False]):
            config = (
                types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
                if grounded
                else None
            )
            try:
                response = client.models.generate_content(
                    model=name,
                    contents=build_prompt(lyrics, grounded),
                    config=config,
                )
            except Exception as e:
                if is_retryable(e):
                    last_error = e
                    continue  # try next option
                raise  # e.g. invalid API key: no point retrying
            data = extract_json(response.text)
            return data, get_sources(response), {"model": name, "grounded": grounded}

    raise last_error if last_error else RuntimeError("No model could be used.")


def get_api_key() -> str:
    """Look for the key in Streamlit secrets, then environment variables."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:  # no secrets.toml present
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def friendly_error(error: Exception) -> str:
    """Turn a raw API error into a short, helpful message."""
    msg = str(error)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return (
            "Gemini quota exceeded for every model I tried. The free tier allows only a "
            "few requests per minute and per day. Wait a minute and try again, or check "
            "your usage at https://ai.dev/rate-limit (or enable billing for higher limits)."
        )
    if "404" in msg or "NOT_FOUND" in msg:
        return (
            "No Gemini model was available. Type a current model name in the sidebar "
            "(see https://ai.google.dev/gemini-api/docs/models)."
        )
    if "API_KEY_INVALID" in msg or "API key not valid" in msg or "401" in msg or "403" in msg:
        return "Your Gemini API key looks invalid or not allowed. Please check it."
    return f"Gemini request failed: {msg}"


# ----------------------------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------------------------
def render_result(data: dict, sources: list[tuple[str, str]], info: dict) -> None:
    if not data.get("found", True):
        st.warning("Could not identify this song.")
        st.write(data.get("summary", "Try adding more lyrics or fixing spelling."))
        return

    confidence = str(data.get("confidence", "unknown")).lower()
    badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
    st.subheader(f"🎵 {data.get('title', 'Unknown')}")
    st.caption(f"{badge} Confidence: {confidence}  ·  Model: {info['model']}")

    col1, col2 = st.columns(2)
    for i, (key, label) in enumerate(FIELDS):
        (col1 if i % 2 == 0 else col2).markdown(
            f"**{label}:** {data.get(key) or 'Unknown'}"
        )

    if data.get("summary"):
        st.markdown("#### About the song")
        st.write(data["summary"])
    if data.get("trivia") and data["trivia"] != "Unknown":
        st.info(f"💡 {data['trivia']}")

    others = data.get("other_matches") or []
    if others:
        st.markdown("#### Other possible matches")
        for item in others:
            st.write(f"- {item}")

    if sources:
        with st.expander("Sources (Google Search)"):
            for title, url in sources:
                st.markdown(f"- [{title}]({url})")
    elif not info["grounded"]:
        st.caption(
            "ℹ️ Answered from the model's own knowledge (no web search). "
            "Double-check names and dates for lesser-known songs."
        )

    st.download_button(
        "Download details (JSON)",
        data=json.dumps(data, indent=2, ensure_ascii=False),
        file_name="song_details.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="Song Finder", page_icon="🎵", layout="centered")
    st.title("🎵 Song Finder")
    st.write("Type a few lyrics from **any song in any language** and get its details.")

    with st.sidebar:
        st.header("Settings")
        api_key = get_api_key() or st.text_input(
            "Gemini API key", type="password", help="Get one at aistudio.google.com"
        )
        model = st.text_input("Gemini model", value=DEFAULT_MODEL)
        use_search = st.checkbox(
            "Use Google Search (paid plan only)",
            value=False,
            help="More accurate and shows sources, but Google does not include Search "
            "grounding in the free tier. If it fails, the app falls back automatically.",
        )
        st.caption("Your key is only used for this session.")

    lyrics = st.text_area(
        "Lyrics",
        height=140,
        placeholder="e.g. 'tum hi ho ab tum hi ho zindagi ab tum hi ho' or any other language...",
    )

    if st.button("Find song", type="primary"):
        lyrics = lyrics.strip()
        if not api_key:
            st.error("Please provide a Gemini API key (sidebar).")
        elif len(lyrics) < 8:
            st.error("Please enter a longer lyrics fragment (at least a short line).")
        else:
            with st.spinner("Searching..."):
                try:
                    data, sources, info = identify_song(
                        api_key, model.strip() or DEFAULT_MODEL, lyrics, use_search
                    )
                except json.JSONDecodeError:
                    st.error("Model returned malformed data. Please try again.")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # network, quota, invalid key...
                    st.error(friendly_error(e))
                else:
                    render_result(data, sources, info)

    st.divider()
    st.caption(
        "AI can make mistakes. Check the confidence level and verify important details."
    )


if __name__ == "__main__":
    main()
