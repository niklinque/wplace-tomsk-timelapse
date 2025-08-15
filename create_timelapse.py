#!/usr/bin/env python3
"""
Скрипт для создания видео-таймлапса из дампов изображений.
Собирает все изображения за день и создает видео на белом фоне.
"""

import os
import glob
import logging
import sys
import argparse
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw
import cv2
import numpy as np
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы
OUTPUT_DIR = "output"
TIMELAPSE_DIR = "timelapse"
VIDEO_WIDTH = 9000
VIDEO_HEIGHT = 9000
FPS = 9
BACKGROUND_COLOR = (255, 255, 255)  # Белый фон
TOMSK_TZ = timezone(timedelta(hours=7))

def get_images_for_date(date_str):
    """
    Получает список изображений за указанную дату.
    
    Args:
        date_str (str): Дата в формате YYYYMMDD
        
    Returns:
        list: Список путей к файлам изображений
    """
    images = []
    
    date_folder = os.path.join(OUTPUT_DIR, date_str)
    if os.path.exists(date_folder):
        pattern = os.path.join(date_folder, "merged_tiles_*.png")
        folder_images = glob.glob(pattern)
        images.extend(folder_images)
        logger.info(f"В папке {date_str} найдено {len(folder_images)} изображений")
    
    # Сортируем по дате и времени из имени файла: merged_tiles_YYYYMMDD_HHMMSS.png
    def extract_timestamp_key(file_path):
        filename = os.path.basename(file_path)
        parts = filename.split('_')
        if len(parts) >= 4:
            date_part = parts[2]
            time_part = parts[3].split('.')[0]
            return f"{date_part}_{time_part}"
        return filename
    
    images.sort(key=extract_timestamp_key)
    
    logger.info(f"Всего найдено {len(images)} изображений за {date_str}")
    return images

def resize_image_to_fit(image, target_width, target_height, background_color=(255, 255, 255)):
    """
    Изменяет размер изображения с сохранением пропорций и добавляет белый фон.
    
    Args:
        image (PIL.Image): Исходное изображение
        target_width (int): Целевая ширина
        target_height (int): Целевая высота
        background_color (tuple): Цвет фона
        
    Returns:
        tuple: (PIL.Image, (x, y, new_width, new_height)) — изображение и позиция/размер вставленного контента
    """
    # Если изображение уже совпадает с целевым размером, не масштабируем
    img_width, img_height = image.size
    if img_width == target_width and img_height == target_height:
        return image, (0, 0, target_width, target_height)

    # Вычисляем коэффициент масштабирования для сохранения пропорций
    img_width, img_height = image.size
    scale_w = target_width / img_width
    scale_h = target_height / img_height
    scale = min(scale_w, scale_h)
    
    # Новые размеры с сохранением пропорций
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)
    
    # Изменяем размер изображения
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    # Создаем новое изображение с белым фоном
    result = Image.new('RGB', (target_width, target_height), background_color)
    
    # Вычисляем позицию для центрирования
    x = (target_width - new_width) // 2
    y = (target_height - new_height) // 2
    
    # Вставляем изображение по центру
    if resized_image.mode == 'RGBA':
        result.paste(resized_image, (x, y), resized_image)
    else:
        result.paste(resized_image, (x, y))
    
    return result, (x, y, new_width, new_height)

