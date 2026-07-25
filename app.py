"""
MEDISCAN AI - COMPLETE PACKAGE (single file)
================================================================

Yeh file 3 cheezon ka combo hai (README + requirements + app code)
taake sab kuch aik hi jagah khul jaye. Neeche pehle README aur
requirements comments ke andar hain, uske baad asli Streamlit code
shuru hota hai.

================================================================
README
================================================================
# MediScan AI 💊

Smart Prescription & Generic Medicine Assistant — built with Streamlit and
Google Gemini 1.5 Flash.

## What it does

Upload or photograph a doctor's prescription (handwritten or printed) and
MediScan AI will:

- Extract each medicine's **brand name** and **generic salt**
- Extract **dosage & schedule**, translated into both **English and Urdu**
- Suggest **affordable generic alternatives**
- Surface the **doctor's general advice** (rest, fluids, follow-up, etc.)
- **Read results aloud** in Urdu or English (🔊 buttons) — for patients who
  can't read, so they can just listen instead
- Gracefully flag prescriptions/handwriting it can't confidently read
- Show a permanent medical safety disclaimer

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   (Note: this uses the current **`google-genai`** package. The older
   `google-generativeai` package and all `gemini-1.5-*` models have been
   retired by Google, so this app uses the `gemini-flash-latest` alias,
   which always points to Google's current stable Flash model.)

2. Get a free Gemini API key from
   [Google AI Studio](https://aistudio.google.com/app/apikey).

3. Provide the key either by:
   - Pasting it into the sidebar field when the app is running, **or**
   - Setting an environment variable before launch:
     ```bash
     export GOOGLE_API_KEY="your-key-here"      # macOS/Linux
     setx GOOGLE_API_KEY "your-key-here"         # Windows
     ```

4. Run the app:
   ```bash
   streamlit run app.py
   ```

5. Open the local URL Streamlit prints (usually `http://localhost:8501`).

## Usage

1. Drag and drop a prescription image (PNG/JPG/JPEG) or take a photo with
   your camera.
2. Click **Analyze Prescription**.
3. Review the extracted medicine cards — brand name, generic salt, dosage in
   English and Urdu, duration, purpose, and affordable alternatives.
4. Download the structured result as JSON if needed.

## Voice / listen feature

Every medicine card has two buttons — **اردو میں سنیں** (Listen in Urdu) and
**Listen in English** — plus a "Listen to Everything" button at the top of
the results and one for the doctor's advice. These use the browser's
built-in text-to-speech (Web Speech API), so:

- No extra API key or internet call is needed for the voice itself.
- The Urdu voice quality depends on what voices are installed on the
  user's device/browser — most modern phones (Android/iOS) and Chrome have
  a usable Urdu voice built in. If none is available, the button shows a
  small "⚠️ Voice not available on this device" message instead of failing
  silently.

## Notes on reliability

- Handwriting recognition is inherently uncertain. When Gemini can't
  confidently read part of a prescription, the app shows an explicit
  "unclear" notice instead of guessing silently.
- This tool does **not** replace professional medical or pharmacist advice —
  see the in-app disclaimer.
- The JSON schema returned by the model is normalized in code, so missing
  fields never crash the UI.

## Project structure

```
mediscan/
├── app.py             # Main Streamlit application
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

================================================================
REQUIREMENTS (requirements.txt ki jagah - inko is tarah install karein)
================================================================
pip install streamlit google-genai Pillow

Ya agar requirements.txt file chahiye to yeh lines ek naye
requirements.txt file mein paste kar dein:

streamlit>=1.36.0
google-genai>=1.0.0
Pillow>=10.0.0
"""

"""
MediScan AI – Smart Prescription & Generic Medicine Assistant
================================================================
A Streamlit web app that reads a photo of a doctor's prescription
(handwritten or printed), extracts medicines, dosages, and generic
salts using Google Gemini 1.5 Flash vision, translates dosage
instructions to Urdu, and suggests affordable alternatives.

Run:
    pip install -r requirements.txt
    streamlit run app.py

Requires a Gemini API key, set as an environment variable
GOOGLE_API_KEY or entered in the sidebar at runtime.
"""

