"""
main.py - Smart SRT Translator Entry Point

Tüm modülleri bir araya getirerek SRT çevirisini orchestrate eder.
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from parser import parse_srt, save_srt, SubtitleBlock
from engine import merge_sentences, smart_split, MergedSentence
from translator import DeepLTranslator, MockTranslator, TranslationConfig


def process_srt(input_path: str, 
                output_path: str,
                target_lang: str = "TR",
                use_mock: bool = False,
                api_key: Optional[str] = None,
                verbose: bool = False) -> None:
    """
    SRT dosyasını işler: parse -> merge -> translate -> split -> save
    
    Args:
        input_path: Girdi SRT dosyası
        output_path: Çıktı SRT dosyası
        target_lang: Hedef dil kodu
        use_mock: Mock translator kullan (test için)
        api_key: DeepL API key
        verbose: Detaylı çıktı
    """
    
    # 1. Parse SRT
    if verbose:
        print(f"[1/5] Parsing SRT file: {input_path}")
    
    blocks = parse_srt(input_path)
    if verbose:
        print(f"      Found {len(blocks)} subtitle blocks")
    
    # 2. Merge sentences with SpaCy
    if verbose:
        print("[2/5] Merging sentences with SpaCy NLP...")
    
    merged = merge_sentences(blocks)
    if verbose:
        print(f"      Detected {len(merged)} complete sentences")
        for i, m in enumerate(merged[:3]):
            print(f"      Example {i+1}: '{m.full_text[:60]}...' ({len(m.source_blocks)} blocks)")
    
    # 3. Translate sentences
    if verbose:
        print(f"[3/5] Translating to {target_lang}...")
    
    if use_mock:
        translator = MockTranslator()
    else:
        translator = DeepLTranslator(api_key)
    
    config = TranslationConfig(target_lang=target_lang)
    
    # Tüm cümleleri toplu çevir
    sentences_to_translate = [m.full_text for m in merged]
    translated_sentences = translator.translate_batch(sentences_to_translate, config)
    
    if verbose:
        print(f"      Translated {len(translated_sentences)} sentences")
    
    # 4. Smart split and rebuild
    if verbose:
        print("[4/5] Smart splitting translated text...")
    
    # Block index -> translated text mapping
    block_translations = {}
    
    for merged_sent, translated_text in zip(merged, translated_sentences):
        # Çevrilmiş cümleyi orijinal blok oranlarına göre böl
        split_parts = smart_split(translated_text, merged_sent.char_ratios)
        
        # Her parçayı ilgili bloğa eşle
        for block, part in zip(merged_sent.source_blocks, split_parts):
            # Aynı blok birden fazla cümlede olabilir, birleştir
            if block.index in block_translations:
                block_translations[block.index] += " " + part
            else:
                block_translations[block.index] = part
    
    # Sıralı çeviri listesi oluştur
    translated_texts = []
    for block in blocks:
        translated_texts.append(block_translations.get(block.index, block.text))
    
    if verbose:
        print(f"      Mapped translations to {len(translated_texts)} blocks")
    
    # 5. Save output
    if verbose:
        print(f"[5/5] Saving to: {output_path}")
    
    save_srt(blocks, output_path, translated_texts)
    
    print(f"\n✓ Translation complete!")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Blocks: {len(blocks)}")
    print(f"  Sentences: {len(merged)}")


def demo_mode(verbose: bool = True) -> None:
    """
    Demo modu - örnek veri ile SpaCy cümle birleştirmeyi gösterir.
    """
    print("=" * 60)
    print("Smart SRT Translator - Demo Mode")
    print("=" * 60)
    
    # Örnek parçalanmış alt yazılar
    sample_texts = [
        "This is the beginning of",
        "a sentence that was split.",
        "Here comes another one!",
        "And this sentence spans",
        "across multiple",
        "subtitle blocks.",
        "Final sentence here."
    ]
    
    print("\n[Demo] Sample fragmented subtitles:")
    for i, text in enumerate(sample_texts, 1):
        print(f"  Block {i}: '{text}'")
    
    # Mock SubtitleBlock oluştur
    from pysrt import SubRipTime
    
    mock_blocks = []
    for i, text in enumerate(sample_texts, 1):
        block = SubtitleBlock(
            index=i,
            start_time=SubRipTime(seconds=i*2),
            end_time=SubRipTime(seconds=i*2+2),
            text=text
        )
        mock_blocks.append(block)
    
    # SpaCy ile birleştir
    print("\n[Demo] Merging with SpaCy NLP...")
    merged = merge_sentences(mock_blocks)
    
    print(f"\n[Demo] Detected {len(merged)} complete sentences:")
    for i, m in enumerate(merged, 1):
        print(f"\n  Sentence {i}: '{m.full_text}'")
        print(f"    Source blocks: {[b.index for b in m.source_blocks]}")
        print(f"    Char ratios: {[f'{r:.2f}' for r in m.char_ratios]}")
    
    # Smart split demo
    print("\n[Demo] Smart Split Example:")
    demo_translated = "Bu örnek bir Türkçe çeviri cümlesidir"
    demo_ratios = [0.35, 0.65]
    split_result = smart_split(demo_translated, demo_ratios)
    print(f"  Original: '{demo_translated}'")
    print(f"  Ratios: {demo_ratios}")
    print(f"  Split result: {split_result}")
    
    print("\n" + "=" * 60)
    print("Demo complete! Use --help to see full usage options.")


def main():
    parser = argparse.ArgumentParser(
        description="Smart SRT Translator - Translate SRT files with context-aware sentence handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py input.srt output.srt
  python main.py input.srt output.srt --lang TR
  python main.py input.srt output.srt --mock --verbose
  python main.py --demo
        """
    )
    
    parser.add_argument("input", nargs="?", help="Input SRT file path")
    parser.add_argument("output", nargs="?", help="Output SRT file path")
    parser.add_argument("--lang", "-l", default="TR", help="Target language code (default: TR)")
    parser.add_argument("--mock", "-m", action="store_true", help="Use mock translator (for testing)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--demo", "-d", action="store_true", help="Run demo mode")
    parser.add_argument("--api-key", "-k", help="DeepL API key (or set DEEPL_API_KEY env var)")
    
    args = parser.parse_args()
    
    if args.demo:
        demo_mode(verbose=True)
        return
    
    if not args.input or not args.output:
        parser.print_help()
        print("\nError: Both input and output files are required (unless using --demo)")
        sys.exit(1)
    
    # Dosya kontrolü
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    try:
        process_srt(
            input_path=args.input,
            output_path=args.output,
            target_lang=args.lang,
            use_mock=args.mock,
            api_key=args.api_key,
            verbose=args.verbose
        )
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
