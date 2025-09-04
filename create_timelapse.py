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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import cv2
import numpy as np
from config import *

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы
OUTPUT_DIR = "output"
TIMELAPSE_DIR = "timelapse"

try:
    SCRIPT_TZ = ZoneInfo(TIMEZONE)
except Exception:
    logger.warning(f"Не удалось загрузить часовой пояс '{TIMEZONE}'. Используется UTC.")
    SCRIPT_TZ = ZoneInfo("UTC")

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

    if not images:
        return [], 0, 0

    # Получение размера выпускного видео из последнего дампа
    image_size = Image.open(images[-1])
    video_width, video_height = image_size.size

    if SCALE != 1:
        video_width = int(video_width * SCALE)
        video_height = int(video_height * SCALE)
    
    logger.info(f"Всего найдено {len(images)} изображений за {date_str}")
    return images, video_width, video_height

def resize_image_to_fit(image, scale, width, height, background_color):
    """
    Изменяет размер изображения с сохранением пропорций и добавляет фон.
    
    Args:
        image (PIL.Image): Исходное изображение
        scale (int): Коэффициент масштабирования
        width (int): Ширина получаемого видео
        height (int): Высота получаемого видео
        background_color (tuple): Цвет фона
        
    Returns:
        tuple: (PIL.Image, (x, y, new_width, new_height)) — изображение и позиция/размер вставленного контента
    """

    # Если исходный размер уже совпадает с целевым и размер не отличен от установленного, возвращаем без пересэмплинга
    img_width, img_height = image.size

    if img_width == width and img_height == height:
        if image.mode == 'RGBA':
            composed = Image.new('RGB', (width, height), background_color)
            composed.paste(image, (0, 0), image)
            return composed, (0, 0, width, height)
        return image.convert('RGB'), (0, 0, width, height)
    
    if scale != 1:
        # Новые размеры с сохранением пропорций
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # Выбираем метод ресайза: для кратного масштабирования используем NEAREST (пиксель-перфект)
        down_int = (img_width % width == 0) and (img_height % height == 0)
        up_int = (width % img_width == 0) and (height % img_height == 0)
        resample = Image.NEAREST if (down_int or up_int) else Image.Resampling.LANCZOS
        
        # Изменяем размер изображения
        resized_image = image.resize((new_width, new_height), resample)
    
    # Создаем новое изображение с белым фоном
    result = Image.new('RGB', (width, height), background_color)
    
    # Вычисляем позицию для центрирования
    x = (width - new_width) // 2
    y = (height - new_height) // 2
    
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

def create_timelapse_video(images, output_path, video_width, video_height):
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
        video_writer = cv2.VideoWriter(output_path, fourcc, FPS, (video_width, video_height))
        
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
                resized_image, placement = resize_image_to_fit(pil_image, SCALE, video_width, video_height, BACKGROUND_COLOR)
                
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
        yesterday = datetime.now(SCRIPT_TZ) - timedelta(days=1)
        date_str = yesterday.strftime("%Y%m%d")
    
    logger.info(f"Создаю таймлапс за {date_str}")
    
    # Получаем список изображений за день
    images, video_width, video_height = get_images_for_date(date_str)
    
    if not images:
        logger.warning(f"Не найдено изображений за {date_str}")
        return False
    
    # Создаем имя выходного файла
    output_filename = f"timelapse_{date_str}.mp4"
    output_path = os.path.join(TIMELAPSE_DIR, output_filename)
    
    # Создаем таймлапс
    success = create_timelapse_video(images, output_path, video_width, video_height)
    
    if success:
        logger.info(f"Таймлапс успешно создан: {output_path}")
    else:
        logger.error("Не удалось создать таймлапс")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