import os
import io
import json
import base64
import re
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None


# ----------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------
st.set_page_config(
    page_title="MediScan AI | Prescription Reader",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ----------------------------------------------------------------
# CUSTOM CSS
# ----------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Noto+Nastaliq+Urdu:wght@400;600&display=swap');

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background: linear-gradient(180deg, #f4f7fb 0%, #eef2f9 100%);
}

/* Hide default streamlit chrome */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Hero header */
.ms-hero {
    background: linear-gradient(135deg, #0f766e 0%, #0891b2 50%, #2563eb 100%);
    padding: 2.2rem 2rem;
    border-radius: 20px;
    color: white;
    margin-bottom: 1.6rem;
    box-shadow: 0 10px 30px -10px rgba(8, 145, 178, 0.45);
}
.ms-hero h1 {
    font-size: 2rem;
    font-weight: 800;
    margin: 0 0 0.3rem 0;
    letter-spacing: -0.02em;
}
.ms-hero p {
    font-size: 1rem;
    opacity: 0.92;
    margin: 0;
}

/* Section title */
.ms-section-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #0f172a;
    margin: 1.4rem 0 0.7rem 0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}

/* Medicine card */
.med-card {
    background: white;
    border-radius: 16px;
    padding: 1.3rem 1.4rem;
    margin-bottom: 1.1rem;
    border: 1px solid #e6ebf2;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    transition: box-shadow 0.2s ease;
}
.med-card:hover {
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.09);
}
.med-card .brand {
    font-size: 1.25rem;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0.1rem;
}
.med-card .salt {
    font-size: 0.92rem;
    color: #0891b2;
    font-weight: 600;
    margin-bottom: 0.7rem;
}
.med-card .purpose-badge {
    display: inline-block;
    background: #ecfeff;
    color: #0e7490;
    border: 1px solid #a5f3fc;
    padding: 0.2rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 0.8rem;
}
.info-row {
    display: flex;
    gap: 0.6rem;
    margin-bottom: 0.55rem;
    align-items: flex-start;
}
.info-label {
    min-width: 92px;
    font-size: 0.8rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding-top: 0.1rem;
}
.info-value {
    font-size: 0.95rem;
    color: #1e293b;
    flex: 1;
}
.urdu-box {
    background: #f8fafc;
    border-left: 3px solid #0891b2;
    border-radius: 8px;
    padding: 0.6rem 0.9rem;
    font-family: 'Noto Nastaliq Urdu', serif;
    font-size: 1.15rem;
    line-height: 2.1;
    color: #0f172a;
    direction: rtl;
    text-align: right;
}
.alt-pill {
    display: inline-block;
    background: #f0fdf4;
    color: #15803d;
    border: 1px solid #bbf7d0;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 600;
    margin: 0.15rem 0.3rem 0.15rem 0;
}

