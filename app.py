from flask import Flask, render_template, request, send_file
from moviepy import VideoFileClip
import whisper
import google.generativeai as genai
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os
import json

app = Flask(__name__)

# ======================
# FOLDERS
# ======================

UPLOAD_FOLDER = "uploads"
PDF_FOLDER = "pdfs"
HISTORY_FILE = "history.json"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

# Create history file if missing
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        json.dump([], f)

# ======================
# GEMINI API
# ======================


import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# ======================
# LOAD MODELS
# ======================

print("Loading Whisper Model...")
whisper_model = whisper.load_model("base")

print("Loading Gemini Model...")

gemini_model = None

try:
    models = genai.list_models()

    for model in models:
        if "generateContent" in model.supported_generation_methods:
            gemini_model = genai.GenerativeModel(model.name)
            print("Using Gemini Model:", model.name)
            break

except Exception as e:
    print("Gemini Error:", e)

# ======================
# TEMP STORAGE
# ======================

latest_data = {
    "transcript": "",
    "ai_notes": ""
}

# ======================
# HOME PAGE
# ======================

@app.route("/")
def home():
    return render_template("index.html")

# ======================
# UPLOAD VIDEO
# ======================

@app.route("/upload", methods=["POST"])
def upload():

    if "video" not in request.files:
        return "No video uploaded"

    file = request.files["video"]

    if file.filename == "":
        return "No file selected"

    video_path = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(video_path)

    # ------------------
    # Extract Audio
    # ------------------

    audio_path = os.path.join(
        UPLOAD_FOLDER,
        "audio.mp3"
    )

    video = VideoFileClip(video_path)

    video.audio.write_audiofile(
        audio_path,
        logger=None
    )

    # ------------------
    # Whisper Transcript
    # ------------------

    result = whisper_model.transcribe(audio_path)

    transcript = result["text"]

    # ------------------
    # Gemini Notes
    # ------------------

    if gemini_model:

        prompt = f"""
Create:

1. Short Summary

2. Key Points

3. 5 Quiz Questions

Transcript:

{transcript}
"""

        try:
            response = gemini_model.generate_content(prompt)
            ai_notes = response.text

        except Exception as e:
            ai_notes = f"Gemini Error: {e}"

    else:
        ai_notes = "Gemini model not available."

    # ------------------
    # Store Latest Data
    # ------------------

    latest_data["transcript"] = transcript
    latest_data["ai_notes"] = ai_notes

    # ------------------
    # Save History
    # ------------------

    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append({
        "filename": file.filename,
        "transcript": transcript,
        "ai_notes": ai_notes
    })

    with open(HISTORY_FILE, "w") as f:
        json.dump(
            history,
            f,
            indent=4
        )

    return render_template(
        "result.html",
        transcript=transcript,
        ai_notes=ai_notes
    )

# ======================
# PDF DOWNLOAD
# ======================

@app.route("/download-pdf")
def download_pdf():

    pdf_path = os.path.join(
        PDF_FOLDER,
        "notes.pdf"
    )

    doc = SimpleDocTemplate(pdf_path)

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "AutoNotes AI Report",
            styles["Title"]
        )
    )

    story.append(
        Spacer(1, 12)
    )

    story.append(
        Paragraph(
            "Transcript",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            latest_data["transcript"],
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 12)
    )

    story.append(
        Paragraph(
            "AI Notes",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            latest_data["ai_notes"],
            styles["BodyText"]
        )
    )

    doc.build(story)

    return send_file(
        pdf_path,
        as_attachment=True
    )

# ======================
# HISTORY PAGE
# ======================

@app.route("/history")
def history():

    try:
        with open(HISTORY_FILE, "r") as f:
            records = json.load(f)
    except:
        records = []

    return render_template(
        "history.html",
        records=records[::-1]
    )

# ======================
# RUN APP
# ======================

if __name__ == "__main__":
    app.run(debug=True)