"""Whisper language presets and multilingual prompting shared by the GUI and engine."""

from __future__ import annotations

from typing import Any


# Whisper's complete multilingual tokenizer catalog. Keep the codes aligned
# with Whisper so every language selectable here can be passed directly to the
# decoder, while the display names remain pleasant to search in the GUI.
ALL_AVAILABLE_LANGUAGES = {
    "en": "English (Global)",
    "zh": "Chinese / Mandarin (中文)",
    "de": "German (Deutsch)",
    "es": "Spanish / Castilian (Español)",
    "ru": "Russian (Русский)",
    "ko": "Korean (한국어)",
    "fr": "French (Français)",
    "ja": "Japanese (日本語)",
    "pt": "Portuguese (Português)",
    "tr": "Turkish (Türkçe)",
    "pl": "Polish (Polski)",
    "ca": "Catalan (Català)",
    "nl": "Dutch (Nederlands)",
    "ar": "Arabic (العربية)",
    "sv": "Swedish (Svenska)",
    "it": "Italian (Italiano)",
    "id": "Indonesian (Bahasa Indonesia)",
    "hi": "Hindi (हिन्दी)",
    "fi": "Finnish (Suomi)",
    "vi": "Vietnamese (Tiếng Việt)",
    "he": "Hebrew (עברית)",
    "uk": "Ukrainian (Українська)",
    "el": "Greek (Ελληνικά)",
    "ms": "Malay (Bahasa Melayu)",
    "cs": "Czech (Čeština)",
    "ro": "Romanian (Română)",
    "da": "Danish (Dansk)",
    "hu": "Hungarian (Magyar)",
    "ta": "Tamil (தமிழ்)",
    "no": "Norwegian (Norsk)",
    "th": "Thai (ไทย)",
    "ur": "Urdu (اردو)",
    "hr": "Croatian (Hrvatski)",
    "bg": "Bulgarian (Български)",
    "lt": "Lithuanian (Lietuvių)",
    "la": "Latin",
    "mi": "Maori (Te Reo Māori)",
    "ml": "Malayalam (മലയാളം)",
    "cy": "Welsh (Cymraeg)",
    "sk": "Slovak (Slovenčina)",
    "te": "Telugu (తెలుగు)",
    "fa": "Persian / Farsi (فارسی)",
    "lv": "Latvian (Latviešu)",
    "bn": "Bengali (বাংলা)",
    "sr": "Serbian (Српски)",
    "az": "Azerbaijani (Azərbaycan)",
    "sl": "Slovenian (Slovenščina)",
    "kn": "Kannada (ಕನ್ನಡ)",
    "et": "Estonian (Eesti)",
    "mk": "Macedonian (Македонски)",
    "br": "Breton (Brezhoneg)",
    "eu": "Basque (Euskara)",
    "is": "Icelandic (Íslenska)",
    "hy": "Armenian (Հայերեն)",
    "ne": "Nepali (नेपाली)",
    "mn": "Mongolian (Монгол)",
    "bs": "Bosnian (Bosanski)",
    "kk": "Kazakh (Қазақша)",
    "sq": "Albanian (Shqip)",
    "sw": "Swahili (Kiswahili)",
    "gl": "Galician (Galego)",
    "mr": "Marathi (मराठी)",
    "pa": "Punjabi (ਪੰਜਾਬੀ)",
    "si": "Sinhala (සිංහල)",
    "km": "Khmer (ខ្មែរ)",
    "sn": "Shona",
    "yo": "Yoruba",
    "so": "Somali (Soomaali)",
    "af": "Afrikaans",
    "oc": "Occitan",
    "ka": "Georgian (ქართული)",
    "be": "Belarusian (Беларуская)",
    "tg": "Tajik (Тоҷикӣ)",
    "sd": "Sindhi (سنڌي)",
    "gu": "Gujarati (ગુજરાતી)",
    "am": "Amharic (አማርኛ)",
    "yi": "Yiddish (ייִדיש)",
    "lo": "Lao (ລາວ)",
    "uz": "Uzbek (Oʻzbek)",
    "fo": "Faroese (Føroyskt)",
    "ht": "Haitian Creole (Kreyòl Ayisyen)",
    "ps": "Pashto (پښتو)",
    "tk": "Turkmen (Türkmençe)",
    "nn": "Norwegian Nynorsk (Nynorsk)",
    "mt": "Maltese (Malti)",
    "sa": "Sanskrit (संस्कृतम्)",
    "lb": "Luxembourgish (Lëtzebuergesch)",
    "my": "Myanmar / Burmese (မြန်မာ)",
    "bo": "Tibetan (བོད་སྐད་)",
    "tl": "Tagalog / Filipino (Taglish)",
    "mg": "Malagasy",
    "as": "Assamese (অসমীয়া)",
    "tt": "Tatar (Татарча)",
    "haw": "Hawaiian (ʻŌlelo Hawaiʻi)",
    "ln": "Lingala",
    "ha": "Hausa",
    "ba": "Bashkir (Башҡортса)",
    "jw": "Javanese (Basa Jawa)",
    "su": "Sundanese (Basa Sunda)",
    "yue": "Cantonese (廣東話)",
}