/* Advice card */
.advice-card {
    background: linear-gradient(135deg, #fef9c3 0%, #fef3c7 100%);
    border: 1px solid #fde68a;
    border-radius: 16px;
    padding: 1.1rem 1.3rem;
    margin: 1rem 0;
}
.advice-card .adv-title {
    font-weight: 700;
    color: #92400e;
    margin-bottom: 0.3rem;
    font-size: 0.95rem;
}
.advice-card .adv-text {
    color: #78350f;
    font-size: 0.95rem;
}

/* Disclaimer */
.disclaimer {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    color: #991b1b;
    font-size: 0.85rem;
    margin-top: 1.6rem;
    line-height: 1.5;
}
.disclaimer b { color: #7f1d1d; }

/* Fallback / unclear notice */
.unclear-box {
    background: #fff7ed;
    border: 1px dashed #fb923c;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    color: #9a3412;
    font-size: 0.9rem;
    margin-bottom: 1rem;
}

/* Metric row */
.metric-chip {
    background: white;
    border: 1px solid #e6ebf2;
    border-radius: 14px;
    padding: 0.9rem 1rem;
    text-align: center;
}
.metric-chip .num {
    font-size: 1.6rem;
    font-weight: 800;
    color: #0891b2;
}
.metric-chip .lbl {
    font-size: 0.78rem;
    color: #64748b;
    font-weight: 600;
    text-transform: uppercase;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ----------------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------------
MODEL_NAME = "gemini-flash-latest"

SYSTEM_PROMPT = """You are MediScan AI, a highly skilled clinical pharmacist and OCR
specialist trained to read doctors' handwritten and printed prescriptions from
Pakistani and South Asian clinical practice.

Your task: examine the prescription image and extract every medicine listed,
even if the handwriting is messy, abbreviated, or partially illegible. Use your
knowledge of common brand names, drug abbreviations (e.g., "Tab", "Cap", "Syp",
"BD", "TDS", "OD", "SOS", "PRN"), and typical dosage conventions to make the
best possible clinical interpretation.

Return STRICT JSON only — no markdown, no code fences, no commentary before or
after — matching exactly this schema:

{
  "prescription_readable": true or false,
  "confidence": "high" | "medium" | "low",
  "medicines": [
    {
      "brand_name": "string - brand name as best identified, or 'Unclear' if illegible",
      "generic_salt": "string - active ingredient/generic name",
      "dosage_english": "string - clear plain-English dosage & schedule",
      "dosage_urdu": "string - the SAME dosage instructions written naturally in Urdu script",
      "duration": "string - how many days/weeks, or 'Not specified'",
      "purpose": "string - short plain-language reason this medicine is typically prescribed",
      "affordable_alternatives": ["array of 2-4 cheaper generic-equivalent brand names available in Pakistan"]
    }
  ],
  "doctor_advice": "string - any general advice visible on the prescription (diet, rest, follow-up), or a sensible general note if none is visible",
  "unclear_notes": "string - if any part of the handwriting was ambiguous, briefly explain what was uncertain and how you interpreted it. Empty string if everything was clear."
}

Rules:
- If the image is not a prescription at all, or is completely unreadable, set
  "prescription_readable": false, leave "medicines" as an empty array, and
  explain briefly in "unclear_notes".
- Never invent a medicine that has no basis in the image; if a name is
  genuinely unreadable, use "Unclear" for brand_name but still make a best
  effort at generic_salt/dosage if partially visible.
- Always attempt an Urdu translation of dosage instructions, in natural,
  patient-friendly Urdu (not machine-transliterated).
- Keep "purpose" short (under 8 words).
- Output must be valid JSON — double-check brackets and quotes.
"""


# ----------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "raw_response" not in st.session_state:
    st.session_state.raw_response = None
if "history" not in st.session_state:
    st.session_state.history = []


# ----------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------
def get_api_key() -> str:
    """Resolve the Gemini API key from sidebar input or environment."""
    return st.session_state.get("api_key_input") or os.environ.get("GOOGLE_API_KEY", "")


def extract_json_from_text(text: str) -> dict:
    """Best-effort extraction of a JSON object from model output,
    even if the model wraps it in code fences or adds stray text."""
    if not text:
        raise ValueError("Empty response from model.")

    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: grab the largest {...} block
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"Model returned malformed JSON: {e}")

    raise ValueError("Could not locate a JSON object in the model's response.")


def call_gemini_vision(image: Image.Image, api_key: str) -> dict:
    """Send the prescription image to Gemini and parse the JSON reply.
    Uses the current google-genai SDK (the old google-generativeai package
    and gemini-1.5-* models have been retired by Google)."""
    if genai is None:
        raise RuntimeError(
            "The 'google-genai' package is not installed. "
            "Run: pip install google-genai"
        )
    if not api_key:
        raise RuntimeError("No Gemini API key provided. Enter one in the sidebar.")

    client = genai.Client(api_key=api_key)

    # Encode the image as raw bytes for the API
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    image_bytes = buf.getvalue()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            SYSTEM_PROMPT,
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        ],
        config=genai_types.GenerateContentConfig(
            temperature=0.15,
            top_p=0.9,
            max_output_tokens=2048,
            response_mime_type="application/json",
        ),
    )

    raw_text = response.text
    st.session_state.raw_response = raw_text
    return extract_json_from_text(raw_text)


