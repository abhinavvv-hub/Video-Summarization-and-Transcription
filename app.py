# app.py
from flask import Flask, render_template, request, jsonify
import os
from werkzeug.utils import secure_filename
from main import transcribe_video, summarize_transcript
import uuid
import traceback

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wav', 'mp3', 'm4a', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)
    
    print(f"File saved to: {filepath}")
    
    try:
        print("Starting transcription...")
        transcript = transcribe_video(filepath)
        if not transcript or not transcript.strip():
            return jsonify({'error': 'No speech detected in the video'}), 400
        
        print(f"Transcription complete. Length: {len(transcript)} chars")
        print("Starting summarization...")
        summary = summarize_transcript(transcript)
        if os.path.exists(filepath):
            os.remove(filepath)
            print("Uploaded file cleaned up")
        
        return jsonify({
            'transcript': transcript,
            'summary': summary
        })
        
    except Exception as e:
        print(f"Error during processing: {e}")
        traceback.print_exc()
        if os.path.exists(filepath):
            os.remove(filepath)
        
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
