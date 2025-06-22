import os, sys

print("CWD is:", os.getcwd())
print("sys.path:")
for p in sys.path:
    print("  ", repr(p))

try:
    import scrapers
    print("✅ Imported scrapers from", scrapers.__file__)
except Exception as e:
    print("❌ Could not import scrapers:", e)
