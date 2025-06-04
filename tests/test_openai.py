# test_openai.py

import sys
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import os
import openai

# 1) Load .env and assign key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")

print("DEBUG: OPENAI_API_KEY loaded?", bool(openai.api_key))

# 2) Try a minimal ChatCompletion request
try:
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user",   "content": "Say hi in one word."}
        ],
        temperature=0.0,
        max_tokens=5
    )
    print("OPENAI RESPONSE:", resp.choices[0].message.content)
except Exception as e:
    print("OPENAI ERROR:", e)
