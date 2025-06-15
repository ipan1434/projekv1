# Telegram Checker Bot

Bot Telegram multifungsi untuk mengecek nomor Telegram, OTP, A2F, mendapatkan informasi pengguna dengan BotAcax API, dan berinteraksi dengan AI (OpenAI & Gemini).

## Fitur Utama

* **Cek Nomor Telegram**: Verifikasi apakah nomor telepon terdaftar di Telegram.
* **Cek OTP**: Memvalidasi kode OTP yang diterima.
* **Cek A2F (Two-Factor Authentication)**: Memverifikasi kode A2F.
* **Informasi Pengguna (`/getuser`)**: Mendapatkan detail pengguna dari database bot, Telegram API, dan informasi eksternal seperti akun GitHub melalui BotAcax API (membutuhkan API Key BotAcax).
* **AI Chatbot**:
    * `/ask_openai <pertanyaan>`: Bertanya kepada OpenAI (ChatGPT).
    * `/ask_gemini <pertanyaan>`: Bertanya kepada Google Gemini.
* **Manajemen Akses**: Fitur `/getuser` hanya bisa diakses oleh Owner dan Admin yang terdaftar.
* **Database MongoDB**: Menyimpan data pengguna bot dan riwayat pengecekan.

## Prasyarat

Sebelum menjalankan bot, pastikan Anda memiliki:

* **Python 3.8+**
* **MongoDB Database**: (Disarankan MongoDB Atlas untuk cloud database gratis)
* **Telegram API ID & API Hash**: Dapatkan dari [my.telegram.org](https://my.telegram.org/).
* **Telegram Bot Token**: Buat bot baru melalui [@BotFather](https://t.me/BotFather).
* **OpenAI API Key**: Dapatkan dari [platform.openai.com/api-keys](https://platform.openai.com/api-keys).
* **Google Gemini API Key**: Dapatkan dari [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
* **BotAcax API Key & URL**: Dapatkan dari penyedia BotAcax API. (Jika Anda tidak memiliki ini, fitur terkait tidak akan berfungsi).

## Instalasi

1.  **Clone Repositori (Jika Anda mengunduh sebagai zip, lewati langkah ini):**
    ```bash
    git clone [https://github.com/your-username/telegram-checker-bot.git](https://github.com/your-username/telegram-checker-bot.git)
    cd telegram-checker_bot
    ```

2.  **Buat Lingkungan Virtual (Opsional tapi Direkomendasikan):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # Untuk Linux/macOS
    # venv\Scripts\activate   # Untuk Windows
    ```

3.  **Instal Dependensi Python:**
    ```bash
    pip install -r requirements.txt
    ```
    (Jika Anda belum memiliki `requirements.txt`, buat dulu dengan `pip freeze > requirements.txt` setelah menginstal semua dependensi secara manual).
    Atau instal satu per satu:
    ```bash
    pip install pyrogram pymongo openai google-generativeai requests
    ```
4. **Deploy vps only support ubuntu/debian:**
  ```
  sudo apt update && sudo apt upgrade -y
  ```
    sudo apt install python3 python3-pip -y
  ``` 
  sudo apt install screen -y # atau sudo apt install tmux -y
  ```
    git clone [https://github.com/your-username/telegram-checker-bot.git](https://github.com/your-username/telegram-checker-bot.git) && cd telegram_checker_bot
    ```
    pip3 install -r requirements.txt
    ```
    pip install yt-dlp 
    ```
    sudo apt update && sudo apt install ffmpeg -y
    ```
    screen -S telegram_bot
    ```
    tmux new -s telegram_bot
    ```
    python3 main.py
    ```

4. **Deploy termux Android only**
  ```
  pkg update && pkg upgrade -y
  ```
    pkg install python python-pip && pkg install git -y
  ```
    git clone [https://github.com/your-username/telegram-checker-bot.git](https://github.com/your-username/telegram-checker-bot.git) && cd telegram_checker_bot
    ```
    nano config.py
    ```
    pip install -r requirements.txt
    ```
    pip install yt-dlp
    ```
    pip3 install ffmpeg -y
    ````
    nohup python main.py &
    ```
    python3 main.py
    ```
    
```## Konfigurasi

Buat file-file berikut di dalam direktori proyek Anda:


``` ### `config.py`

Isi dengan kredensial API Anda. **Ganti semua placeholder `YOUR_..._HERE` dengan nilai yang sebenarnya.**

```### penjelasan untuk termux 
### ditutup), Anda bisa menggunakan nohup:Bash
nohup python main.py &
Output akan disimpan di nohup.out. Anda bisa melihat log dengan tail -f nohup.out. Untuk menjalankan secara langsung di foreground:


``` ### `nano congfig.py`
sesudah mengganti congfig.py Tekan Ctrl+X, Y, Enter untuk menyimpan

```### Catatan Penting
Keamanan API Keys: Jangan pernah membagikan file config.py Anda.
Sesi Pyrogram: Proses check_number, check_otp, check_a2f memerlukan Pyrogram Client untuk melakukan simulasi login. Jika API ID/Hash Anda belum pernah login melalui Pyrogram (atau Telegram Desktop/Mobile), mungkin akan memerlukan interaksi awal (memasukkan OTP secara manual di konsol Termux/VPS) saat pertama kali bot mencoba melakukan send_code. Untuk penggunaan produksi, pertimbangkan solusi manajemen sesi yang lebih robust.
Legalitas dan Etika: Penggunaan bot untuk mengecek nomor, OTP, atau kredensial A2F orang lain tanpa izin tegas adalah pelanggaran privasi dan dapat melanggar hukum. Gunakan bot ini secara bertanggung jawab dan etis.
BotAcax API: Pastikan Anda memiliki akses dan izin yang benar untuk menggunakan BotAcax API. Sesuaikan BOTACAX_API_URL dan cara parsing respons JSON-nya di main.py agar sesuai dengan dokumentasi API yang sebenarnya.
Sekarang Anda memiliki seluruh source code dan file README.md yang lengkap dengan panduan deployment untuk VPS dan Termux. Semoga ini sangat membantu!

```python
# config.py

API_ID = 1234567 # Ganti dengan API ID Telegram Anda
API_HASH = "your_telegram_api_hash_here" # Ganti dengan API Hash Telegram Anda
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # Ganti dengan Bot Token dari @BotFather
MONGO_URI = "mongodb+srv://user:password@cluster.mongodb.net/mydatabase?retryWrites=true&w=majority" # Ganti dengan MongoDB URI Anda

# --- API Keys untuk Fitur Tambahan ---
OPENAI_API_KEY = "sk-YOUR_OPENAI_API_KEY_HERE" # Ganti dengan OpenAI API Key Anda
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # Ganti dengan Gemini API Key Anda

# URL BotAcax API (Ganti dengan URL API yang benar dan pastikan Anda memiliki API Key jika diperlukan)
BOTACAX_API_URL = "[https://api.botacax.com/v1/userinfo](https://api.botacax.com/v1/userinfo)" # Contoh URL, sesuaikan jika berbeda
BOTACAX_API_KEY = "YOUR_BOTACAX_API_KEY_HERE" # Ganti dengan BotAcax API Key Anda (jika diperlukan)![IMG_20250613_203753_670](https://github.com/user-attachments/assets/91b13034-5e3d-42c8-8f49-cd89a539e961)
