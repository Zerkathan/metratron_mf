import os
from dotenv import load_dotenv

# Cargar entorno
load_dotenv()

print("\n🔍 --- AUDITORÍA DE SISTEMAS METRATRON ---")
print(f"📂 Directorio actual: {os.getcwd()}")

# Lista de llaves vitales
keys = [
    "OPENAI_API_KEY",
    "PEXELS_API_KEY",
    "PIXABAY_KEY",
    "RUNWAY_API_KEY"
]

all_good = True

for key in keys:
    value = os.getenv(key)
    if value and len(value) > 5:
        # Mostramos solo el final para verificar sin revelar todo
        print(f"✅ {key}: DETECTADA (...{value[-4:]})")
    else:
        print(f"❌ {key}: NO ENCONTRADA o VACÍA")
        all_good = False

print("-" * 30)

# Verificar archivos físicos
files = ["client_secret.json", "tiktok_cookies.txt"]
for f in files:
    if os.path.exists(f):
        print(f"✅ Archivo {f}: PRESENTE")
    else:
        print(f"❌ Archivo {f}: FALTA")
        all_good = False

print("-" * 30)
if all_good:
    print("🚀 SISTEMAS LISTOS. El problema es tu Internet.")
else:
    print("⚠️ FALTAN PIEZAS. Revisa tu archivo .env")