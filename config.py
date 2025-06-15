# config.py

API_ID = 1234567 # Ganti dengan API ID Telegram Anda
API_HASH = "your_telegram_api_hash_here" # Ganti dengan API Hash Telegram Anda
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # Ganti dengan Bot Token dari @BotFather
MONGO_URI = "mongodb+srv://user:password@cluster.mongodb.net/mydatabase?retryWrites=true&w=majority" # Ganti dengan MongoDB URI Anda

# --- API Keys untuk Fitur Tambahan ---
# Jika BotAcax menyediakan OpenAI, Anda bisa menghapus ini dan mengintegrasikan melalui BotAcax.
# Namun, saya akan membiarkannya terpisah untuk fleksibilitas.
OPENAI_API_KEY = "sk-YOUR_OPENAI_API_KEY_HERE" # Ganti dengan OpenAI API Key Anda
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # Ganti dengan Gemini API Key Anda

# URL BotAcax API (Ganti dengan URL API yang benar)
# Ini adalah contoh URL, sesuaikan dengan endpoint BotAcax yang sebenarnya.
BOTACAX_BASE_URL = "https://api.botacax.com/v1/" # Base URL untuk BotAcax
BOTACAX_API_KEY = "YOUR_BOTACAX_API_KEY_HERE" # Ganti dengan BotAcax API Key Anda
# Endpoint spesifik BotAcax yang akan digunakan:
BOTACAX_USERINFO_ENDPOINT = f"{BOTACAX_BASE_URL}userinfo"
BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT = f"{BOTACAX_BASE_URL}tiktok_dl" # Asumsi ada endpoint ini

# Konfigurasi untuk fitur YouTube Download
DOWNLOAD_DIR = "downloads/" # Direktori untuk menyimpan file yang diunduh sementara
COOKIES_FILE = "cookies.txt" # Nama file cookies untuk yt-dlp