def normalize_result(data: dict) -> dict:
    """Fill in any missing keys so downstream rendering never KeyErrors."""
    data.setdefault("prescription_readable", True)
    data.setdefault("confidence", "medium")
    data.setdefault("medicines", [])
    data.setdefault("doctor_advice", "")
    data.setdefault("unclear_notes", "")

    for med in data["medicines"]:
        med.setdefault("brand_name", "Unclear")
        med.setdefault("generic_salt", "Not identified")
        med.setdefault("dosage_english", "Not specified")
        med.setdefault("dosage_urdu", "واضح نہیں")
        med.setdefault("duration", "Not specified")
        med.setdefault("purpose", "Not specified")
        med.setdefault("affordable_alternatives", [])
    return data


def render_tts_button(text: str, lang: str, label: str, key: str, bg: str = "#0891b2"):
    """Render a small 'speak this text' button using the browser's built-in
    text-to-speech (Web Speech API). Works fully offline in the browser —
    no extra API calls or audio files needed. Useful for people who can't
    read the script (e.g. Urdu) — they can just listen instead."""
    safe_text = json.dumps(text or "")  # safely escape quotes/newlines for JS
    safe_lang = json.dumps(lang)
    html_code = f"""
    <div style="font-family: 'Inter', sans-serif;">
      <button id="btn_{key}" onclick="speak_{key}()" style="
          background:{bg}; color:white; border:none; border-radius:999px;
          padding:0.4rem 0.9rem; font-size:0.82rem; font-weight:600;
          cursor:pointer; display:inline-flex; align-items:center; gap:0.4rem;">
        🔊 {label}
      </button>
      <span id="status_{key}" style="font-size:0.78rem; color:#64748b; margin-left:0.5rem;"></span>
      <script>
        function speak_{key}() {{
          try {{
            const synth = window.speechSynthesis;
            synth.cancel(); // stop anything already playing
            const utter = new SpeechSynthesisUtterance({safe_text});
            utter.lang = {safe_lang};
            utter.rate = 0.92;
            const statusEl = document.getElementById("status_{key}");
            utter.onstart = () => {{ statusEl.innerText = "🔈 Playing..."; }};
            utter.onend = () => {{ statusEl.innerText = ""; }};
            utter.onerror = () => {{ statusEl.innerText = "⚠️ Voice not available on this device."; }};
            synth.speak(utter);
          }} catch (e) {{
            document.getElementById("status_{key}").innerText = "⚠️ Speech not supported here.";
          }}
        }}
      </script>
    </div>
    """
    components.html(html_code, height=44)


