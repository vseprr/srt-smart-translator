"""
app.py - Flask Web Server for Smart SRT Translator

Modern web interface for SRT file translation with on-demand SpaCy model management.
"""

import os
import json
import uuid
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_file, redirect, url_for
from werkzeug.utils import secure_filename

# Project modules
from parser import parse_srt, save_srt
from engine import merge_sentences_with_manager, smart_split
from translator import DeepLTranslator, TranslationConfig
from backend.model_manager import get_model_manager
from backend.language_data import PRESET_MODELS, ALL_LANGUAGES

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Create folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def cleanup_temp_files():
    """Clean up temp files from previous session."""
    count = 0
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                filepath = os.path.join(folder, filename)
                try:
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        count += 1
                except Exception:
                    pass
    if count > 0:
        print(f"  🧹 Cleaned up {count} old files.")


# Clean up on startup
cleanup_temp_files()

# Job tracking
translation_jobs = {}

# DeepL supported languages (target languages)
DEEPL_LANGUAGES = {
    "TR": "Türkçe",
    "EN-US": "English (US)",
    "EN-GB": "English (UK)",
    "DE": "Deutsch",
    "FR": "Français",
    "ES": "Español",
    "IT": "Italiano",
    "PT-PT": "Português",
    "PT-BR": "Português (Brasil)",
    "NL": "Nederlands",
    "PL": "Polski",
    "RU": "Русский",
    "JA": "日本語",
    "ZH": "中文",
    "KO": "한국어",
    "AR": "العربية",
    "BG": "Български",
    "CS": "Čeština",
    "DA": "Dansk",
    "EL": "Ελληνικά",
    "ET": "Eesti",
    "FI": "Suomi",
    "HU": "Magyar",
    "ID": "Indonesia",
    "LT": "Lietuvių",
    "LV": "Latviešu",
    "NB": "Norsk",
    "RO": "Română",
    "SK": "Slovenčina",
    "SL": "Slovenščina",
    "SV": "Svenska",
    "UK": "Українська",
}


# ============================================================
# SETUP CHECK MIDDLEWARE
# ============================================================

@app.before_request
def check_setup():
    """Redirect to setup if no models are configured."""
    manager = get_model_manager()
    
    # Allow these endpoints without setup
    allowed_endpoints = ['setup', 'static', 'api_install_model']
    
    if request.endpoint in allowed_endpoints:
        return None
    
    if not manager.is_setup_complete():
        return redirect(url_for('setup'))
    
    return None


# ============================================================
# SETUP WIZARD
# ============================================================

@app.route('/setup', methods=['GET'])
def setup():
    """First-run setup wizard."""
    manager = get_model_manager()
    
    # If already set up, redirect to home
    if manager.is_setup_complete():
        return redirect(url_for('index'))
    
    return render_template(
        'setup.html',
        preset_models=PRESET_MODELS,
        all_languages=ALL_LANGUAGES
    )


# ============================================================
# SETTINGS PAGE
# ============================================================

@app.route('/settings')
def settings():
    """Settings page for model management."""
    manager = get_model_manager()
    
    return render_template(
        'settings.html',
        models=manager.get_installed_models(),
        all_languages=ALL_LANGUAGES
    )


# ============================================================
# MAIN PAGE
# ============================================================

@app.route('/')
def index():
    """Main page."""
    manager = get_model_manager()
    active_model = manager.get_active_model_info()
    
    return render_template(
        'index.html',
        languages=DEEPL_LANGUAGES,
        active_model=active_model
    )


@app.route('/languages')
def get_languages():
    """Return supported languages."""
    return jsonify(DEEPL_LANGUAGES)


# ============================================================
# API: MODEL MANAGEMENT
# ============================================================

