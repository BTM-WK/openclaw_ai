import base64, os, json
TARGET = r"C:\openclaw\bot"
os.makedirs(TARGET, exist_ok=True)
# Skip config.json (already written with real tokens)
SKIP = ["config.json"]