def render_medicine_card(med: dict, index: int):
    alt_pills = "".join(
        f'<span class="alt-pill">💊 {alt}</span>'
        for alt in med.get("affordable_alternatives", [])
    ) or '<span class="alt-pill" style="background:#f1f5f9;color:#64748b;border-color:#e2e8f0;">No alternatives listed</span>'

    brand = med.get("brand_name", "Unclear")
    is_unclear_brand = brand.strip().lower() in ("unclear", "not identified", "")

    st.markdown(
        f"""
        <div class="med-card">
            <div class="brand">{index}. {"⚠️ Unclear handwriting" if is_unclear_brand else brand}</div>
            <div class="salt">{med.get("generic_salt", "Not identified")}</div>
            <span class="purpose-badge">{med.get("purpose", "Not specified")}</span>
            <div class="info-row">
                <div class="info-label">Dosage</div>
                <div class="info-value">{med.get("dosage_english", "Not specified")}</div>
            </div>
            <div class="info-row">
                <div class="info-label">Duration</div>
                <div class="info-value">{med.get("duration", "Not specified")}</div>
            </div>
            <div class="info-row">
                <div class="info-label">اردو</div>
                <div class="info-value">
                    <div class="urdu-box">{med.get("dosage_urdu", "واضح نہیں")}</div>
                </div>
            </div>
            <div class="info-row">
                <div class="info-label">Alternatives</div>
                <div class="info-value">{alt_pills}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Voice / listen buttons (for patients who can't read) ---
    listen_col1, listen_col2 = st.columns(2)
    full_urdu_text = (
        f"{med.get('brand_name', '')}۔ خوراک: {med.get('dosage_urdu', 'واضح نہیں')}۔ "
        f"مدت: {med.get('duration', 'واضح نہیں')}۔"
    )
    full_english_text = (
        f"{med.get('brand_name', '')}. Dosage: {med.get('dosage_english', 'Not specified')}. "
        f"Duration: {med.get('duration', 'Not specified')}."
    )
    with listen_col1:
        render_tts_button(
            full_urdu_text, "ur-PK", "اردو میں سنیں", key=f"ur_{index}", bg="#0f766e"
        )
    with listen_col2:
        render_tts_button(
            full_english_text, "en-US", "Listen in English", key=f"en_{index}", bg="#2563eb"
        )


def render_disclaimer():
    st.markdown(
        """
        <div class="disclaimer">
        ⚠️ <b>Medical Disclaimer:</b> MediScan AI uses automated image recognition and
        may misread handwriting, dosages, or medicine names. This tool is for
        informational purposes only and is <b>not a substitute for professional
        medical advice, diagnosis, or treatment</b>. Always verify extracted
        information with your doctor or a licensed pharmacist before taking any
        medication, especially regarding dosage, duration, or substitutions.
        In case of emergency, contact your local emergency services immediately.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------
# SIDEBAR
# ----------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🔑 Configuration")
    st.text_input(
        "Google Gemini API Key",
        type="password",
        key="api_key_input",
        placeholder="Paste your API key here",
        help="Get a free key at https://aistudio.google.com/app/apikey. "
             "You can also set it as the GOOGLE_API_KEY environment variable.",
    )

    if os.environ.get("GOOGLE_API_KEY") and not st.session_state.get("api_key_input"):
        st.success("Using API key from environment.", icon="✅")

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        """
        **MediScan AI** reads photos of doctor prescriptions and extracts:
        - 💊 Medicine & generic salt names
        - ⏱️ Dosage & schedule (English + Urdu)
        - 💰 Affordable generic alternatives
        - 📋 Doctor's general advice

        Powered by **Google Gemini 1.5 Flash** vision.
        """
    )
    st.markdown("---")
    st.markdown("### 🧪 Session Stats")
    st.markdown(
        f"""
        <div class="metric-chip">
            <div class="num">{len(st.session_state.history)}</div>
            <div class="lbl">Scans this session</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------
# HERO HEADER
# ----------------------------------------------------------------
st.markdown(
    """
    <div class="ms-hero">
        <h1>💊 MediScan AI</h1>
        <p>Smart Prescription Reader &amp; Affordable Generic Medicine Assistant —
        upload a photo, get clear dosage instructions in English &amp; Urdu.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------
# UPLOAD SECTION
# ----------------------------------------------------------------
col_upload, col_preview = st.columns([1.3, 1])

with col_upload:
    st.markdown('<div class="ms-section-title">📤 Upload Prescription</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drag and drop a prescription photo, or click to browse",
        type=["png", "jpg", "jpeg"],
        help="Supported formats: PNG, JPG, JPEG. A clear, well-lit photo works best.",
    )
    camera_photo = st.camera_input("Or take a photo directly")

    image_source = camera_photo or uploaded_file

    analyze_clicked = st.button(
        "🔍 Analyze Prescription", type="primary", use_container_width=True,
        disabled=image_source is None,
    )

with col_preview:
    st.markdown('<div class="ms-section-title">🖼️ Preview</div>', unsafe_allow_html=True)
    if image_source is not None:
        img = Image.open(image_source)
        st.image(img, use_container_width=True, caption="Prescription preview")
    else:
        st.info("No image selected yet. Upload or capture a prescription to begin.")


# ----------------------------------------------------------------
# ANALYSIS
# ----------------------------------------------------------------
if analyze_clicked and image_source is not None:
    api_key = get_api_key()
    img = Image.open(image_source).convert("RGB")

    with st.spinner("🧠 Reading prescription with Gemini 1.5 Flash..."):
        try:
            data = call_gemini_vision(img, api_key)
            data = normalize_result(data)
            st.session_state.result = data
            st.session_state.history.append(
                {"time": datetime.now().strftime("%H:%M:%S"), "count": len(data.get("medicines", []))}
            )
        except RuntimeError as e:
            st.session_state.result = None
            st.error(f"⚙️ Configuration issue: {e}", icon="⚙️")
        except ValueError as e:
            st.session_state.result = None
            st.error(
                f"🤖 The AI response couldn't be parsed as valid JSON ({e}). "
                "This can happen with very unclear images — try a clearer, "
                "better-lit photo of the prescription.",
                icon="🤖",
            )
            with st.expander("Show raw model output (for debugging)"):
                st.code(st.session_state.raw_response or "No response captured.")
        except Exception as e:
            st.session_state.result = None
            st.error(f"❌ Unexpected error while contacting Gemini: {e}", icon="❌")


# ----------------------------------------------------------------
# RESULTS
# ----------------------------------------------------------------
result = st.session_state.result

if result is not None:
    st.markdown("---")

    if not result.get("prescription_readable", True) or not result.get("medicines"):
        st.markdown(
            f"""
            <div class="unclear-box">
            🧐 <b>We couldn't confidently read this prescription.</b><br/>
            {result.get("unclear_notes") or
             "The handwriting may be too unclear, the image too blurry, or this "
             "may not be a prescription. Please try again with a clearer, "
             "well-lit, close-up photo — or consult your pharmacist directly."}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        meds = result.get("medicines", [])
        confidence = result.get("confidence", "medium").capitalize()

        # Metrics row
        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(
                f'<div class="metric-chip"><div class="num">{len(meds)}</div>'
                f'<div class="lbl">Medicines Found</div></div>',
                unsafe_allow_html=True,
            )
        with m2:
            st.markdown(
                f'<div class="metric-chip"><div class="num">{confidence}</div>'
                f'<div class="lbl">Read Confidence</div></div>',
                unsafe_allow_html=True,
            )
        with m3:
            total_alts = sum(len(m.get("affordable_alternatives", [])) for m in meds)
            st.markdown(
                f'<div class="metric-chip"><div class="num">{total_alts}</div>'
                f'<div class="lbl">Alternatives Suggested</div></div>',
                unsafe_allow_html=True,
            )

        if result.get("unclear_notes"):
            st.markdown(
                f"""
                <div class="unclear-box">
                ✏️ <b>Note on legibility:</b> {result["unclear_notes"]}
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Full readout — one tap to hear everything, for patients who can't read
        full_summary_ur = " ".join(
            f"دوا نمبر {i}: {m.get('brand_name', '')}۔ خوراک: {m.get('dosage_urdu', 'واضح نہیں')}۔ مدت: {m.get('duration', 'واضح نہیں')}۔"
            for i, m in enumerate(meds, start=1)
        )
        st.markdown('<div class="ms-section-title">🔊 پوری تفصیل سنیں (Listen to Everything)</div>', unsafe_allow_html=True)
        render_tts_button(
            full_summary_ur, "ur-PK", "تمام ادویات اردو میں سنیں", key="all_ur", bg="#0f766e"
        )

        st.markdown('<div class="ms-section-title">💊 Extracted Medicines</div>', unsafe_allow_html=True)
        for i, med in enumerate(meds, start=1):
            render_medicine_card(med, i)

        if result.get("doctor_advice"):
            st.markdown(
                f"""
                <div class="advice-card">
                    <div class="adv-title">🩺 Doctor's General Advice</div>
                    <div class="adv-text">{result["doctor_advice"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_tts_button(
                result["doctor_advice"], "ur-PK", "ہدایات سنیں", key="advice_ur", bg="#92400e"
            )

        # Downloadable JSON
        st.download_button(
            "⬇️ Download Result as JSON",
            data=json.dumps(result, ensure_ascii=False, indent=2),
            file_name="mediscan_result.json",
            mime="application/json",
        )

    render_disclaimer()

else:
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align:center; padding: 2rem 1rem; color:#94a3b8;">
        Upload or capture a prescription photo above, then click
        <b>Analyze Prescription</b> to get started.
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_disclaimer()