"""
engine.py - SpaCy Sentence Merging & Smart Splitting Engine

SpaCy NLP kullanarak parçalanmış alt yazı cümlelerini birleştirir
ve çeviri sonrası karakter oranına göre geri böler.
"""

from dataclasses import dataclass
from typing import List, Tuple
import spacy

from parser import SubtitleBlock


# SpaCy modelleri için cache (lazy loading)
_nlp_models = {}

# Dil kodlarından SpaCy model adlarına eşleme
# DeepL dil kodları -> SpaCy model adları
LANGUAGE_MODEL_MAP = {
    # İngilizce - özel model
    "EN": "en_core_web_sm",
    "EN-US": "en_core_web_sm",
    "EN-GB": "en_core_web_sm",
    # Türkçe - özel model
    "TR": "tr_core_web_md",
}

# Çoklu dil modeli (fallback)
MULTI_LANG_MODEL = "xx_sent_ud_sm"


def get_nlp(source_lang: str = "EN"):
    """
    Kaynak dile göre uygun SpaCy modelini lazy load eder.
    
    Öncelik sırası:
    1. Dile özel model (en_core_web_sm, tr_core_web_md)
    2. Çoklu dil modeli (xx_sent_ud_sm)
    3. Rule-based Sentencizer (fallback)
    
    Args:
        source_lang: Kaynak dil kodu (DeepL formatında, örn: "EN", "TR", "DE")
        
    Returns:
        SpaCy nlp nesnesi
    """
    global _nlp_models
    
    # Önce cache'e bak
    if source_lang in _nlp_models:
        return _nlp_models[source_lang]
    
    nlp = None
    
    # 1. Dile özel model dene
    if source_lang in LANGUAGE_MODEL_MAP:
        model_name = LANGUAGE_MODEL_MAP[source_lang]
        try:
            nlp = spacy.load(model_name)
            print(f"  ✓ Loaded language-specific model: {model_name}")
        except OSError:
            print(f"  ⚠ Model not found: {model_name}, trying multi-language model...")
    
    # 2. Çoklu dil modeli dene
    if nlp is None:
        try:
            nlp = spacy.load(MULTI_LANG_MODEL)
            print(f"  ✓ Loaded multi-language model: {MULTI_LANG_MODEL}")
        except OSError:
            print(f"  ⚠ Multi-language model not found: {MULTI_LANG_MODEL}, using rule-based sentencizer...")
    
    # 3. Son çare: Rule-based Sentencizer
    if nlp is None:
        nlp = create_sentencizer_nlp(source_lang)
        print(f"  ✓ Using rule-based sentencizer for: {source_lang}")
    
    # Cache'e kaydet
    _nlp_models[source_lang] = nlp
    return nlp


def create_sentencizer_nlp(lang_code: str):
    """
    Belirtilen dil için rule-based Sentencizer oluşturur.
    Noktalama işaretlerine göre cümle sonu tespit eder.
    """
    # Desteklenen SpaCy dil sınıfları
    lang_classes = {
        "TR": "tr", "EN": "en", "EN-US": "en", "EN-GB": "en",
        "DE": "de", "FR": "fr", "ES": "es", "IT": "it",
        "PT-PT": "pt", "PT-BR": "pt", "NL": "nl", "PL": "pl",
        "RU": "ru", "JA": "ja", "ZH": "zh", "KO": "ko",
        "AR": "ar", "BG": "bg", "CS": "cs", "DA": "da",
        "EL": "el", "ET": "et", "FI": "fi", "HU": "hu",
        "ID": "id", "LT": "lt", "LV": "lv", "NB": "nb",
        "RO": "ro", "SK": "sk", "SL": "sl", "SV": "sv",
        "UK": "uk",
    }
    
    spacy_lang = lang_classes.get(lang_code, "xx")  # xx = multi-language
    
    try:
        nlp = spacy.blank(spacy_lang)
    except:
        nlp = spacy.blank("xx")  # Fallback to multi-language blank
    
    # Sentencizer ekle - noktalama kurallarıyla cümle bölme
    nlp.add_pipe("sentencizer")
    return nlp


@dataclass
class MergedSentence:
    """Birleştirilmiş bir cümleyi ve kaynak bloklarını temsil eder."""
    full_text: str
    source_blocks: List[SubtitleBlock]
    char_ratios: List[float]
    
    def __repr__(self):
        return f"MergedSentence('{self.full_text[:50]}...' from {len(self.source_blocks)} blocks)"


