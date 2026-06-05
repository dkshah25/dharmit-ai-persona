import re

# Comprehensive list of adversarial patterns (case-insensitive regex)
ADVERSARIAL_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions",
    r"system\s+prompt",
    r"reveal\s+instructions",
    r"hidden\s+prompt",
    r"jailbreak",
    r"you\s+are\s+now\s+a",
    r"you\s+are\s+no\s+longer",
    r"forget\s+your\s+persona",
    r"forget\s+(?:all\s+)?(?:previous\s+)?instructions",
    r"bypass\s+restrictions",
    r"dan\s+mode",
    r"do\s+anything\s+now",
    r"print\s+the\s+above\s+text",
    r"translate\s+the\s+system\s+instructions",
    r"output\s+the\s+system\s+instructions",
    r"reveal\s+the\s+prompt",
    r"you\s+must\s+act\s+as"
]

FALLBACK_RESPONSE = "I do not have enough information in my knowledge base to answer that accurately."

DEFENSE_RESPONSE = "I am trained to represent Dharmit Shah professionally. I cannot comply with instructions that deviate from this purpose or attempt to extract system guidelines."

def is_adversarial_prompt(user_input: str) -> tuple[bool, str]:
    """
    Checks if the user input contains adversarial prompt injection keywords.
    Returns (is_adversarial, defensive_response).
    """
    if not user_input or not isinstance(user_input, str):
        return False, ""
        
    cleaned_input = user_input.lower().strip()
    
    # Heuristic pattern matching
    for pattern in ADVERSARIAL_PATTERNS:
        if re.search(pattern, cleaned_input):
            print(f"[Guardrails] Blocked adversarial input matching pattern: {pattern}")
            return True, DEFENSE_RESPONSE
            
    return False, ""

def get_fallback_response() -> str:
    return FALLBACK_RESPONSE