LANGUAGE_PRESETS = {
    "Auto-Detect (Best Available Detection)": [],
    "🇮🇩 Indonesian + 🇺🇸 English (Bilingual / Campuran)": ["id", "en"],
    "🇮🇩 Indonesian Only (Bahasa Indonesia)": ["id"],
    "🇺🇸 English Only": ["en"],
    "🇯🇵 Japanese + 🇺🇸 English (日本語 + EN)": ["ja", "en"],
    "🇯🇵 Japanese Only (日本語)": ["ja"],
    "🇰🇷 Korean + 🇺🇸 English (한국어 + EN)": ["ko", "en"],
    "🇰🇷 Korean Only (한국어)": ["ko"],
    "🇵🇭 Filipino / Tagalog + English (Taglish)": ["tl", "en"],
    "🇪🇸 Spanish + 🇺🇸 English": ["es", "en"],
    "🇨🇳 Chinese (中文)": ["zh"],
    "🇫🇷 French (Français)": ["fr"],
    "🇩🇪 German (Deutsch)": ["de"],
    "🌐 Custom Multi-Select...": "custom",
}

LANGUAGE_PROMPTS = {
    "id": "Bahasa Indonesia, percakapan sehari-hari, dialog.",
    "en": "English, everyday conversation, dialogue.",
    "ja": "日本語の日常会話、対話。",
    "ko": "한국어 일상 대화, 대화체.",
    "tl": "Filipino at Tagalog, pang-araw-araw na usapan, diyalogo.",
    "es": "Español, conversación diaria, diálogo.",
    "zh": "中文普通话对话，日常交流。",
    "fr": "Français, conversation quotidienne, dialogue.",
    "de": "Deutsch, tägliche Unterhaltung, Dialog.",
    "ru": "Русский язык, повседневная речь, диалог.",
    "pt": "Português, conversa diária, diálogo.",
    "ar": "محادثة باللغة العربية، حوار يومي.",
    "vi": "Tiếng Việt, hội thoại hàng ngày, trò chuyện.",
    "th": "ภาษาไทย, การสนทนาประจำวัน, บทสนทนา.",
    "it": "Italiano, conversazione quotidiana, dialogo.",
}


def normalize_language_codes(language: Any) -> list[str]:
    if isinstance(language, (list, tuple, set)):
        values = language
    elif isinstance(language, str):
        values = language.split(",")
    else:
        values = []
    result: list[str] = []
    for value in values:
        code = str(value).strip().lower()
        if code and code not in {"auto", "none"} and code not in result:
            result.append(code)
    return result


def build_multilingual_prompt(language: Any) -> tuple[str | None, str | None]:
    codes = normalize_language_codes(language)
    if not codes:
        return None, None
    if len(codes) == 1:
        code = codes[0]
        return code, LANGUAGE_PROMPTS.get(code, f"Spoken {code} conversation.")

    non_english = [code for code in codes if code != "en"]
    primary = non_english[0] if non_english else codes[0]
    names = [ALL_AVAILABLE_LANGUAGES.get(code, code.upper()) for code in codes]
    prompts = [LANGUAGE_PROMPTS[code] for code in codes if code in LANGUAGE_PROMPTS]
    return primary, f"Multilingual speech ({', '.join(names)}). {' '.join(prompts)}"