def merge_sentences_with_manager(blocks: List[SubtitleBlock], source_lang: str = "en") -> Tuple[List[MergedSentence], str, bool]:
    """
    Merge sentences using ModelManager for dynamic model selection.
    
    Args:
        blocks: SubtitleBlock list
        source_lang: ISO language code (e.g., 'en', 'tr', 'de')
        
    Returns:
        Tuple of (merged_sentences, model_name, is_fallback)
    """
    if not blocks:
        return [], "none", False
    
    # Use ModelManager for model selection
    try:
        from backend.model_manager import get_model_manager
        manager = get_model_manager()
        nlp, model_name, is_fallback = manager.get_model_for_language(source_lang)
    except ImportError:
        # Fallback to old behavior if backend not available
        nlp = get_nlp(source_lang)
        model_name = "legacy"
        is_fallback = True
    
    # Rest of the merge logic
    block_positions: List[Tuple[int, int, SubtitleBlock]] = []
    full_text_parts = []
    current_pos = 0
    
    for block in blocks:
        text = block.text
        start_pos = current_pos
        end_pos = current_pos + len(text)
        block_positions.append((start_pos, end_pos, block))
        full_text_parts.append(text)
        current_pos = end_pos + 1
    
    full_text = " ".join(full_text_parts)
    doc = nlp(full_text)
    
    merged_sentences = []
    
    for sent in doc.sents:
        sent_start = sent.start_char
        sent_end = sent.end_char
        sent_text = sent.text.strip()
        
        if not sent_text:
            continue
        
        overlapping_blocks = []
        char_contributions = []
        
        for block_start, block_end, block in block_positions:
            overlap_start = max(sent_start, block_start)
            overlap_end = min(sent_end, block_end)
            
            if overlap_start < overlap_end:
                overlapping_blocks.append(block)
                contribution = overlap_end - overlap_start
                char_contributions.append(contribution)
        
        if overlapping_blocks:
            total_chars = sum(char_contributions)
            if total_chars > 0:
                char_ratios = [c / total_chars for c in char_contributions]
            else:
                char_ratios = [1.0 / len(overlapping_blocks)] * len(overlapping_blocks)
            
            merged = MergedSentence(
                full_text=sent_text,
                source_blocks=overlapping_blocks,
                char_ratios=char_ratios
            )
            merged_sentences.append(merged)
    
    return merged_sentences, model_name, is_fallback


def merge_sentences(blocks: List[SubtitleBlock], source_lang: str = "EN") -> List[MergedSentence]:
    """
    Alt yazı bloklarını SpaCy ile gerçek cümle sınırlarına göre birleştirir.
    
    Algoritma:
    1. Tüm blok metinlerini birleştir
    2. SpaCy ile cümle sınırlarını tespit et
    3. Her cümlenin hangi bloklardan geldiğini izle
    4. Karakter oranlarını hesapla
    
    Args:
        blocks: SubtitleBlock listesi
        source_lang: Kaynak dil kodu (DeepL formatında, örn: "EN", "TR", "DE")
        
    Returns:
        List[MergedSentence]: Birleştirilmiş cümleler
    """
    if not blocks:
        return []
    
    nlp = get_nlp(source_lang)
    
    # Block sınırlarını ve pozisyonlarını izle
    # Her bloğun başlangıç ve bitiş karakter pozisyonunu tut
    block_positions: List[Tuple[int, int, SubtitleBlock]] = []
    full_text_parts = []
    current_pos = 0
    
    for block in blocks:
        text = block.text
        start_pos = current_pos
        end_pos = current_pos + len(text)
        block_positions.append((start_pos, end_pos, block))
        full_text_parts.append(text)
        current_pos = end_pos + 1  # +1 for space
    
    # Tüm metni birleştir
    full_text = " ".join(full_text_parts)
    
    # SpaCy ile işle
    doc = nlp(full_text)
    
    # Cümleleri ve kaynak bloklarını eşleştir
    merged_sentences = []
    
    for sent in doc.sents:
        sent_start = sent.start_char
        sent_end = sent.end_char
        sent_text = sent.text.strip()
        
        if not sent_text:
            continue
        
        # Bu cümleyle örtüşen blokları bul
        overlapping_blocks = []
        char_contributions = []
        
        for block_start, block_end, block in block_positions:
            # Örtüşme kontrolü
            overlap_start = max(sent_start, block_start)
            overlap_end = min(sent_end, block_end)
            
            if overlap_start < overlap_end:
                overlapping_blocks.append(block)
                # Bu bloğun cümleye katkı yaptığı karakter sayısı
                contribution = overlap_end - overlap_start
                char_contributions.append(contribution)
        
        if overlapping_blocks:
            # Karakter oranlarını hesapla
            total_chars = sum(char_contributions)
            if total_chars > 0:
                char_ratios = [c / total_chars for c in char_contributions]
            else:
                char_ratios = [1.0 / len(overlapping_blocks)] * len(overlapping_blocks)
            
            merged = MergedSentence(
                full_text=sent_text,
                source_blocks=overlapping_blocks,
                char_ratios=char_ratios
            )
            merged_sentences.append(merged)
    
    return merged_sentences


