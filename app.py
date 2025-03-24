import os
from flask import Flask, render_template, request, flash, session, redirect, url_for, send_file
from moviepy.editor import VideoFileClip
import sqlite3
import speech_recognition as sr
from werkzeug.utils import secure_filename


app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback_key')

UPLOAD_FOLDER = 'static/uploads'
AUDIO_FOLDER = 'static/audio'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

profanity_words = ["khota", "badmaash launda","karun", "kameena sala", "kameena", "sala", "kamina", "be haya", "kutti", "manhos"]

def check_profanity(text):
    words = text.split()
    detected_words = [word for word in words if word.lower() in profanity_words]
    return detected_words

def init_db():
    try:
        connection = sqlite3.connect('mydatabase.db')
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_name TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                profanity_words TEXT,
                profanity_status BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        connection.commit()
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        connection.close()

def save_to_database(video_name, extracted_text, profanity_words, profanity_status):
    try:
        connection = sqlite3.connect('mydatabase.db')
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO videos (video_name, extracted_text, profanity_words, profanity_status)
            VALUES (?, ?, ?, ?)
        """, (video_name, extracted_text, ', '.join(profanity_words), profanity_status))
        connection.commit()
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        connection.close()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    file = request.files.get('file')
    if not file or file.filename == '':
        flash("No file uploaded. Please upload a video file.", "error")
        return redirect(url_for('home'))

    allowed_extensions = {'mp4', 'mkv', 'avi', 'mov'}
    file_extension = file.filename.rsplit('.', 1)[-1].lower()
    if file_extension not in allowed_extensions:
        flash("Invalid file type. Please upload a valid video file.", "error")
        return redirect(url_for('home'))

    filename = secure_filename(file.filename)
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(video_path)
    
    session['video_path'] = video_path
    return redirect(url_for('process_video'))

@app.route('/process', methods=['GET'])
def process_video():
    video_path = session.get('video_path')
    if not video_path or not os.path.isfile(video_path):
        flash("No video to process.", "error")
        return redirect(url_for('home'))

    try:
        video = VideoFileClip(video_path)
        audio_path = os.path.join(AUDIO_FOLDER, 'extracted_audio.wav')
        video.audio.write_audiofile(audio_path)
        session['audio_path'] = audio_path
    except Exception as e:
        flash(f"Error processing the video: {str(e)}", "error")
        return redirect(url_for('home'))

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
            extracted_text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        extracted_text = "Audio could not be recognized."
    except sr.RequestError as e:
        extracted_text = f"Speech recognition error: {str(e)}"

    profanity_words_detected = check_profanity(extracted_text)
    profanity_status = bool(profanity_words_detected)

    session.update({
        'extracted_text': extracted_text,
        'profanity_status': profanity_status,
        'profanity_words': profanity_words_detected
    })

    save_to_database(os.path.basename(video_path), extracted_text, profanity_words_detected, profanity_status)

    return redirect(url_for('result'))

@app.route('/result')
def result():
    return render_template('result.html',
                           text=session.get('extracted_text', 'No text found'),
                           profanity_status=session.get('profanity_status', False),
                           detected_words=session.get('profanity_words', []),
                           audio_path=session.get('audio_path', None))


@app.route('/history')
def history():
    try:
        connection = sqlite3.connect('mydatabase.db')
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM videos ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        return render_template('history.html', rows=rows)
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('home'))
    finally:
        connection.close()

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
