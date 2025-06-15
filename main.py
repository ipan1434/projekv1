import os
import requests
import logging
import google.generativeai as genai
from pyrogram import Client, filters
from pyrogram.errors import PhoneNumberInvalid, SessionPasswordNeeded, PhoneCodeExpired, PhoneCodeInvalid, PasswordHashInvalid
from pymongo import MongoClient
from openai import OpenAI
from datetime import datetime
import yt_dlp
import asyncio # Untuk async processes

# Impor konfigurasi dari config.py
from config import (
    API_ID, API_HASH, BOT_TOKEN, MONGO_URI,
    OPENAI_API_KEY, GEMINI_API_KEY,
    BOTACAX_BASE_URL, BOTACAX_API_KEY,
    BOTACAX_USERINFO_ENDPOINT, BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT,
    DOWNLOAD_DIR, COOKIES_FILE
)

# Pastikan direktori download ada
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Konfigurasi Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Inisialisasi MongoDB ---
try:
    client_mongo = MongoClient(MONGO_URI)
    db = client_mongo["telegram_checker_db"]
    users_collection = db["users"]
    telegram_sessions_collection = db["telegram_sessions"] # Untuk potensi manajemen sesi di masa depan
    check_results_collection = db["check_results"]
    logger.info("Koneksi MongoDB berhasil.")
except Exception as e:
    logger.error(f"Gagal terhubung ke MongoDB: {e}")
    exit(1) # Keluar jika tidak bisa terhubung ke DB

# --- Muat Owner dan Admin dari File ---
OWNER_IDS = set()
ADMIN_IDS = set()

def load_ids_from_file(filename):
    ids = set()
    try:
        with open(filename, 'r') as f:
            for line in f:
                try:
                    ids.add(int(line.strip()))
                except ValueError:
                    logger.warning(f"Melewatkan baris tidak valid di {filename}: {line.strip()}")
        logger.info(f"Berhasil memuat ID dari {filename}.")
    except FileNotFoundError:
        logger.warning(f"File {filename} tidak ditemukan. Pastikan file ada jika ingin menggunakan fitur owner/admin.")
    return ids

OWNER_IDS = load_ids_from_file('owners.txt')
ADMIN_IDS = load_ids_from_file('admins.txt')