@app.route('/api/install-model', methods=['POST'])
def api_install_model():
    """Install a SpaCy model."""
    data = request.get_json()
    install_cmd = data.get('install_cmd', '')
    model_name = data.get('model_name', '')
    lang_code = data.get('lang_code', '')
    
    if not all([install_cmd, model_name, lang_code]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    manager = get_model_manager()
    result = manager.install_model(install_cmd, model_name, lang_code)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/remove-model', methods=['POST'])
def api_remove_model():
    """Remove a model from configuration and uninstall from pip."""
    data = request.get_json()
    model_name = data.get('model_name', '')
    
    if not model_name:
        return jsonify({'success': False, 'error': 'Model name required'}), 400
    
    manager = get_model_manager()
    result = manager.remove_model(model_name)
    
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@app.route('/api/detect-language', methods=['POST'])
def api_detect_language():
    """Detect language of text."""
    data = request.get_json()
    text = data.get('text', '')
    
    if not text:
        return jsonify({'lang': 'unknown', 'confidence': 0})
    
    manager = get_model_manager()
    lang, confidence = manager.detect_language(text)
    
    return jsonify({
        'lang': lang,
        'confidence': confidence,
        'language_name': ALL_LANGUAGES.get(lang, lang.upper())
    })


@app.route('/api/model-status')
def api_model_status():
    """Get current model status."""
    manager = get_model_manager()
    
    return jsonify({
        'setup_complete': manager.is_setup_complete(),
        'installed_models': manager.get_installed_models(),
        'active_model': manager.get_active_model_info()
    })


# ============================================================
# API: CONFIG (DeepL API Key)
# ============================================================

CONFIG_FILE = 'config.json'


def load_config():
    """Load config from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_config(config):
    """Save config to JSON file."""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def get_api_key():
    """Get API key from config."""
    config = load_config()
    return config.get('deepl_api_key', '')


@app.route('/api/config', methods=['GET'])
def get_config():
    """Check if API key is configured."""
    api_key = get_api_key()
    has_key = bool(api_key and len(api_key) > 10)
    masked_key = ''
    if has_key:
        masked_key = api_key[:8] + '...' + api_key[-4:] if len(api_key) > 12 else '***'
    return jsonify({
        'has_api_key': has_key,
        'masked_key': masked_key
    })


@app.route('/api/config', methods=['POST'])
def save_api_config():
    """Save API key to config."""
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    
    if not api_key:
        return jsonify({'error': 'API key cannot be empty'}), 400
    
    config = load_config()
    config['deepl_api_key'] = api_key
    save_config(config)
    
    return jsonify({'message': 'API key saved', 'success': True})


@app.route('/api/config', methods=['DELETE'])
def delete_api_config():
    """Remove API key from config."""
    config = load_config()
    if 'deepl_api_key' in config:
        del config['deepl_api_key']
        save_config(config)
    
    return jsonify({'message': 'API key removed', 'success': True})


# ============================================================
# FILE UPLOAD & TRANSLATION
# ============================================================

@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload SRT file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file found'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.srt'):
        return jsonify({'error': 'Only SRT files are accepted'}), 400
    
    # Save with unique ID
    job_id = str(uuid.uuid4())[:8]
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
    file.save(filepath)
    
    # Read file content for language detection
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        # Get first 2000 chars for detection
        sample_text = content[:2000]
    except:
        sample_text = ""
    
    # Detect language
    manager = get_model_manager()
    detected_lang, confidence = manager.detect_language(sample_text)
    
    # Check if we have a matching model
    installed_models = manager.get_installed_models()
    matching_model = next((m for m in installed_models if m.get('lang_code') == detected_lang), None)
    has_matching_model = matching_model is not None
    
    # Determine which model will be used
    if matching_model:
        active_model_name = matching_model.get('model_name', '')
        active_model_lang = matching_model.get('language_name', '')
    elif installed_models:
        # Fallback to first installed model
        active_model_name = installed_models[0].get('model_name', 'en_core_web_sm')
        active_model_lang = installed_models[0].get('language_name', 'English')
    else:
        active_model_name = 'sentencizer'
        active_model_lang = 'Rule-based'
    
    # Create job status
    translation_jobs[job_id] = {
        'status': 'uploaded',
        'progress': 0,
        'filename': filename,
        'filepath': filepath,
        'output_path': None,
        'error': None,
        'detected_lang': detected_lang,
        'lang_confidence': confidence,
        'has_matching_model': has_matching_model,
        'warning': None
    }
    
    # Set warning if mismatch
    if not has_matching_model and detected_lang != 'unknown':
        translation_jobs[job_id]['warning'] = f"Detected {ALL_LANGUAGES.get(detected_lang, detected_lang)}, but using {active_model_name}"
    
    return jsonify({
        'job_id': job_id,
        'filename': filename,
        'message': 'File uploaded',
        'detected_lang': detected_lang,
        'lang_name': ALL_LANGUAGES.get(detected_lang, detected_lang.upper()),
        'confidence': confidence,
        'has_matching_model': has_matching_model,
        'active_model_name': active_model_name,
        'active_model_lang': active_model_lang,
        'warning': translation_jobs[job_id].get('warning')
    })


@app.route('/translate', methods=['POST'])
def start_translation():
    """Start translation job."""
    data = request.get_json()
    job_id = data.get('job_id')
    target_lang = data.get('target_lang', 'TR')
    output_filename = data.get('output_filename', None)
    
    if job_id not in translation_jobs:
        return jsonify({'error': 'Invalid job ID'}), 400
    
    job = translation_jobs[job_id]
    
    if job['status'] not in ['uploaded', 'error']:
        return jsonify({'error': 'Job already processing or completed'}), 400
    
    # Output filename
    if not output_filename:
        base_name = Path(job['filename']).stem
        output_filename = f"{base_name}_{target_lang}.srt"
    
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}_{output_filename}")
    job['output_path'] = output_path
    job['output_filename'] = output_filename
    job['status'] = 'processing'
    job['progress'] = 0
    
    # Use detected language for SpaCy model selection
    source_lang = job.get('detected_lang', 'en')
    
    # Start translation in background
    thread = threading.Thread(
        target=run_translation,
        args=(job_id, job['filepath'], output_path, source_lang, target_lang)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Translation started', 'job_id': job_id})


def run_translation(job_id: str, input_path: str, output_path: str, source_lang: str, target_lang: str):
    """Run translation in background."""
    job = translation_jobs[job_id]
    
    try:
        # 1. Parse SRT (10%)
        job['progress'] = 5
        job['status'] = 'parsing'
        blocks = parse_srt(input_path)
        job['progress'] = 10
        
        # 2. Merge sentences (20%) - Use ModelManager
        job['status'] = 'merging'
        merged, model_info, is_fallback = merge_sentences_with_manager(blocks, source_lang)
        job['progress'] = 20
        
        # Store model info
        job['used_model'] = model_info
        job['model_fallback'] = is_fallback
        
        # 3. Translate (20% -> 80%)
        job['status'] = 'translating'
        translator = DeepLTranslator()
        config = TranslationConfig(target_lang=target_lang)
        
        sentences_to_translate = [m.full_text for m in merged]
        total_sentences = len(sentences_to_translate)
        translated_sentences = []
        
        # Batch translation
        batch_size = 10
        for i in range(0, total_sentences, batch_size):
            batch = sentences_to_translate[i:i+batch_size]
            translated_batch = translator.translate_batch(batch, config)
            translated_sentences.extend(translated_batch)
            
            progress = 20 + int((i + len(batch)) / total_sentences * 60)
            job['progress'] = min(progress, 80)
        
        # 4. Smart split (80% -> 90%)
        job['status'] = 'splitting'
        block_translations = {}
        
        for merged_sent, translated_text in zip(merged, translated_sentences):
            split_parts = smart_split(translated_text, merged_sent.char_ratios)
            for block, part in zip(merged_sent.source_blocks, split_parts):
                if block.index in block_translations:
                    block_translations[block.index] += " " + part
                else:
                    block_translations[block.index] = part
        
        translated_texts = []
        for block in blocks:
            translated_texts.append(block_translations.get(block.index, block.text))
        
        job['progress'] = 90
        
        # 5. Save (90% -> 100%)
        job['status'] = 'saving'
        save_srt(blocks, output_path, translated_texts)
        
        job['progress'] = 100
        job['status'] = 'completed'
        
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)


@app.route('/progress/<job_id>')
def get_progress(job_id):
    """Return job progress (SSE stream)."""
    def generate():
        while True:
            if job_id not in translation_jobs:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            
            job = translation_jobs[job_id]
            data = {
                'status': job['status'],
                'progress': job['progress'],
                'error': job.get('error'),
                'warning': job.get('warning'),
                'used_model': job.get('used_model'),
                'model_fallback': job.get('model_fallback', False)
            }
            yield f"data: {json.dumps(data)}\n\n"
            
            if job['status'] in ['completed', 'error']:
                break
            
            import time
            time.sleep(0.5)
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/status/<job_id>')
def get_status(job_id):
    """Return job status as JSON."""
    if job_id not in translation_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = translation_jobs[job_id]
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'filename': job.get('filename'),
        'output_filename': job.get('output_filename'),
        'error': job.get('error'),
        'warning': job.get('warning'),
        'detected_lang': job.get('detected_lang'),
        'used_model': job.get('used_model'),
        'model_fallback': job.get('model_fallback', False)
    })


@app.route('/download/<job_id>')
def download_file(job_id):
    """Download translated file."""
    if job_id not in translation_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = translation_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Translation not completed'}), 400
    
    return send_file(
        job['output_path'],
        as_attachment=True,
        download_name=job['output_filename']
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    import logging
    import socket
    
    # Silence Flask/Werkzeug logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    # Get LAN IP
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    local_ip = get_local_ip()
    manager = get_model_manager()
    
    print()
    print("  Smart SRT Translator")
    print("  " + "-" * 30)
    print(f"  Local:   http://localhost:5000")
    print(f"  Network: http://{local_ip}:5000")
    
    if not manager.is_setup_complete():
        print(f"  Status:  ⚠️  Setup required")
    else:
        models = manager.get_installed_models()
        print(f"  Models:  {len(models)} installed")
    
    print("  Exit:    Ctrl+C")
    print()
    
    app.run(debug=False, host='0.0.0.0', port=5000)
