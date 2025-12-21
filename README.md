# 🎬 Smart SRT Translator

<p align="center">
  <img src="logo_v-2.svg" alt="Smart SRT Translator Logo" width="200"/>
</p>

<p align="center">
  <strong>AI-powered subtitle translation with context preservation</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#demo">Demo</a> •
  <a href="#the-problem">The Problem</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#api-reference">API</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## ✨ Features

- 🧠 **Smart Sentence Merging** – Uses SpaCy NLP to detect sentence boundaries across subtitle blocks
- 🔄 **Context-Aware Translation** – Translates complete sentences, not fragmented blocks
- ⚡ **Proportional Splitting** – Redistributes translations back to original timestamps using character ratios
- 🌍 **29+ Languages** – Powered by DeepL API with support for major world languages
- 🎨 **Modern Web UI** – Dark glassmorphism theme with drag-and-drop file upload
- 📊 **Real-time Progress** – Server-Sent Events (SSE) for live translation status updates
- 🔐 **Secure** – API keys stored locally, never transmitted to third parties

---

## 🎥 Demo

<p align="center">
  <img src="assets/demo.gif" alt="Smart SRT Translator Demo" width="700"/>
</p>

---

## 🎯 The Problem

Traditional subtitle translators process each subtitle block independently:

```
1
00:00:01,000 --> 00:00:03,000
I went to the store

2
00:00:03,001 --> 00:00:05,000
and bought some milk.
```

**Block-by-block translation result:** ❌
```
1: "Mağazaya gittim"
2: "ve biraz süt satın aldı."  ← Wrong conjugation, lost context!
```

---

## 💡 How It Works

Smart SRT Translator uses a 4-step pipeline:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Parse   │───▶│  Merge   │───▶│Translate │───▶│  Split   │
│   SRT    │    │Sentences │    │  (API)   │    │  Back    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### 1. Parse
Reads the SRT file with UTF-8 BOM support using `pysrt`

### 2. Merge
SpaCy NLP detects sentence boundaries and merges split sentences:
```
"I went to the store" + "and bought some milk." 
→ "I went to the store and bought some milk."
```

### 3. Translate
Complete sentences are sent to DeepL API for contextual translation:
```
→ "Mağazaya gittim ve biraz süt aldım."
```

### 4. Smart Split
Translation is proportionally split back to original block structure using character ratios:
```
Original: [40% chars] [60% chars]
Translation: [40% of chars] [60% of chars]
```

**Result:** ✅
```
1: "Mağazaya gittim"
2: "ve biraz süt aldım."
```

---

## 🛠 Installation

### Prerequisites

#### 1. Python 3.8 or higher
If you don't have Python installed:
- **Windows:** Download from [python.org](https://www.python.org/downloads/) and run the installer
  - ⚠️ **Important:** Check "Add Python to PATH" during installation!
- **macOS:** `brew install python` or download from python.org
- **Linux:** `sudo apt install python3 python3-pip python3-venv`

Verify installation:
```bash
python --version  # Should show Python 3.8+
```

#### 2. DeepL API Key (Free)
1. Go to [DeepL API](https://www.deepl.com/pro-api)
2. Click "Sign up for free"
3. Register with your email
4. Go to your [Account Settings](https://www.deepl.com/account/summary)
5. Copy your **Authentication Key** (starts with something like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx`)

---

### Step-by-Step Setup

#### 1. Clone or Download the Repository
```bash
# Option A: Clone with Git
git clone https://github.com/vseprr/srt-smart-translator.git
cd srt-smart-translator

# Option B: Download ZIP from GitHub and extract it
```

#### 2. Create a Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Windows (Command Prompt):
venv\Scripts\activate

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On macOS/Linux:
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt when activated.

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Download SpaCy Language Model
```bash
python -m spacy download en_core_web_sm
```

This downloads the English NLP model (~12MB) for sentence detection.

#### 5. Run the Application
```bash
python app.py
```

You should see:
```
  Smart SRT Translator
  ------------------------------
  Adres: http://localhost:5000
  Cikis: Ctrl+C
```

#### 6. Open in Browser
Navigate to **http://localhost:5000** and enter your DeepL API key.

#### 7. Test with Sample File
A sample file `example.srt` is included for testing. It contains split sentences to demonstrate the smart merging feature.

---

### Windows Quick Launch
After initial setup, just double-click `UI-Start.bat` to launch the application.

---

## 🚀 Usage

1. **Start the server**
   ```bash
   python app.py
   ```

2. **Open your browser**
   Navigate to `http://localhost:5000`

3. **Enter your DeepL API key** (first time only)

4. **Upload an SRT file** via drag-and-drop

5. **Select target language** and click "Start Translation"

6. **Download** the translated file when complete

---

## 📁 Project Structure

```
srt-smart-translator/
├── app.py              # Flask server + API endpoints
├── parser.py           # SRT file reading/writing
├── engine.py           # Sentence merging algorithm
├── translator.py       # DeepL API integration
├── main.py             # CLI interface (optional)
├── config.json         # API key storage (gitignored)
├── templates/
│   └── index.html      # Web UI with inline SVG logo
├── static/
│   └── style.css       # Dark glassmorphism theme
├── uploads/            # Temporary upload storage
├── outputs/            # Translated files
└── memory/             # Project documentation
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Main page (HTML) |
| `GET` | `/languages` | List of supported languages |
| `GET` | `/api/config` | Check API key status |
| `POST` | `/api/config` | Save API key |
| `DELETE` | `/api/config` | Remove API key |
| `POST` | `/upload` | Upload SRT file |
| `POST` | `/translate` | Start translation job |
| `GET` | `/status/{job_id}` | Translation status (JSON) |
| `GET` | `/progress/{job_id}` | Real-time progress (SSE) |
| `GET` | `/download/{job_id}` | Download translated file |

---

## 🎨 Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask 3.x |
| NLP | SpaCy (en_core_web_sm) |
| Translation | DeepL Free API |
| SRT Parsing | pysrt |
| Frontend | Vanilla HTML/CSS/JS |
| Design | Dark Glassmorphism |

---

## ⚠️ Limitations

- **Single file only** – No batch translation yet
- **SRT format only** – VTT, ASS not supported
- **English source** – Assumes EN source language by default
- **Internet required** – DeepL API needs connectivity

---

## 🗺️ Roadmap

- [ ] Batch file translation
- [ ] VTT/ASS format support
- [ ] Automatic source language detection
- [ ] Formality selection (formal/informal)
- [ ] Translation history
- [ ] PWA support for offline UI

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

## 🙏 Acknowledgements

- [DeepL](https://www.deepl.com/) for their excellent translation API
- [SpaCy](https://spacy.io/) for natural language processing
- [pysrt](https://github.com/byroot/pysrt) for SRT file handling

---

<p align="center">
  Made with ❤️ for the subtitle community
</p>
