# core/openai_utils.py

import os
import re
import json
import openai
from dotenv import load_dotenv
from typing import Dict

# Load key once
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("OPENAI_API_KEY is not set. Aborting.")

def extract_vehicle_info(
    raw_text: str,
    system_prompt: str,
    debug: bool = True,
    max_tokens: int = 1000
) -> Dict:
    """
    Send raw_text to GPT with system_prompt, return parsed JSON dict.
    If debug, prints first 200 chars of the raw response.
    """
    # 1) Clean ellipses
    safe_text = raw_text.replace("…", "...")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": safe_text}
    ]
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens
        )
        raw = resp.choices[0].message.content
        if debug:
            snippet = raw[:200].replace("\n"," ") + " …"
            print("RAW GPT→JSON (first 200 chars):", snippet)
        # strip ```json fences
        cleaned = re.sub(r'^```json\s*|\s*```$', '', raw.strip())
        return json.loads(cleaned)
    except Exception as e:
        if debug:
            print("OpenAI extraction error:", repr(e))
        return {}
