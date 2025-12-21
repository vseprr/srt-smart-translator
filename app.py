"""
app.py - Flask Web Server for Smart SRT Translator

Modern web arayüzü ile SRT dosyası çevirisi.
"""

import os
import json
import uuid
import shutil
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, send_file
from werkzeug.utils import secure_filename

# Proje modülleri
from parser import parse_srt, save_srt
from engine import merge_sentences, smart_split
from translator import DeepLTranslator, TranslationConfig

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Klasörleri oluştur
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def cleanup_temp_files():
    """Önceki oturumdan kalan geçici dosyaları temizle."""
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
        print(f"  🧹 {count} eski dosya temizlendi.")


# Sunucu başlarken önceki oturumdan kalan dosyaları temizle
cleanup_temp_files()


# İşlem durumu takibi
translation_jobs = {}

# DeepL desteklenen diller
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


@app.route('/')
def index():
    """Ana sayfa."""
    return render_template('index.html', languages=DEEPL_LANGUAGES)


@app.route('/languages')
def get_languages():
    """Desteklenen dilleri döndür."""
    return jsonify(DEEPL_LANGUAGES)


# Config file for API key storage
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
    # Mask the key for display
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
        return jsonify({'error': 'API anahtarı boş olamaz'}), 400
    
    config = load_config()
    config['deepl_api_key'] = api_key
    save_config(config)
    
    return jsonify({'message': 'API anahtarı kaydedildi', 'success': True})


@app.route('/api/config', methods=['DELETE'])
def delete_api_config():
    """Remove API key from config."""
    config = load_config()
    if 'deepl_api_key' in config:
        del config['deepl_api_key']
        save_config(config)
    
    return jsonify({'message': 'API anahtarı kaldırıldı', 'success': True})


@app.route('/upload', methods=['POST'])
def upload_file():
    """SRT dosyası yükle."""
    if 'file' not in request.files:
        return jsonify({'error': 'Dosya bulunamadı'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Dosya seçilmedi'}), 400
    
    if not file.filename.lower().endswith('.srt'):
        return jsonify({'error': 'Sadece SRT dosyaları kabul edilir'}), 400
    
    # Benzersiz ID ile kaydet
    job_id = str(uuid.uuid4())[:8]
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
    file.save(filepath)
    
    # İşlem durumu oluştur
    translation_jobs[job_id] = {
        'status': 'uploaded',
        'progress': 0,
        'filename': filename,
        'filepath': filepath,
        'output_path': None,
        'error': None
    }
    
    return jsonify({
        'job_id': job_id,
        'filename': filename,
        'message': 'Dosya yüklendi'
    })


@app.route('/translate', methods=['POST'])
def start_translation():
    """Çeviri işlemini başlat."""
    data = request.get_json()
    job_id = data.get('job_id')
    target_lang = data.get('target_lang', 'TR')
    output_filename = data.get('output_filename', None)
    
    if job_id not in translation_jobs:
        return jsonify({'error': 'Geçersiz iş ID'}), 400
    
    job = translation_jobs[job_id]
    
    if job['status'] not in ['uploaded', 'error']:
        return jsonify({'error': 'Bu iş zaten işleniyor veya tamamlandı'}), 400
    
    # Çıktı dosya adı
    if not output_filename:
        base_name = Path(job['filename']).stem
        output_filename = f"{base_name}_{target_lang}.srt"
    
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}_{output_filename}")
    job['output_path'] = output_path
    job['output_filename'] = output_filename
    job['status'] = 'processing'
    job['progress'] = 0
    
    # Arka planda çeviri başlat
    thread = threading.Thread(
        target=run_translation,
        args=(job_id, job['filepath'], output_path, target_lang)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Çeviri başladı', 'job_id': job_id})


def run_translation(job_id: str, input_path: str, output_path: str, target_lang: str):
    """Çeviri işlemini arka planda çalıştır."""
    job = translation_jobs[job_id]
    
    try:
        # 1. Parse SRT (10%)
        job['progress'] = 5
        job['status'] = 'parsing'
        blocks = parse_srt(input_path)
        job['progress'] = 10
        
        # 2. Merge sentences (20%)
        job['status'] = 'merging'
        merged = merge_sentences(blocks)
        job['progress'] = 20
        
        # 3. Translate (20% -> 80%)
        job['status'] = 'translating'
        translator = DeepLTranslator()
        config = TranslationConfig(target_lang=target_lang)
        
        sentences_to_translate = [m.full_text for m in merged]
        total_sentences = len(sentences_to_translate)
        translated_sentences = []
        
        # Batch olarak çevir ama progress güncelle
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
    """İşlem durumunu döndür (SSE stream)."""
    def generate():
        while True:
            if job_id not in translation_jobs:
                yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                break
            
            job = translation_jobs[job_id]
            data = {
                'status': job['status'],
                'progress': job['progress'],
                'error': job.get('error')
            }
            yield f"data: {json.dumps(data)}\n\n"
            
            if job['status'] in ['completed', 'error']:
                break
            
            import time
            time.sleep(0.5)
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/status/<job_id>')
def get_status(job_id):
    """İşlem durumunu JSON olarak döndür."""
    if job_id not in translation_jobs:
        return jsonify({'error': 'İş bulunamadı'}), 404
    
    job = translation_jobs[job_id]
    return jsonify({
        'status': job['status'],
        'progress': job['progress'],
        'filename': job.get('filename'),
        'output_filename': job.get('output_filename'),
        'error': job.get('error')
    })


@app.route('/download/<job_id>')
def download_file(job_id):
    """Çevrilmiş dosyayı indir."""
    if job_id not in translation_jobs:
        return jsonify({'error': 'İş bulunamadı'}), 404
    
    job = translation_jobs[job_id]
    
    if job['status'] != 'completed':
        return jsonify({'error': 'Çeviri henüz tamamlanmadı'}), 400
    
    return send_file(
        job['output_path'],
        as_attachment=True,
        download_name=job['output_filename']
    )


if __name__ == '__main__':
    import logging
    # Flask ve Werkzeug loglarını sustur
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print()
    print("  Smart SRT Translator")
    print("  " + "-" * 30)
    print("  Adres: http://localhost:5000")
    print("  Cikis: Ctrl+C")
    print()
    
    app.run(debug=False, host='127.0.0.1', port=5000)

