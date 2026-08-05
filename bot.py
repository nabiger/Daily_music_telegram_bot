import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

#  تنظیمات اولیه 
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ADMIN_ID = 000000000  # <---آیدی عددی خودت


#اگر سرور فیلتر بود از این پروکسی استفاده میکنیم
"""
session = AiohttpSession(proxy="http://proxy.server:3128")
bot = Bot(token=BOT_TOKEN, session=session)
"""
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

USERS_FILE = "users.txt"
MUSIC_IDS_FILE = "music_ids.txt"
SENT_MUSIC_FILE = "sent_music.txt"

#  تعریف حالت‌های FSM
class MusicForm(StatesGroup):
    waiting_for_suggestion = State()

#  توابع کمکی 
def get_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def add_user(user_id):
    users = get_users()
    if str(user_id) not in users:
        with open(USERS_FILE, "a") as f:
            f.write(f"{user_id}\n")

def get_all_music_ids():
    if not os.path.exists(MUSIC_IDS_FILE):
        return []
    with open(MUSIC_IDS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_music_id(file_id):
    with open(MUSIC_IDS_FILE, "a") as f:
        f.write(f"{file_id}\n")

def get_sent_music_ids():
    if not os.path.exists(SENT_MUSIC_FILE):
        return set()
    with open(SENT_MUSIC_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def mark_music_as_sent(file_id):
    with open(SENT_MUSIC_FILE, "a") as f:
        f.write(f"{file_id}\n")

#  دکمه‌ها 
def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 دریافت موزیک امروز", callback_data="get_today_music")
    builder.button(text="💡 پیشنهاد موزیک", callback_data="suggest_music")
    builder.adjust(1)  # چیدمان تک‌ستونی دکمه‌ها
    return builder.as_markup()

def get_music_keyboard(bot_username):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="🚀 ارسال برای دوستان", 
            switch_inline_query="پیشنهاد موزیک امروز!"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="🎧 عضویت در ربات", 
            url=f"https://t.me/{bot_username}"
        )
    )
    return builder.as_markup()

#  دریافت و ثبت موزیک از ادمین 
@dp.message(F.audio, F.from_user.id == ADMIN_ID)
async def handle_admin_audio_upload(message: types.Message):
    file_id = message.audio.file_id
    save_music_id(file_id)

    await message.answer(
        " *موزیک با موفقیت به آرشیو اضافه شد!*\n\n", 
        parse_mode="Markdown"
    )

#  بخش پیشنهاد موزیک توسط کاربر 
@dp.callback_query(F.data == "suggest_music")
async def start_suggestion(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(MusicForm.waiting_for_suggestion)
    await callback.message.answer(
        "💡 **پیشنهاد موزیک**\n\n"
        "موزیک پیشنهادیتو بفرست",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(MusicForm.waiting_for_suggestion)
async def receive_suggestion(message: types.Message, state: FSMContext):
    user = message.from_user
    user_info = (
        f"📩 **یک پیشنهاد جدید دریافت شد!**\n\n"
        f"👤 **فرستنده:** {user.full_name}\n"
        f"🆔 **آیدی:** `{user.id}`\n"
        f"🔗 **یوزرنیم:** @{user.username if user.username else 'ندارد'}\n"
        f"━━━━━━━━━━━━━━━"
    )

    # ارسال اطلاعات کاربر برای ادمین
    await bot.send_message(ADMIN_ID, user_info, parse_mode="Markdown")

    # ارسال محتوای پیشنهادی (صوتی یا متنی) برای ادمین
    if message.audio:
        await bot.send_audio(ADMIN_ID, message.audio.file_id, caption="🎧 فایل صوتی ارسالی کاربر")
    elif message.voice:
        await bot.send_voice(ADMIN_ID, message.voice.file_id, caption="🎙️ وویس ارسالی کاربر")
    elif message.text:
        await bot.send_message(ADMIN_ID, f"📝 **متن پیشنهاد:**\n{message.text}")
    else:
        await bot.send_message(ADMIN_ID, "⚠️ کاربر یک فایل غیرمجاز ارسال کرد.")

    await message.answer(
        "✅ **پیشنهاد شما با موفقیت برای ادمین ارسال شد!**\n"
        "ممنون از اینکه به بهتر شدن آرشیو کمک می‌کنی 🙏", 
        parse_mode="Markdown"
    )
    
    # خروج از حالت انتظار
    await state.clear()

#  تابع ارسال موزیک روز 
async def send_music_to_chat(chat_id: int):
    all_ids = get_all_music_ids()
    sent_ids = get_sent_music_ids()
    available_ids = [fid for fid in all_ids if fid not in sent_ids]

    if not available_ids and all_ids:
        if os.path.exists(SENT_MUSIC_FILE):
            os.remove(SENT_MUSIC_FILE)
        available_ids = all_ids

    if not available_ids:
        await bot.send_message(chat_id, "⚠️ *هیچ موزیکی در آرشیو یافت نشد!*", parse_mode="Markdown")
        return

    selected_file_id = random.choice(available_ids)

    bot_info = await bot.get_me()
    keyboard = get_music_keyboard(bot_info.username)

    caption_text = (
        "✨ **Daily Music Pick** ✨\n"
        "━━━━━⬍━━━━━\n\n"
        "🎧 **موزیک پیشنهادی امروز**\n\n"
    )

    await bot.send_audio(
        chat_id=chat_id,
        audio=selected_file_id,
        caption=caption_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    mark_music_as_sent(selected_file_id)

#  ارسال همگانی 
async def send_daily_music():
    users = get_users()
    for user_id in users:
        try:
            await send_music_to_chat(int(user_id))
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"خطا در ارسال به {user_id}: {e}")

#  دستورات 
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    add_user(message.chat.id)
    welcome_text = (
        f"سلام {message.from_user.first_name} عزیز! 👋\n\n"
        "به ربات **Daily Music** خوش آمدید 🎧\n"
        "از منوی زیر گزینه مورد نظرت رو انتخاب کن👇"
    )
    await message.answer(
        welcome_text, 
        parse_mode="Markdown", 
        reply_markup=get_main_menu_keyboard()
    )

@dp.callback_query(F.data == "get_today_music")
async def process_get_music_button(callback: types.CallbackQuery):
    await callback.answer("⏳ در حال ارسال موزیک...")
    await send_music_to_chat(callback.message.chat.id)

#  اجرا
async def main():
    scheduler.add_job(send_daily_music, 'cron', hour=9, minute=0)
    scheduler.start()
    print("ربات آنلاین شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