# --- Inisialisasi Pyrogram Client (Bot) ---
bot = Client(
    "telegram_checker_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
logger.info("Pyrogram Bot Client diinisialisasi.")

# --- Inisialisasi API AI ---
openai_client = None
if OPENAI_API_KEY:
    try:
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client diinisialisasi.")
    except Exception as e:
        logger.error(f"Gagal inisialisasi OpenAI client: {e}")
else:
    logger.warning("OPENAI_API_KEY tidak ditemukan. Fitur OpenAI tidak akan berfungsi.")

gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-pro')
        logger.info("Gemini model diinisialisasi.")
    except Exception as e:
        logger.error(f"Gagal inisialisasi Gemini model: {e}")
else:
    logger.warning("GEMINI_API_KEY tidak ditemukan. Fitur Gemini tidak akan berfungsi.")


# --- Helper Functions ---

def is_owner_or_admin(user_id):
    """Memeriksa apakah user adalah owner atau admin."""
    return user_id in OWNER_IDS or user_id in ADMIN_IDS

def owner_or_admin_only(func):
    """Decorator untuk membatasi akses ke owner dan admin."""
    async def wrapper(client, message):
        if not is_owner_or_admin(message.from_user.id):
            await message.reply_text("⛔️ Maaf, Anda tidak memiliki izin untuk menggunakan fitur ini.")
            return
        await func(client, message)
    return wrapper

async def get_temp_user_client():
    """Mendapatkan sesi Pyrogram sementara untuk pengecekan."""
    try:
        temp_client = Client(
            "temp_checker",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True # Tidak menyimpan sesi ke disk
        )
        await temp_client.start()
        logger.info("Temporary user client started.")
        return temp_client
    except Exception as e:
        logger.error(f"Gagal memulai temporary user client: {e}")
        return None

async def fetch_botacax_userinfo(telegram_id):
    """Mengambil informasi pengguna dari BotAcax API."""
    if not BOTACAX_USERINFO_ENDPOINT or not BOTACAX_API_KEY:
        logger.warning("BOTACAX_USERINFO_ENDPOINT atau BOTACAX_API_KEY tidak diatur.")
        return None

    headers = {"Authorization": f"Bearer {BOTACAX_API_KEY}"}
    params = {"telegram_id": telegram_id}

    try:
        response = requests.get(BOTACAX_USERINFO_ENDPOINT, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Data dari BotAcax UserInfo API untuk {telegram_id}: {data}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from BotAcax UserInfo API for ID {telegram_id}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing JSON from BotAcax UserInfo API for ID {telegram_id}: {e}")
        return None

async def fetch_botacax_tiktok_download(tiktok_url):
    """Mengambil informasi TikTok download dari BotAcax API."""
    if not BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT or not BOTACAX_API_KEY:
        logger.warning("BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT atau BOTACAX_API_KEY tidak diatur.")
        return None
    
    headers = {"Authorization": f"Bearer {BOTACAX_API_KEY}"}
    payload = {"url": tiktok_url} # Asumsi BotAcax menerima URL di body atau param

    try:
        response = requests.post(BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Data dari BotAcax TikTok API untuk {tiktok_url}: {data}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching from BotAcax TikTok API for URL {tiktok_url}: {e}")
        return None
    except ValueError as e:
        logger.error(f"Error parsing JSON from BotAcax TikTok API for URL {tiktok_url}: {e}")
        return None

# --- Event Handlers ---

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id, "is_owner": user_id in OWNER_IDS, "is_admin": user_id in ADMIN_IDS, "last_interaction": datetime.now()})
        logger.info(f"Pengguna baru terdaftar: {user_id} - {user_name}")
    else:
        users_collection.update_one({"_id": user_id}, {"$set": {"last_interaction": datetime.now()}})

    await message.reply_text(
        f"👋 Halo **{user_name}**!\n"
        "Selamat datang di **Telegram Checker Bot**.\n\n"
        "Gunakan perintah berikut untuk fitur pengecekan:\n"
        "  • `/check_number <nomor_telepon>` - Mengecek apakah nomor terdaftar di Telegram.\n"
        "  • `/check_otp <kode_otp>` - Mengecek kode OTP untuk nomor terakhir yang dicek.\n"
        "  • `/check_a2f <password_a2f>` - Mengecek Two-Factor Authentication (A2F).\n\n"
        "Gunakan perintah berikut untuk fitur AI:\n"
        "  • `/ask_openai <pertanyaan>` - Bertanya kepada OpenAI (ChatGPT).\n"
        "  • `/ask_gemini <pertanyaan>` - Bertanya kepada Google Gemini.\n\n"
        "Gunakan perintah berikut untuk Multimedia:\n"
        "  • `/tiktok_dl <url_tiktok>` - Mengunduh video TikTok (tanpa watermark).\n"
        "  • `/song <url_youtube_atau_query>` - Mengunduh dan mengirim audio dari YouTube.\n"
        "  • `/vsong <url_youtube_atau_query>` - Mengunduh dan mengirim video dari YouTube.\n\n"
        "Fitur khusus Owner/Admin:\n"
        "  • `/getuser <user_id>` - Mendapatkan informasi detail pengguna bot, termasuk dari BotAcax."
    )

@bot.on_message(filters.command("check_number") & filters.private)
async def check_telegram_number(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **nomor telepon**.\nContoh: `/check_number +6281234567890`")
        return

    phone_number = message.command[1].strip()
    await message.reply_text(f"⏳ Sedang mengecek nomor: `{phone_number}`...")
    logger.info(f"Mulai cek nomor untuk user {message.from_user.id}: {phone_number}")

    user_client = None
    try:
        user_client = await get_temp_user_client()
        if not user_client:
            await message.reply_text("Terjadi masalah saat menyiapkan sesi pengecekan. Coba lagi.")
            return

        sent_code = await user_client.send_code(phone_number)
        phone_code_hash = sent_code.phone_code_hash

        result_data = {
            "user_id": message.from_user.id,
            "type": "number_check",
            "phone_number": phone_number,
            "status": "Telegram User Found",
            "phone_code_hash": phone_code_hash,
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.info(f"Nomor ditemukan: {phone_number}. Phone Code Hash disimpan.")
        await message.reply_text(
            f"✅ Nomor `{phone_number}` **terdaftar** di Telegram.\n"
            "Kode OTP telah dikirimkan ke nomor tersebut.\n"
            "Sekarang, Anda dapat mengecek OTP dengan perintah:\n"
            "`/check_otp <kode_otp_yang_diterima>`"
        )
    except PhoneNumberInvalid:
        result_data = {
            "user_id": message.from_user.id,
            "type": "number_check",
            "phone_number": phone_number,
            "status": "Phone Number Invalid (Not Registered)",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.info(f"Nomor tidak terdaftar atau invalid: {phone_number}")
        await message.reply_text(
            f"❌ Nomor `{phone_number}` **tidak terdaftar** di Telegram, atau format tidak valid.\n"
            "Pastikan Anda menyertakan kode negara (misal: `+628...`)."
        )
    except Exception as e:
        logger.error(f"Error saat cek nomor {phone_number}: {e}")
        await message.reply_text(f"Terjadi kesalahan saat mengecek nomor: `{e}`")
    finally:
        if user_client:
            await user_client.stop()
            logger.info("Temporary user client stopped.")

@bot.on_message(filters.command("check_otp") & filters.private)
async def check_telegram_otp(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **kode OTP**.\nContoh: `/check_otp 12345`")
        return

    otp_code = message.command[1].strip()
    await message.reply_text(f"⏳ Sedang mengecek OTP: `{otp_code}`...")
    logger.info(f"Mulai cek OTP untuk user {message.from_user.id}: {otp_code}")

    last_check = check_results_collection.find_one(
        {"user_id": message.from_user.id, "type": "number_check"},
        sort=[("timestamp", -1)]
    )

    if not last_check or "phone_code_hash" not in last_check or "phone_number" not in last_check:
        await message.reply_text(
            "Anda perlu melakukan `/check_number` terlebih dahulu untuk mengirim OTP ke nomor target dan mendapatkan informasi yang diperlukan."
        )
        return

    phone_number = last_check["phone_number"]
    phone_code_hash = last_check["phone_code_hash"]

    user_client = None
    try:
        user_client = await get_temp_user_client()
        if not user_client:
            await message.reply_text("Terjadi masalah saat menyiapkan sesi pengecekan OTP. Coba lagi.")
            return

        await user_client.sign_in(phone_number, phone_code_hash, otp_code)

        result_data = {
            "user_id": message.from_user.id,
            "type": "otp_check",
            "phone_number": phone_number,
            "otp_code": otp_code,
            "status": "OTP Valid",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.info(f"OTP valid untuk {phone_number}")
        await message.reply_text(
            f"✅ OTP `{otp_code}` **valid** untuk nomor `{phone_number}`.\n"
            "Akun berhasil login!"
        )
    except PhoneCodeExpired:
        result_data = {
            "user_id": message.from_user.id,
            "type": "otp_check",
            "phone_number": phone_number,
            "otp_code": otp_code,
            "status": "OTP Expired",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.warning(f"OTP kadaluarsa untuk {phone_number}")
        await message.reply_text("❌ Kode OTP sudah **kadaluarsa**.\nSilakan coba lagi dengan `/check_number`.")
    except PhoneCodeInvalid:
        result_data = {
            "user_id": message.from_user.id,
            "type": "otp_check",
            "phone_number": phone_number,
            "otp_code": otp_code,
            "status": "OTP Invalid",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.warning(f"OTP salah untuk {phone_number}")
        await message.reply_text("❌ Kode OTP **salah**.\nMohon masukkan kode yang benar.")
    except SessionPasswordNeeded:
        result_data = {
            "user_id": message.from_user.id,
            "type": "otp_check",
            "phone_number": phone_number,
            "otp_code": otp_code,
            "status": "OTP Valid, A2F Needed",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.info(f"OTP valid, A2F diperlukan untuk {phone_number}")
        await message.reply_text(
            f"✅ OTP `{otp_code}` **valid** tetapi akun `{phone_number}` memiliki **Two-Factor Authentication (A2F)**.\n"
            "Sekarang Anda dapat mengecek A2F dengan perintah:\n"
            "`/check_a2f <password_a2f>`"
        )
    except Exception as e:
        logger.error(f"Error saat cek OTP {otp_code} untuk {phone_number}: {e}")
        await message.reply_text(f"Terjadi kesalahan saat mengecek OTP: `{e}`")
    finally:
        if user_client:
            await user_client.stop()
            logger.info("Temporary user client stopped.")

@bot.on_message(filters.command("check_a2f") & filters.private)
async def check_telegram_a2f(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **kata sandi A2F**.\nContoh: `/check_a2f YourSecretPassword123`")
        return

    a2f_password = message.command[1].strip()
    await message.reply_text(f"⏳ Sedang mengecek A2F dengan sandi: `{a2f_password}`...")
    logger.info(f"Mulai cek A2F untuk user {message.from_user.id}")

    last_otp_check = check_results_collection.find_one(
        {"user_id": message.from_user.id, "type": "otp_check", "status": "OTP Valid, A2F Needed"},
        sort=[("timestamp", -1)]
    )

    if not last_otp_check or "phone_number" not in last_otp_check:
        await message.reply_text(
            "Anda perlu menyelesaikan `/check_otp` yang mengindikasikan A2F diperlukan terlebih dahulu."
        )
        return

    phone_number = last_otp_check["phone_number"]

    user_client = None
    try:
        user_client = await get_temp_user_client()
        if not user_client:
            await message.reply_text("Terjadi masalah saat menyiapkan sesi pengecekan A2F. Coba lagi.")
            return

        await user_client.check_password(a2f_password)

        result_data = {
            "user_id": message.from_user.id,
            "type": "a2f_check",
            "phone_number": phone_number,
            "a2f_password": a2f_password,
            "status": "A2F Valid (Login Successful)",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.info(f"A2F valid untuk {phone_number}. Login berhasil.")
        await message.reply_text(
            f"✅ A2F `{a2f_password}` **valid** untuk nomor `{phone_number}`.\n"
            "**Login ke akun berhasil!**"
        )
    except PasswordHashInvalid:
        result_data = {
            "user_id": message.from_user.id,
            "type": "a2f_check",
            "phone_number": phone_number,
            "a2f_password": a2f_password,
            "status": "A2F Invalid",
            "timestamp": datetime.now()
        }
        check_results_collection.insert_one(result_data)
        logger.warning(f"A2F salah untuk {phone_number}")
        await message.reply_text("❌ Kata sandi A2F **salah**.\nMohon masukkan kata sandi yang benar.")
    except Exception as e:
        logger.error(f"Error saat cek A2F untuk {phone_number}: {e}")
        await message.reply_text(f"Terjadi kesalahan saat mengecek A2F: `{e}`")
    finally:
        if user_client:
            await user_client.stop()
            logger.info("Temporary user client stopped.")

@bot.on_message(filters.command("getuser") & filters.private)
@owner_or_admin_only
async def get_user_info(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **ID pengguna** yang ingin Anda cari.\nContoh: `/getuser 123456789`")
        return

    try:
        target_user_id = int(message.command[1].strip())
    except ValueError:
        await message.reply_text("ID pengguna harus berupa angka yang valid.")
        return

    logger.info(f"Owner/Admin {message.from_user.id} meminta info user: {target_user_id}")
    
    user_info_str = f"**🔍 Informasi Pengguna (ID: `{target_user_id}`):**\n"

    # --- Informasi dari Database Bot ---
    target_user_db = users_collection.find_one({"_id": target_user_id})
    if target_user_db:
        is_owner_status = "✅ Ya" if target_user_db.get("is_owner") else "❌ Tidak"
        is_admin_status = "✅ Ya" if target_user_db.get("is_admin") else "❌ Tidak"
        
        user_info_str += (
            f"  • **Owner di Bot:** {is_owner_status}\n"
            f"  • **Admin di Bot:** {is_admin_status}\n"
            f"  • **Terakhir Interaksi:** {target_user_db.get('last_interaction').strftime('%Y-%m-%d %H:%M:%S') if target_user_db.get('last_interaction') else 'Tidak diketahui'}\n"
        )
    else:
        user_info_str += "  • Status di Bot DB: Tidak terdaftar (Mungkin belum pernah `/start`)\n"

    # --- Informasi dari Telegram API (Pyrogram) ---
    try:
        pyrogram_user = await client.get_users(target_user_id)
        user_info_str += (
            f"  • **Nama Lengkap:** {pyrogram_user.first_name} {pyrogram_user.last_name or ''}\n"
            f"  • **Username:** @{pyrogram_user.username or 'Tidak ada'}\n"
            f"  • **Adalah Bot:** {'✅ Ya' if pyrogram_user.is_bot else '❌ Tidak'}\n"
        )
    except Exception as e:
        logger.warning(f"Gagal mengambil detail Pyrogram user {target_user_id}: {e}")
        user_info_str += "  • Detail Telegram: Tidak dapat diambil (ID mungkin tidak valid atau masalah API).\n"
    
    # --- Informasi dari BotAcax API ---
    if BOTACAX_USERINFO_ENDPOINT and BOTACAX_API_KEY:
        await message.reply_text("⏳ Sedang mengambil informasi dari BotAcax API...")
        botacax_data = await fetch_botacax_userinfo(target_user_id)
        if botacax_data:
            user_info_str += "\n**🌐 Informasi dari BotAcax API:**\n"
            if isinstance(botacax_data, dict) and botacax_data.get('status') == 'success': # Asumsi respons sukses punya 'status': 'success'
                data_payload = botacax_data.get('data')
                if data_payload and isinstance(data_payload, dict):
                    user_info_str += f"  • **Nama Akun:** {data_payload.get('full_name', 'N/A')}\n"
                    user_info_str += f"  • **Username Telegram:** @{data_payload.get('telegram_username', 'N/A')}\n"
                    user_info_str += f"  • **Bio Telegram:** {data_payload.get('telegram_bio', 'N/A')}\n"
                    user_info_str += f"  • **ID GitHub:** {data_payload.get('github_id', 'Tidak ditemukan')}\n"
                    user_info_str += f"  • **Username GitHub:** {data_payload.get('github_username', 'Tidak ditemukan')}\n"
                    user_info_str += f"  • **Email GitHub:** {data_payload.get('github_email', 'Tidak ditemukan')}\n"
                    # Tambahkan data lain sesuai respons BotAcax API Anda
                else:
                    user_info_str += "  • Data akun tidak ditemukan di BotAcax.\n"
            else:
                user_info_str += f"  • Respons BotAcax API: {botacax_data.get('message', str(botacax_data))}\n"
        else:
            user_info_str += "\n🌐 **Informasi dari BotAcax API:** Gagal mengambil atau tidak ditemukan.\n"
    else:
        user_info_str += "\n🌐 **Informasi BotAcax API:** Konfigurasi API tidak lengkap.\n"

    await message.reply_text(user_info_str)

@bot.on_message(filters.command("ask_openai") & filters.private)
async def ask_openai_command(client, message):
    if not openai_client:
        await message.reply_text("❌ Fitur OpenAI tidak diaktifkan atau API Key belum diatur.")
        return

    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **pertanyaan Anda**.\nContoh: `/ask_openai Jelaskan tentang fusi nuklir.`")
        return

    prompt = " ".join(message.command[1:])
    await message.reply_text("⏳ Sedang memproses pertanyaan Anda dengan OpenAI...")
    logger.info(f"User {message.from_user.id} meminta OpenAI: {prompt[:50]}...")

    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo", # Anda bisa mengganti dengan model lain seperti "gpt-4" jika memiliki akses
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        answer = response.choices[0].message.content
        await message.reply_text(f"**🤖 Jawaban dari OpenAI:**\n\n{answer}")
        logger.info(f"Jawaban OpenAI terkirim ke user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error saat memanggil OpenAI API: {e}")
        await message.reply_text(f"Terjadi kesalahan saat memproses permintaan Anda dengan OpenAI: `{e}`")

@bot.on_message(filters.command("ask_gemini") & filters.private)
async def ask_gemini_command(client, message):
    if not gemini_model:
        await message.reply_text("❌ Fitur Gemini AI tidak diaktifkan atau API Key belum diatur.")
        return

    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **pertanyaan Anda**.\nContoh: `/ask_gemini Siapa penemu lampu?`")
        return

    prompt = " ".join(message.command[1:])
    await message.reply_text("⏳ Sedang memproses pertanyaan Anda dengan Gemini AI...")
    logger.info(f"User {message.from_user.id} meminta Gemini: {prompt[:50]}...")

    try:
        response = gemini_model.generate_content(prompt)
        answer = response.text
        await message.reply_text(f"**🤖 Jawaban dari Gemini AI:**\n\n{answer}")
        logger.info(f"Jawaban Gemini AI terkirim ke user {message.from_user.id}")
    except Exception as e:
        logger.error(f"Error saat memanggil Gemini API: {e}")
        await message.reply_text(f"Terjadi kesalahan saat memproses permintaan Anda dengan Gemini AI: `{e}`")

@bot.on_message(filters.command("tiktok_dl") & filters.private)
async def tiktok_download(client, message):
    if not BOTACAX_TIKTOK_DOWNLOAD_ENDPOINT or not BOTACAX_API_KEY:
        await message.reply_text("❌ Fitur TikTok Downloader tidak diaktifkan atau konfigurasi API BotAcax tidak lengkap.")
        return

    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **URL video TikTok** yang ingin diunduh.\nContoh: `/tiktok_dl https://vt.tiktok.com/ZSJxy1234/`")
        return
    
    tiktok_url = message.command[1].strip()
    await message.reply_text(f"⏳ Sedang mengunduh video TikTok dari `{tiktok_url}`...\nIni mungkin memakan waktu.")
    logger.info(f"User {message.from_user.id} meminta download TikTok: {tiktok_url}")

    try:
        botacax_data = await fetch_botacax_tiktok_download(tiktok_url)
        
        if botacax_data and isinstance(botacax_data, dict) and botacax_data.get('status') == 'success':
            video_url = botacax_data.get('data', {}).get('video_url_no_watermark') # Asumsi BotAcax menyediakan ini
            if video_url:
                await message.reply_video(video_url, caption=f"✅ Video TikTok dari {tiktok_url}")
                logger.info(f"Video TikTok berhasil dikirim untuk {tiktok_url}")
            else:
                await message.reply_text("❌ Gagal mendapatkan URL video TikTok tanpa watermark dari BotAcax. Data tidak ditemukan atau format salah.")
        else:
            error_message = botacax_data.get('message', 'Tidak ada data video yang ditemukan.') if botacax_data else 'Respons API tidak valid.'
            await message.reply_text(f"❌ Gagal mengunduh video TikTok: {error_message}")
            logger.warning(f"Gagal download TikTok dari BotAcax: {error_message}")
    except Exception as e:
        logger.error(f"Error saat proses TikTok download untuk {tiktok_url}: {e}")
        await message.reply_text(f"Terjadi kesalahan saat mengunduh video TikTok: `{e}`")

async def download_youtube_media(url_or_query, is_video=False):
    """Mengunduh media dari YouTube menggunakan yt-dlp."""
    ydl_opts = {
        'format': 'bestaudio/best' if not is_video else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'extract_audio': True,
        'audioformat': 'mp3',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title).20s.%(ext)s'), # Batasi panjang nama file
        'quiet': True,
        'no_warnings': True,
        'forcethumbnail': True, # Coba paksa thumbnail
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }] if not is_video else [],
        'external_downloader': 'ffmpeg',
        'external_downloader_args': ['-loglevel', 'error'] # Kurangi log ffmpeg
    }

    # Tambahkan opsi cookies jika file cookies.txt ada
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE
        logger.info(f"Menggunakan file cookies: {COOKIES_FILE}")
    else:
        logger.warning(f"File cookies {COOKIES_FILE} tidak ditemukan. Konten YouTube mungkin tidak dapat diakses.")


    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url_or_query, download=True)
            # Dapatkan jalur file yang sebenarnya setelah diunduh dan diproses
            file_path = ydl.prepare_filename(info_dict)
            if not is_video:
                # yt-dlp mungkin menambahkan ekstensi .mp3 setelah ekstraksi audio
                # Cari file dengan ekstensi audio yang sesuai
                base_name = os.path.splitext(file_path)[0]
                possible_audio_path = f"{base_name}.mp3"
                if os.path.exists(possible_audio_path):
                    file_path = possible_audio_path
            
            # Coba dapatkan thumbnail
            thumbnail_url = None
            if info_dict.get('thumbnails'):
                # Ambil thumbnail kualitas terbaik
                thumbnail_url = info_dict['thumbnails'][-1]['url']
            elif info_dict.get('thumbnail'):
                thumbnail_url = info_dict['thumbnail']

            return file_path, info_dict.get('title'), info_dict.get('duration'), thumbnail_url
    except Exception as e:
        logger.error(f"Error downloading YouTube media ({url_or_query}, video={is_video}): {e}")
        return None, None, None, None

@bot.on_message(filters.command("song") & filters.private)
async def youtube_song_download(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **URL YouTube** atau **query pencarian**.\nContoh: `/song Never Gonna Give You Up` atau `/song https://www.youtube.com/watch?v=dQw4w9WgXcQ`")
        return
    
    query = " ".join(message.command[1:])
    await message.reply_text(f"⏳ Sedang mencari dan mengunduh musik untuk: `{query}`...")
    logger.info(f"User {message.from_user.id} meminta song: {query}")

    file_path, title, duration, thumbnail_url = await download_youtube_media(query, is_video=False)

    if file_path and os.path.exists(file_path):
        try:
            await message.reply_audio(
                audio=file_path,
                caption=f"✅ **{title or 'Musik YouTube'}**",
                duration=duration,
                thumb=thumbnail_url,
                parse_mode='Markdown'
            )
            logger.info(f"Musik berhasil dikirim: {file_path}")
        except Exception as e:
            logger.error(f"Error saat mengirim audio {file_path}: {e}")
            await message.reply_text(f"❌ Terjadi kesalahan saat mengirim musik: `{e}`")
        finally:
            os.remove(file_path)
            logger.info(f"File sementara dihapus: {file_path}")
    else:
        await message.reply_text("❌ Gagal mengunduh musik. Mungkin URL tidak valid, tidak ditemukan, atau masalah jaringan/server.")

@bot.on_message(filters.command("vsong") & filters.private)
async def youtube_video_download(client, message):
    if len(message.command) < 2:
        await message.reply_text("Silakan berikan **URL YouTube** atau **query pencarian**.\nContoh: `/vsong Rick Astley Never Gonna Give You Up` atau `/vsong https://www.youtube.com/watch?v=dQw4w9WgXcQ`")
        return
    
    query = " ".join(message.command[1:])
    await message.reply_text(f"⏳ Sedang mencari dan mengunduh video untuk: `{query}`...\nIni mungkin memakan waktu tergantung ukuran video.")
    logger.info(f"User {message.from_user.id} meminta vsong: {query}")

    file_path, title, duration, thumbnail_url = await download_youtube_media(query, is_video=True)

    if file_path and os.path.exists(file_path):
        try:
            await message.reply_video(
                video=file_path,
                caption=f"✅ **{title or 'Video YouTube'}**",
                duration=duration,
                thumb=thumbnail_url,
                parse_mode='Markdown'
            )
            logger.info(f"Video berhasil dikirim: {file_path}")
        except Exception as e:
            logger.error(f"Error saat mengirim video {file_path}: {e}")
            await message.reply_text(f"❌ Terjadi kesalahan saat mengirim video: `{e}`")
        finally:
            os.remove(file_path)
            logger.info(f"File sementara dihapus: {file_path}")
    else:
        await message.reply_text("❌ Gagal mengunduh video. Mungkin URL tidak valid, tidak ditemukan, atau masalah jaringan/server.")

# --- Jalankan Bot ---
if __name__ == "__main__":
    logger.info("Memulai bot Telegram...")
    bot.run() 