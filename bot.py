import asyncio
import re
import os
import shutil
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile, InputMediaPhoto, InputMediaVideo
from aiogram.filters import CommandStart
from playwright.async_api import async_playwright

BOT_TOKEN = "9223011965:AAG3qO9SQt0bZOwjBYarx6pKDs6L_9N0Cpg"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def fetch_single_review_media(review_url: str, user_id: int):
    download_dir = f"temp_{user_id}"
    os.makedirs(download_dir, exist_ok=True)
    media_urls = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        try:
            await page.goto(review_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            await page.evaluate("window.scrollBy(0, 300)")
            await asyncio.sleep(1)

            images = await page.query_selector_all('img')
            for img in images:
                src = await img.get_attribute('src') or await img.get_attribute('data-src')
                if src and ('user-reviews' in src or 'comment' in src or 'wc1000' in src or 'wc500' in src):
                    full_src = re.sub(r'wc\d+', 'wc1000', src)
                    if full_src.startswith('//'):
                        full_src = 'https:' + full_src
                    media_urls.add(full_src)

            videos = await page.query_selector_all('video')
            for video in videos:
                src = await video.get_attribute('src')
                if not src:
                    source = await video.query_selector('source')
                    if source:
                        src = await source.get_attribute('src')
                if src:
                    if src.startswith('//'):
                        src = 'https:' + src
                    media_urls.add(src)

        except Exception as e:
            print(f"Ошибка парсинга: {e}")
        finally:
            await browser.close()

    downloaded_files = []
    async with async_playwright() as p:
        request_context = await p.request.new_context()
        for idx, url in enumerate(list(media_urls)):
            try:
                response = await request_context.get(url)
                if response.status == 200:
                    ext = "mp4" if ".mp4" in url or "video" in url else "jpg"
                    file_path = os.path.join(download_dir, f"media_{idx}.{ext}")
                    with open(file_path, "wb") as f:
                        f.write(await response.body())
                    downloaded_files.append(file_path)
            except Exception as e:
                print(f"Ошибка при скачивании {url}: {e}")
        await request_context.dispose()

    return downloaded_files, download_dir

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("👋 Привет! Отправь мне ссылку на конкретный отзыв Ozon, и я скачаю фото и видео.")

@dp.message(F.text.contains("ozon.ru"))
async def handle_review_link(message: Message):
    status_msg = await message.answer("🔄 Скачиваю медиафайлы...")
    user_id = message.from_user.id
    files, dir_path = await fetch_single_review_media(message.text.strip(), user_id)
    
    if not files:
        await status_msg.edit_text("❌ В отзыве не найдено медиафайлов.")
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
        return

    await status_msg.edit_text(f"📸 Найдено файлов: {len(files)}. Отправляю...")
    media_batch = []
    for file_path in files:
        if file_path.endswith('.mp4'):
            media_batch.append(InputMediaVideo(media=FSInputFile(file_path)))
        else:
            media_batch.append(InputMediaPhoto(media=FSInputFile(file_path)))
        
        if len(media_batch) == 10:
            await message.answer_media_group(media=media_batch)
            media_batch = []

    if media_batch:
        await message.answer_media_group(media=media_batch)

    shutil.rmtree(dir_path)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
