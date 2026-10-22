"""Song Finder - identify a song from a few lyrics (any language) using Gemini + Google Search.

Run locally:  streamlit run app.py
"""

import json
import os
import re

import streamlit as st
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-flash"

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
def build_prompt(lyrics: str) -> str:
    """Create the instruction we send to Gemini."""
    return f"""You are a music expert. A user typed a fragment of song lyrics.
The lyrics may be in ANY language or script (English, Urdu, Hindi, Pashto,
Arabic, Spanish, Korean, ...), may be transliterated (Roman Urdu etc.), and may
contain small mistakes.

Use Google Search to find which song these lyrics come from, then report
verified details. Do NOT guess: if you are not sure, say so in "confidence"
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


def identify_song(api_key: str, model: str, lyrics: str):
    """Call Gemini (with Google Search grounding). Returns (data_dict, sources)."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=build_prompt(lyrics),
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.1,  # low = fewer made-up facts
        ),
    )
    data = extract_json(response.text)
    return data, get_sources(response)


def get_api_key() -> str:
    """Look for the key in Streamlit secrets, then environment variables."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:  # no secrets.toml present
        pass
    return os.environ.get("GEMINI_API_KEY", "")


# ----------------------------------------------------------------------------
# Streamlit UI
# ----------------------------------------------------------------------------
def render_result(data: dict, sources: list[tuple[str, str]]) -> None:
    if not data.get("found", True):
        st.warning("Could not identify this song.")
        st.write(data.get("summary", "Try adding more lyrics or fixing spelling."))
        return

    confidence = str(data.get("confidence", "unknown")).lower()
    badge = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "⚪")
    st.subheader(f"🎵 {data.get('title', 'Unknown')}")
    st.caption(f"{badge} Confidence: {confidence}")

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
                    data, sources = identify_song(api_key, model.strip(), lyrics)
                except json.JSONDecodeError:
                    st.error("Model returned malformed data. Please try again.")
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # network, quota, invalid key...
                    st.error(f"Gemini request failed: {e}")
                else:
                    render_result(data, sources)

    st.divider()
    st.caption(
        "AI can make mistakes. Check the sources and confidence level before relying on the result."
    )


if __name__ == "__main__":
    main()
