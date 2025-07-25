import logging
import gc
import asyncio
import sys

from aiogram.types import FSInputFile
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties

from net import *
from functions import *

API_TOKEN = "7851212851:AAFjumFjDljm0ckBdST6aqMWHFuTH7mE4Ow"

# Инициализация логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные
flag = True
content_flag = False
style_flag = False

# Модель
style_model = Net(ngf=128)
style_model.load_state_dict(torch.load("21styles.model"), False)

# Router
router = Router()


def transform(content_root, style_root, im_size):
    content_image = tensor_load_rgbimage(
        content_root, size=im_size, keep_asp=True
    ).unsqueeze(0)
    style = tensor_load_rgbimage(style_root, size=im_size).unsqueeze(0)
    style = preprocess_batch(style)
    style_v = Variable(style)
    content_image = Variable(preprocess_batch(content_image))
    style_model.setTarget(style_v)
    output = style_model(content_image)
    tensor_save_bgrimage(output.data[0], "result.jpg", False)

    del content_image, style, style_v, output
    torch.cuda.empty_cache()
    gc.collect()


@router.message(Command("start"))
async def cmd_start(message: Message):
    try:
        await message.answer("Привет! Используй /help для инструкции.")
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")


@router.message(Command("help"))
async def cmd_help(message: Message):
    try:
        await message.answer(
            "Отправь изображение-контент, затем изображение-стиль. "
            "После выбери качество и получишь результат.\n\n"
            "Команды:\n"
            "/cancel — сбросить изображения\n"
            "/continue — начать обработку\n"
            "/creator — автор бота"
        )
    except Exception as e:
        logger.error(f"Ошибка в /help: {e}")


@router.message(Command("test"))
async def cmd_test(message: Message):
    try:
        await message.answer("It works!")
    except Exception as e:
        logger.error(f"Ошибка в /test: {e}")


@router.message(Command("creator"))
async def cmd_creator(message: Message):
    try:
        await message.answer(
            "Создатель: toefL\nhttps://github.com/t0efL/Style-Transfer-Telegram-Bot"
        )
    except Exception as e:
        logger.error(f"Ошибка в /creator: {e}")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    global flag, content_flag
    try:
        if not content_flag:
            await message.answer("Ты ещё не отправил контент-изображение.")
        else:
            flag = not flag
            await message.answer("Успешно сброшено.")
    except Exception as e:
        logger.error(f"Ошибка в /cancel: {e}")


@router.message(Command("continue"))
async def cmd_continue(message: Message):
    global content_flag, style_flag
    try:
        if not (content_flag and style_flag):
            await message.answer("Ты ещё не загрузил оба изображения.")
            return

        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Low")],
                [KeyboardButton(text="Medium")],
                [KeyboardButton(text="High")],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await message.answer("Выбери качество изображения:", reply_markup=kb)
    except Exception as e:
        logger.error(f"Ошибка в /continue: {e}")


@router.message(F.photo)
async def photo_handler(message: Message):
    global flag, content_flag, style_flag
    try:
        if flag:
            try:
                await message.bot.download(message.photo[-1], destination="content.jpg")
                await message.answer(
                    "Контент изображение получено. Теперь отправь стиль."
                )
                flag = False
                content_flag = True
            except Exception as e:
                logger.error(f"Ошибка при скачивании контент-изображения: {e}")
                await message.answer(
                    "Ошибка при получении изображения. Попробуй ещё раз."
                )
        else:
            try:
                await message.bot.download(message.photo[-1], destination="style.jpg")
                await message.answer(
                    "Стиль получен. Используй /continue для обработки."
                )
                flag = True
                style_flag = True
            except Exception as e:
                logger.error(f"Ошибка при скачивании стиля: {e}")
                await message.answer(
                    "Ошибка при получении изображения-стиля. Попробуй ещё раз."
                )
    except Exception as e:
        logger.error(f"Ошибка в photo_handler: {e}")
        await message.answer("Произошла ошибка при обработке изображения.")


@router.message(F.text.in_({"Low", "Medium", "High"}))
async def quality_handler(message: Message):
    quality_map = {"Low": 256, "Medium": 300, "High": 350}
    image_size = quality_map.get(message.text, 256)
    try:
        await message.answer(
            "Началась обработка, подожди немного...", reply_markup=ReplyKeyboardRemove()
        )
        try:
            transform("content.jpg", "style.jpg", image_size)
        except Exception as e:
            logger.error(f"Ошибка при трансформации: {e}")
            await message.answer("Ошибка при обработке изображения. Попробуй ещё раз.")
            return
        try:
            photo = FSInputFile("result.jpg")  # передаём путь к файлу
            await message.answer_photo(photo=photo, caption="Вот ваше изображение")

        except Exception as e:
            logger.error(f"Ошибка при отправке результата: {e}")
            await message.answer("Не удалось отправить результат. Попробуй ещё раз.")
    except Exception as e:
        logger.error(f"Ошибка в quality_handler: {e}")
        await message.answer("Произошла ошибка при выборе качества.")


@router.message()
async def unknown_message(message: Message):
    try:
        await message.answer(
            "Пожалуйста, отправь фото или используй команды. Для справки — /help"
        )
    except Exception as e:
        logger.error(f"Ошибка в unknown_message: {e}")


async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Ошибка запуска бота: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
