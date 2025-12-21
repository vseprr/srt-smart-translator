"""
translator.py - DeepL Translation Module

DeepL Free API kullanarak cümleleri çevirir.
Direct HTTP API kullanımı (requests kütüphanesi).
API key config.json dosyasından okunur.
"""

import os
import json
import requests
from typing import List, Optional
from dataclasses import dataclass

# Config file path
CONFIG_FILE = 'config.json'


def load_api_key_from_config() -> str:
    """Load API key from config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('deepl_api_key', '')
        except:
            pass
    return ''


@dataclass
class TranslationConfig:
    """Çeviri konfigürasyonu."""
    source_lang: str = "EN"
    target_lang: str = "TR"
    formality: str = "default"  # "more", "less", "default", "prefer_more", "prefer_less"
    preserve_formatting: bool = True


class DeepLTranslator:
    """DeepL Free API ile çeviri yapan sınıf (Direct HTTP)."""
    
    # DeepL Free API endpoint - :fx ile biten keyler için zorunlu
    BASE_URL = "https://api-free.deepl.com/v2/translate"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: DeepL API anahtarı. Verilmezse config.json'dan okunur.
        """
        self.api_key = api_key or load_api_key_from_config()

        
    def _make_request(self, texts: List[str], config: TranslationConfig) -> dict:
        """
        DeepL API'ye HTTP POST isteği gönderir.
        
        Args:
            texts: Çevrilecek metin listesi
            config: Çeviri konfigürasyonu
            
        Returns:
            API response JSON
            
        Raises:
            ValueError: API key eksikse
            requests.HTTPError: API hatası
        """
        if not self.api_key:
            raise ValueError(
                "DeepL API key required. Please add your API key via the Web UI settings."
            )
        
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": texts,
            "target_lang": config.target_lang,
            "source_lang": config.source_lang,
            # IMPORTANT: split_sentences=0 → Cümle bölmeyi biz SpaCy ile yapıyoruz
            "split_sentences": "0",
            "preserve_formatting": config.preserve_formatting
        }
        
        # Formality sadece desteklenen dillerde kullanılabilir
        # TR desteklemiyor, bu yüzden sadece destekleyenler için ekle
        formality_supported = ["DE", "FR", "IT", "ES", "NL", "PL", "PT-PT", "PT-BR", "RU", "JA"]
        if config.target_lang in formality_supported and config.formality != "default":
            payload["formality"] = config.formality
        
        response = requests.post(self.BASE_URL, headers=headers, json=payload, timeout=30)
        
        # Hata kontrolü
        if response.status_code != 200:
            error_msg = f"DeepL API Error {response.status_code}: {response.text}"
            raise requests.HTTPError(error_msg, response=response)
        
        return response.json()
    
    def translate_text(self, text: str, config: Optional[TranslationConfig] = None) -> str:
        """
        Tek bir metni çevirir.
        
        Args:
            text: Çevrilecek metin
            config: Çeviri konfigürasyonu
            
        Returns:
            Çevrilmiş metin
        """
        if not text.strip():
            return ""
            
        config = config or TranslationConfig()
        result = self._make_request([text], config)
        
        if "translations" in result and len(result["translations"]) > 0:
            return result["translations"][0]["text"]
        
        return ""
    
    def translate_batch(self, texts: List[str], config: Optional[TranslationConfig] = None) -> List[str]:
        """
        Birden fazla metni toplu çevirir (tek API çağrısı - optimize).
        
        Args:
            texts: Çevrilecek metin listesi
            config: Çeviri konfigürasyonu
            
        Returns:
            Çevrilmiş metin listesi (aynı sırada)
        """
        if not texts:
            return []
            
        config = config or TranslationConfig()
        
        # Boş metinleri filtrele ve indekslerini tut
        non_empty_texts = []
        original_indices = []
        
        for i, text in enumerate(texts):
            if text.strip():
                non_empty_texts.append(text)
                original_indices.append(i)
        
        if not non_empty_texts:
            return [""] * len(texts)
        
        # Tek API çağrısı ile toplu çeviri
        result = self._make_request(non_empty_texts, config)
        
        # Sonuçları orijinal sıraya yerleştir
        translated = [""] * len(texts)
        
        if "translations" in result:
            for i, translation in enumerate(result["translations"]):
                original_idx = original_indices[i]
                translated[original_idx] = translation["text"]
        
        return translated
    
    def test_connection(self) -> dict:
        """
        API bağlantısını test eder.
        
        Returns:
            dict: Başarılıysa {"success": True, "message": "..."}, değilse {"success": False, "error": "..."}
        """
        try:
            result = self.translate_text("Hello", TranslationConfig(target_lang="TR"))
            return {
                "success": True,
                "message": f"API connection successful! 'Hello' → '{result}'",
                "translation": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


def translate_sentences(sentences: List[str], 
                       target_lang: str = "TR",
                       api_key: Optional[str] = None) -> List[str]:
    """
    Cümle listesini çevirir (convenience function).
    
    Args:
        sentences: Çevrilecek cümleler
        target_lang: Hedef dil kodu
        api_key: DeepL API key (opsiyonel)
        
    Returns:
        Çevrilmiş cümleler
    """
    translator = DeepLTranslator(api_key)
    config = TranslationConfig(target_lang=target_lang)
    return translator.translate_batch(sentences, config)


class MockTranslator:
    """
    Test amaçlı mock translator.
    API key olmadan test etmek için kullanılır.
    """
    
    def translate_text(self, text: str, config: Optional[TranslationConfig] = None) -> str:
        """Basit mock çeviri - sadece [TR] prefix ekler."""
        return f"[TR] {text}"
    
    def translate_batch(self, texts: List[str], config: Optional[TranslationConfig] = None) -> List[str]:
        """Toplu mock çeviri."""
        return [self.translate_text(t, config) for t in texts]


if __name__ == "__main__":
    # Test kodu
    print("=" * 60)
    print("DeepL API Connection Test")
    print("=" * 60)
    
    translator = DeepLTranslator()
    
    # API bağlantı testi
    print("\n[1] Testing API connection...")
    result = translator.test_connection()
    
    if result["success"]:
        print(f"    ✓ {result['message']}")
    else:
        print(f"    ✗ Connection failed: {result['error']}")
        exit(1)
    
    # Batch test
    print("\n[2] Testing batch translation...")
    test_sentences = [
        "This is a test sentence.",
        "Here is another one about artificial intelligence.",
        "The system works correctly."
    ]
    
    try:
        config = TranslationConfig(target_lang="TR")
        translations = translator.translate_batch(test_sentences, config)
        
        print("    Results:")
        for orig, trans in zip(test_sentences, translations):
            print(f"    EN: '{orig}'")
            print(f"    TR: '{trans}'")
            print()
        
        print("✓ All tests passed!")
        
    except Exception as e:
        print(f"    ✗ Batch test failed: {e}")
        exit(1)
