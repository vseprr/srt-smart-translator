"""
language_data.py - SpaCy Model Mappings and Language Data

ISO 639-1 language codes, SpaCy model names, and preset configurations.
"""

# Preset models for Setup Wizard (popular languages with speed optimization)
PRESET_MODELS = [
    {
        "id": "en",
        "name": "English",
        "optimization": "Speed",
        "model_name": "en_core_web_sm",
        "install_cmd": "python -m spacy download en_core_web_sm"
    },
    {
        "id": "tr",
        "name": "Turkish",
        "optimization": "Accuracy",
        "model_name": "tr_core_news_lg",
        "install_cmd": "pip install https://huggingface.co/turkish-nlp-suite/tr_core_news_lg/resolve/main/tr_core_news_lg-any-py3-none-any.whl"
    },
    {
        "id": "es",
        "name": "Spanish",
        "optimization": "Speed",
        "model_name": "es_core_news_sm",
        "install_cmd": "python -m spacy download es_core_news_sm"
    },
    {
        "id": "fr",
        "name": "French",
        "optimization": "Speed",
        "model_name": "fr_core_news_sm",
        "install_cmd": "python -m spacy download fr_core_news_sm"
    },
    {
        "id": "de",
        "name": "German",
        "optimization": "Speed",
        "model_name": "de_core_news_sm",
        "install_cmd": "python -m spacy download de_core_news_sm"
    },
]

# ISO 639-1 to language name mapping (for Custom dropdown)
ALL_LANGUAGES = {
    "af": "Afrikaans",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "kn": "Kannada",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mr": "Marathi",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "sq": "Albanian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
}

# langdetect code to DeepL code mapping
LANGDETECT_TO_DEEPL = {
    "en": "EN",
    "tr": "TR",
    "de": "DE",
    "fr": "FR",
    "es": "ES",
    "it": "IT",
    "pt": "PT-PT",
    "nl": "NL",
    "pl": "PL",
    "ru": "RU",
    "ja": "JA",
    "zh-cn": "ZH",
    "zh-tw": "ZH",
    "ko": "KO",
    "ar": "AR",
    "bg": "BG",
    "cs": "CS",
    "da": "DA",
    "el": "EL",
    "et": "ET",
    "fi": "FI",
    "hu": "HU",
    "id": "ID",
    "lt": "LT",
    "lv": "LV",
    "no": "NB",
    "ro": "RO",
    "sk": "SK",
    "sl": "SL",
    "sv": "SV",
    "uk": "UK",
}

# ISO code to SpaCy blank language for sentencizer fallback
SPACY_BLANK_LANGUAGES = {
    "en": "en", "tr": "tr", "de": "de", "fr": "fr", "es": "es",
    "it": "it", "pt": "pt", "nl": "nl", "pl": "pl", "ru": "ru",
    "ja": "ja", "zh": "zh", "ko": "ko", "ar": "ar", "bg": "bg",
    "cs": "cs", "da": "da", "el": "el", "et": "et", "fi": "fi",
    "hu": "hu", "id": "id", "lt": "lt", "lv": "lv", "nb": "nb",
    "ro": "ro", "sk": "sk", "sl": "sl", "sv": "sv", "uk": "uk",
}


def get_language_name(iso_code: str) -> str:
    """Get human-readable language name from ISO code."""
    return ALL_LANGUAGES.get(iso_code, iso_code.upper())


def get_deepl_code(langdetect_code: str) -> str:
    """Convert langdetect code to DeepL API code."""
    return LANGDETECT_TO_DEEPL.get(langdetect_code, langdetect_code.upper())
