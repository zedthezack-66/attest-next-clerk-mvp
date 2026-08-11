def confidence_for(raw_text: str, method: str) -> dict:
    base = 0.93 if method == "direct_text" else 0.72
    if len(raw_text.strip()) < 80:
        base -= 0.2
    return {"raw_text": max(0.1, round(base, 2))}

