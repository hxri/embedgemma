"""Rule-written variants of a sentence. The same rules build the proof bank and the expected form of a typed sentence."""
import re

FEM = {"man": "woman", "boy": "girl", "guy": "girl", "men": "women", "boys": "girls", "he": "she", "his": "her", "him": "her",
       "father": "mother", "husband": "wife", "son": "daughter", "brother": "sister", "king": "queen", "actor": "actress"}
MASC = {"woman": "man", "girl": "boy", "lady": "man", "women": "men", "girls": "boys", "she": "he", "her": "his",
        "mother": "father", "wife": "husband", "daughter": "son", "sister": "brother", "queen": "king", "actress": "actor"}


def _swap(table):
    pat = re.compile(r"\b(" + "|".join(table) + r")\b")
    return lambda c: pat.sub(lambda m: table[m.group(1)], c)


def _neg(c):
    return re.sub(r"\b(is|are|was|were) (\w+ing)\b", r"\1 not \2", c, count=1)


def _past(c):
    return re.sub(r"\b(is|are)( not)? (\w+ing)\b", lambda m: ("was" if m.group(1) == "is" else "were") + (m.group(2) or "") + " " + m.group(3), c, count=1)


def _ques(c):
    return re.sub(r"^(a|an|the|two|three|some|several|my|our|his|her|this|that) (.+?) (is|are|was|were) (.+?)[.!]?$",
                  lambda m: f"{m.group(3)} {m.group(1)} {m.group(2)} {m.group(4)}?", c, count=1)


RULES = {
    "gender man>woman": _swap(FEM),
    "gender woman>man": _swap(MASC),
    "negation": _neg,
    "past tense": _past,
    "question": _ques,
    "at night": lambda c: c + " at night",
    "in slow motion": lambda c: c + " in slow motion",
}
ORDER = list(RULES)

# which fitted direction (and sign) each operation uses
DIRECTION_OF = {"gender man>woman": ("gender man>woman", 1.0), "gender woman>man": ("gender man>woman", -1.0),
                "negation": ("negation", 1.0), "past tense": ("past tense", 1.0), "question": ("question", 1.0),
                "at night": ("at night", 1.0), "in slow motion": ("in slow motion", 1.0)}

LANGS = {"hi": ("Hindi", "hin_Deva"), "ta": ("Tamil", "tam_Taml"), "te": ("Telugu", "tel_Telu"), "bn": ("Bengali", "ben_Beng"),
         "kn": ("Kannada", "kan_Knda"), "ja": ("Japanese", "jpn_Jpan"), "zh": ("Chinese", "zho_Hans"), "ko": ("Korean", "kor_Hang"),
         "es": ("Spanish", "spa_Latn"), "fr": ("French", "fra_Latn"), "de": ("German", "deu_Latn"), "ru": ("Russian", "rus_Cyrl"),
         "ar": ("Arabic", "arb_Arab")}


def expected(text: str, ops: list[str]) -> tuple[str, list[str]]:
    """Apply the rule ops in canonical order. Returns the expected text and the ops whose rule did not apply."""
    out, missing = text, []
    for op in ORDER:
        if op in ops:
            v = RULES[op](out)
            if v == out:
                missing.append(op)
            out = v
    return out, missing
