from flask import Flask, render_template, request
import pdfplumber
import os
import re
import random
from collections import Counter

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Common words to ignore when picking "important" terms
STOPWORDS = set("""
a an the and or but if while is are was were be been being to of in on for
with as by at from that this these those it its it's their his her they he she
we you your i not no do does did can could should would may might will shall
than then so such which who whom what when where why how also into over under
about above below between among through during before after up down out off
each other some any all most more less few many much own same just only very
""".split())


def extract_text_from_pdf(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def split_sentences(text):
    # Clean up line breaks/extra spaces, then split into sentences
    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    # Keep sentences that are substantial but not walls of text
    sentences = [s.strip() for s in sentences if 40 <= len(s.strip()) <= 220]
    return sentences


def score_sentences(sentences):
    # Simple frequency-based scoring (extractive summarization)
    words = re.findall(r"[A-Za-z]{4,}", " ".join(sentences).lower())
    words = [w for w in words if w not in STOPWORDS]
    freq = Counter(words)

    scored = []
    for s in sentences:
        s_words = [w for w in re.findall(r"[A-Za-z]{4,}", s.lower()) if w not in STOPWORDS]
        score = sum(freq[w] for w in s_words)
        scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def pick_key_term(sentence):
    # Pick the most "important" word in a sentence to blank out / use as a flashcard term
    candidates = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", sentence)
    candidates = [c for c in candidates if c.lower() not in STOPWORDS]
    if not candidates:
        return None
    # Prefer capitalized (likely proper nouns / key terms), then longest word
    capitalized = [c for c in candidates if c[0].isupper() and not sentence.startswith(c)]
    pool = capitalized if capitalized else candidates
    return max(pool, key=len)


def make_fill_in_blank(sentence, term):
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    blanked = pattern.sub("_____", sentence, count=1)
    return blanked


def create_quiz_and_flashcards(text, num_items=8):
    sentences = split_sentences(text)

    if not sentences:
        # Fallback if the PDF had no extractable/usable text
        quiz = [{"question": "The PDF text couldn't be read well enough to generate questions.",
                 "answer": "Try a text-based PDF (not a scanned image)."}]
        flashcards = [{"front": "No content found",
                       "back": "Try uploading a PDF with selectable text."}]
        return quiz, flashcards

    scored = score_sentences(sentences)
    top_sentences = [s for _, s in scored[: num_items * 2]]  # extra buffer in case terms fail

    quiz = []
    flashcards = []
    used_terms = set()

    for sentence in top_sentences:
        if len(quiz) >= num_items:
            break
        term = pick_key_term(sentence)
        if not term or term.lower() in used_terms:
            continue
        used_terms.add(term.lower())

        question = make_fill_in_blank(sentence, term)
        quiz.append({"question": question, "answer": term})
        flashcards.append({"front": term, "back": sentence})

    if not quiz:
        # Last-resort fallback: use raw top sentences as short-answer prompts
        for sentence in top_sentences[:num_items]:
            quiz.append({"question": f"Explain in your own words: \"{sentence}\"", "answer": sentence})
            flashcards.append({"front": sentence[:40] + "...", "back": sentence})

    return quiz, flashcards


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files.get("pdf")
        if file and file.filename:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            text = extract_text_from_pdf(file_path)
            quiz, flashcards = create_quiz_and_flashcards(text)
            return render_template("result.html", quiz=quiz, flashcards=flashcards, filename=file.filename)
        return render_template("index.html", error="Please choose a PDF file first.")
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
