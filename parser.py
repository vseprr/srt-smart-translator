"""
parser.py - SRT Parsing Module

pysrt kullanarak SRT dosyasını okur ve her bloğu
timestamp bilgisiyle birlikte yapılandırılmış veri olarak döndürür.
Orijinal satır yapısı (line_count) korunur.
"""

from dataclasses import dataclass, field
from typing import List
import pysrt
from pysrt import SubRipTime


@dataclass
class SubtitleBlock:
    """Tek bir SRT bloğunu temsil eder."""
    index: int
    start_time: SubRipTime
    end_time: SubRipTime
    text: str
    line_count: int = 1  # Orijinal satır sayısı (1 veya 2 genellikle)
    char_count: int = field(init=False)
    
    def __post_init__(self):
        # Karakter sayısını hesapla (boşluklar dahil, newline hariç)
        self.char_count = len(self.text.replace('\n', ' '))
    
    def __repr__(self):
        return f"SubtitleBlock({self.index}: '{self.text[:30]}...' [{self.char_count} chars, {self.line_count} lines])"


def parse_srt(file_path: str) -> List[SubtitleBlock]:
    """
    SRT dosyasını parse eder ve SubtitleBlock listesi döndürür.
    Orijinal satır yapısını korur.
    UTF-8 BOM karakterini otomatik olarak temizler.
    
    Args:
        file_path: SRT dosyasının yolu
        
    Returns:
        List[SubtitleBlock]: Parse edilmiş alt yazı blokları
    """
    # utf-8-sig encoding BOM karakterini otomatik temizler
    subs = pysrt.open(file_path, encoding='utf-8-sig')
    
    blocks = []
    for i, sub in enumerate(subs, start=1):
        original_text = sub.text.strip()
        # Orijinal satır sayısını kaydet
        line_count = original_text.count('\n') + 1
        
        # İşleme için satır sonlarını boşluğa çevir (cümle birleştirme için)
        # Ama line_count'u sakladık, çıktıda kullanacağız
        text = original_text.replace('\n', ' ').strip()
        
        # Index'i normalize et (BOM veya bozuk karakterlerden temizle)
        # pysrt bazen string döndürebilir, integer'a çevir
        try:
            clean_index = int(str(sub.index).strip().lstrip('\ufeff'))
        except ValueError:
            clean_index = i  # Fallback: sıra numarası kullan
        
        block = SubtitleBlock(
            index=clean_index,
            start_time=sub.start,
            end_time=sub.end,
            text=text,
            line_count=line_count
        )
        blocks.append(block)
    
    return blocks


def format_text_with_lines(text: str, line_count: int) -> str:
    """
    Çevrilmiş metni orijinal satır sayısına göre biçimlendirir.
    
    Args:
        text: Çevrilmiş metin (tek satır)
        line_count: Orijinal satır sayısı
        
    Returns:
        Satır sonları eklenmiş metin
    """
    if line_count <= 1:
        return text
    
    text = text.strip()
    words = text.split()
    
    if len(words) < line_count:
        # Yeterli kelime yoksa olduğu gibi döndür
        return text
    
    # Kelimeleri eşit oranda satırlara böl
    words_per_line = len(words) // line_count
    remainder = len(words) % line_count
    
    lines = []
    start = 0
    
    for i in range(line_count):
        # Her satıra kaç kelime
        count = words_per_line + (1 if i < remainder else 0)
        end = start + count
        line = ' '.join(words[start:end])
        if line:
            lines.append(line)
        start = end
    
    return '\n'.join(lines)


def save_srt(blocks: List[SubtitleBlock], output_path: str, translated_texts: List[str]) -> None:
    """
    Çevrilmiş metinleri orijinal timestamp ve satır yapısıyla SRT dosyasına yazar.
    
    Args:
        blocks: Orijinal SubtitleBlock listesi
        output_path: Çıktı dosya yolu
        translated_texts: Çevrilmiş metin listesi (block sırasına göre)
    """
    subs = pysrt.SubRipFile()
    
    for block, translated_text in zip(blocks, translated_texts):
        # Orijinal satır yapısını uygula
        formatted_text = format_text_with_lines(translated_text, block.line_count)
        
        item = pysrt.SubRipItem(
            index=block.index,
            start=block.start_time,
            end=block.end_time,
            text=formatted_text
        )
        subs.append(item)
    
    subs.save(output_path, encoding='utf-8')


if __name__ == "__main__":
    # Test kodu
    import sys
    if len(sys.argv) > 1:
        blocks = parse_srt(sys.argv[1])
        print(f"Parsed {len(blocks)} blocks:")
        for block in blocks[:5]:
            print(f"  {block}")
    else:
        # format_text_with_lines test
        test_text = "Bu bir test cümlesidir ve birden fazla satıra bölünecek"
        print("Line formatting test:")
        print(f"  Original: '{test_text}'")
        print(f"  2 lines: '{format_text_with_lines(test_text, 2)}'")
        print(f"  3 lines: '{format_text_with_lines(test_text, 3)}'")
