"""
engine.py - SpaCy Sentence Merging & Smart Splitting Engine

SpaCy NLP kullanarak parçalanmış alt yazı cümlelerini birleştirir
ve çeviri sonrası karakter oranına göre geri böler.
"""

from dataclasses import dataclass
from typing import List, Tuple
import spacy

from parser import SubtitleBlock


# SpaCy modelini yükle (lazy loading için modül seviyesinde None)
_nlp = None


def get_nlp():
    """SpaCy modelini lazy load eder."""
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


@dataclass
class MergedSentence:
    """Birleştirilmiş bir cümleyi ve kaynak bloklarını temsil eder."""
    full_text: str
    source_blocks: List[SubtitleBlock]
    char_ratios: List[float]
    
    def __repr__(self):
        return f"MergedSentence('{self.full_text[:50]}...' from {len(self.source_blocks)} blocks)"


def merge_sentences(blocks: List[SubtitleBlock]) -> List[MergedSentence]:
    """
    Alt yazı bloklarını SpaCy ile gerçek cümle sınırlarına göre birleştirir.
    
    Algoritma:
    1. Tüm blok metinlerini birleştir
    2. SpaCy ile cümle sınırlarını tespit et
    3. Her cümlenin hangi bloklardan geldiğini izle
    4. Karakter oranlarını hesapla
    
    Args:
        blocks: SubtitleBlock listesi
        
    Returns:
        List[MergedSentence]: Birleştirilmiş cümleler
    """
    if not blocks:
        return []
    
    nlp = get_nlp()
    
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