def smart_split(translated_text: str, ratios: List[float]) -> List[str]:
    """
    Çevrilmiş metni orijinal blok oranlarına göre böler.
    Kelimeleri ortadan bölmez, en yakın boşluğu bulur.
    
    Args:
        translated_text: Çevrilmiş tam cümle
        ratios: Her bloğun karakter oranı (toplamı 1.0)
        
    Returns:
        List[str]: Bölünmüş metin parçaları
    """
    if len(ratios) == 1:
        return [translated_text.strip()]
    
    text = translated_text.strip()
    total_len = len(text)
    parts = []
    current_pos = 0
    
    for i, ratio in enumerate(ratios[:-1]):  # Son parça için bölme yapma
        # Hedef pozisyonu hesapla
        target_len = int(total_len * ratio)
        target_pos = current_pos + target_len
        
        # target_pos'a en yakın boşluğu bul
        best_split = find_best_split_position(text, current_pos, target_pos, total_len)
        
        # Parçayı al
        part = text[current_pos:best_split].strip()
        if part:  # Boş parça ekleme
            parts.append(part)
        current_pos = best_split
    
    # Son parçayı ekle
    last_part = text[current_pos:].strip()
    if last_part:
        parts.append(last_part)
    
    # Parça sayısı ratio sayısından azsa, son parçaları birleştir veya ayır
    while len(parts) < len(ratios):
        # Yeterli parça yoksa, en uzun parçayı böl
        if parts:
            longest_idx = max(range(len(parts)), key=lambda i: len(parts[i]))
            longest = parts[longest_idx]
            mid = len(longest) // 2
            # En yakın boşluğu bul
            split_pos = find_nearest_space(longest, mid)
            if split_pos > 0 and split_pos < len(longest):
                part1 = longest[:split_pos].strip()
                part2 = longest[split_pos:].strip()
                parts[longest_idx:longest_idx+1] = [part1, part2]
            else:
                parts.append("")  # Boş parça ekle
        else:
            parts.append("")
    
    return parts[:len(ratios)]  # Fazla parça varsa kes


def find_best_split_position(text: str, start: int, target: int, end: int) -> int:
    """
    Hedef pozisyona en yakın boşluk karakterini bulur.
    """
    # Arama aralığı: target'ın %20'si kadar sağa ve sola bak
    search_range = max(10, int((end - start) * 0.2))
    
    best_pos = target
    min_distance = float('inf')
    
    # Hedefin etrafında boşluk ara
    for offset in range(-search_range, search_range + 1):
        pos = target + offset
        if start < pos < end and text[pos] == ' ':
            distance = abs(offset)
            if distance < min_distance:
                min_distance = distance
                best_pos = pos
    
    return best_pos


def find_nearest_space(text: str, pos: int) -> int:
    """Verilen pozisyona en yakın boşluğu bulur."""
    left = pos
    right = pos
    
    while left > 0 or right < len(text):
        if left > 0:
            left -= 1
            if text[left] == ' ':
                return left
        if right < len(text):
            if text[right] == ' ':
                return right
            right += 1
    
    return pos


if __name__ == "__main__":
    # Test kodu
    print("Testing engine.py...")
    
    # Test smart_split
    test_text = "Bu örnek bir Türkçe çeviri cümlesidir ve bölünecek"
    test_ratios = [0.4, 0.6]
    result = smart_split(test_text, test_ratios)
    print(f"Smart split test: {result}")
    
    # SpaCy test
    nlp = get_nlp()
    doc = nlp("This is a test. Here is another sentence! And a third one?")
    print("SpaCy sentences:")
    for sent in doc.sents:
        print(f"  - {sent.text}")