def add_timestamp_overlay(image, timestamp, font_size=36):
    """
    Добавляет временную метку на изображение.
    
    Args:
        image (PIL.Image): Изображение
        timestamp (str): Временная метка
        font_size (int): Размер шрифта
        
    Returns:
        PIL.Image: Изображение с временной меткой
    """
    # Подготовим RGBA для полупрозрачности
    base = image.convert('RGBA')
    overlay = Image.new('RGBA', base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Вычислим размер текста и позицию по центру снизу
    # Начальная позиция для bbox (0,0), затем отцентрируем вручную
    text_bbox = draw.textbbox((0, 0), timestamp)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    margin_x = 16
    margin_y = 12
    x = (image.width - text_width) // 2
    y = image.height - text_height - margin_y - 8

    # Полупрозрачный (слегка) текст со stroke для читаемости
    draw.text((x, y), timestamp, fill=(255, 255, 255, 230), stroke_width=2, stroke_fill=(0, 0, 0, 160))

    # Композитим и возвращаем в RGB
    composed = Image.alpha_composite(base, overlay).convert('RGB')
    return composed

def create_timelapse_video(images, output_path):
    """
    Создает видео-таймлапс из списка изображений.
    
    Args:
        images (list): Список путей к изображениям
        output_path (str): Путь для сохранения видео
        
    Returns:
        bool: True если успешно, False в случае ошибки
    """
    if not images:
        logger.error("Нет изображений для создания таймлапса")
        return False
    
    try:
        # Инициализируем видео writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(output_path, fourcc, FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))
        
        logger.info(f"Создаю видео с {len(images)} кадрами, FPS: {FPS}")
        
        for i, image_path in enumerate(images):
            try:
                # Загружаем изображение
                pil_image = Image.open(image_path)
                
                # Извлекаем временную метку из имени файла
                filename = os.path.basename(image_path)
                # Формат: merged_tiles_YYYYMMDD_HHMMSS.png
                parts = filename.split('_')
                if len(parts) >= 3:
                    date_part = parts[2]
                    time_part = parts[3].split('.')[0]
                    timestamp = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                else:
                    timestamp = f"Кадр {i+1}"
                
                # Изменяем размер и добавляем на белый фон
                resized_image, placement = resize_image_to_fit(pil_image, VIDEO_WIDTH, VIDEO_HEIGHT, BACKGROUND_COLOR)
                
                # Добавляем временную метку
                final_image = add_timestamp_overlay(resized_image, timestamp)
                
                # Конвертируем PIL в OpenCV формат
                opencv_image = cv2.cvtColor(np.array(final_image), cv2.COLOR_RGB2BGR)
                
                # Записываем кадр в видео
                video_writer.write(opencv_image)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Обработано {i + 1}/{len(images)} кадров")
                    
            except Exception as e:
                logger.error(f"Ошибка при обработке изображения {image_path}: {e}")
                continue
        
        # Закрываем video writer
        video_writer.release()
        logger.info(f"Видео успешно создано: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при создании видео: {e}")
        return False

def send_to_telegram(video_path, date_str):
    """
    Отправляет видео файл в Telegram канал.
    
    Args:
        video_path (str): Путь к видео файлу
        date_str (str): Дата в формате YYYYMMDD
        
    Returns:
        bool: True если успешно отправлено, False в случае ошибки
    """
    # Получаем токен бота и ID канала из переменных окружения
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.warning("Telegram токен или ID канала не настроены. Пропускаем отправку в Telegram.")
        return False
    
    if not os.path.exists(video_path):
        logger.error(f"Видео файл не найден: {video_path}")
        return False
    
    try:
        # Форматируем дату для подписи
        date_obj = datetime.strptime(date_str, "%Y%m%d")
        formatted_date = date_obj.strftime("%d%m%Y")
        
        # Создаем подпись
        caption = f"""🤖 Ежедневный таймлапс за {formatted_date}

[🎬 Репозиторий с автоматизироваными таймлапсами](https://github.com/niklinque/wplace-tomsk-timelapse/)
[📸 Репозиторий с дампами](https://github.com/niklinque/wplace-tomsk/)"""
        
        # URL для отправки документа
        url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
        
        # Открываем файл и отправляем как документ с принудительным именем файла
        with open(video_path, 'rb') as video_file:
            # Принудительно указываем расширение .mp4 для отправки как файла
            filename = f"timelapse_{formatted_date}.mp4"
            files = {'document': (filename, video_file, 'application/octet-stream')}
            data = {
                'chat_id': chat_id,
                'caption': caption,
                'parse_mode': 'Markdown',
                'disable_content_type_detection': True
            }
            
            logger.info(f"Отправляем видео в Telegram канал: {video_path}")
            response = requests.post(url, files=files, data=data, timeout=300)
            
            if response.status_code == 200:
                logger.info("Видео успешно отправлено в Telegram канал")
                return True
            else:
                logger.error(f"Ошибка при отправке в Telegram: {response.status_code}, {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Ошибка при отправке в Telegram: {e}")
        return False

def parse_args():
    parser = argparse.ArgumentParser(description="Создание видео-таймлапса из изображений за день")
    parser.add_argument("--date", dest="date_str", help="Дата в формате YYYYMMDD. По умолчанию — вчера (Томск)")
    return parser.parse_args()

def main():
    """
    Основная функция скрипта.
    """
    # Создаем директорию для таймлапсов
    os.makedirs(TIMELAPSE_DIR, exist_ok=True)
    
    args = parse_args()
    if args.date_str:
        date_str = args.date_str
    else:
        # Получаем вчерашнюю дату (так как скрипт обычно запускается на следующий день)
        yesterday = datetime.now(TOMSK_TZ) - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
    
    logger.info(f"Создаю таймлапс за {date_str}")
    
    # Получаем список изображений за день
    images = get_images_for_date(date_str)
    
    if not images:
        logger.warning(f"Не найдено изображений за {date_str}")
        return False
    
    # Создаем имя выходного файла
    output_filename = f"timelapse_{date_str}.mp4"
    output_path = os.path.join(TIMELAPSE_DIR, output_filename)
    
    # Создаем таймлапс
    success = create_timelapse_video(images, output_path)
    
    if success:
        logger.info(f"Таймлапс успешно создан: {output_path}")
        
        # Также создаем ссылку на последний таймлапс
        latest_path = os.path.join(TIMELAPSE_DIR, "latest.mp4")
        if os.path.exists(latest_path):
            os.remove(latest_path)
        
        # Создаем копию как latest.mp4
        import shutil
        shutil.copy2(output_path, latest_path)
        logger.info(f"Создана копия как: {latest_path}")
        
        # Отправляем видео в Telegram канал
        telegram_success = send_to_telegram(output_path, date_str)
        if telegram_success:
            logger.info("Видео успешно отправлено в Telegram")
        else:
            logger.warning("Не удалось отправить видео в Telegram")

        return True
    else:
        logger.error("Не удалось создать таймлапс")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
