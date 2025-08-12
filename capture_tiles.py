#!/usr/bin/env python3
"""
Скрипт для загрузки тайлов с wplace.live и создания объединенного изображения
"""

import os
import requests
import json
from datetime import datetime
from PIL import Image
import time

# Координаты тайлов для загрузки (3x3 сетка)
TILE_COORDS = [
    (1506, 631), (1507, 631), (1508, 631),
    (1506, 632), (1507, 632), (1508, 632),
    (1506, 633), (1507, 633), (1508, 633)
]

BASE_URL = "https://backend.wplace.live/files/s0/tiles"
TILES_DIR = "tiles"
IMAGES_DIR = "images"
DOCS_DIR = "docs"

def ensure_directories():
    """Создает необходимые директории"""
    for directory in [TILES_DIR, IMAGES_DIR, DOCS_DIR, f"{DOCS_DIR}/images"]:
        os.makedirs(directory, exist_ok=True)

def download_tile(x, y, session, max_retries=3):
    """Загружает тайл с заданными координатами"""
    url = f"{BASE_URL}/{x}/{y}.png"
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Ошибка загрузки тайла {x}/{y} (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Экспоненциальная задержка
            else:
                raise

def merge_tiles(tile_data, grid_size=(3, 3), tile_size=(1000, 1000)):
    """Объединяет тайлы в одно изображение"""
    merged_width = grid_size[0] * tile_size[0]
    merged_height = grid_size[1] * tile_size[1]
    merged_image = Image.new('RGB', (merged_width, merged_height))
    
    for i, data in enumerate(tile_data):
        if data is None:
            continue
            
        try:
            tile_image = Image.open(data)
            row = i // grid_size[0]
            col = i % grid_size[0]
            x = col * tile_size[0]
            y = row * tile_size[1]
            merged_image.paste(tile_image, (x, y))
        except Exception as e:
            print(f"Ошибка обработки тайла {i}: {e}")
    
    return merged_image

def save_metadata(timestamp, success_count, total_count):
    """Сохраняет метаданные захвата"""
    metadata = {
        'timestamp': timestamp,
        'success_tiles': success_count,
        'total_tiles': total_count,
        'iso_time': datetime.fromtimestamp(timestamp).isoformat()
    }
    
    metadata_file = f"{IMAGES_DIR}/metadata_{int(timestamp)}.json"
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

def update_latest_info(timestamp, filename):
    """Обновляет информацию о последнем изображении"""
    images_list = [f for f in os.listdir(IMAGES_DIR) if f.endswith('.png')]
    
    latest_info = {
        'latest_timestamp': timestamp,
        'latest_filename': filename,
        'latest_iso_time': datetime.fromtimestamp(timestamp).isoformat(),
        'total_images': len(images_list),
        'all_images': sorted(images_list, key=lambda x: int(x.split('_')[1].split('.')[0]), reverse=True)[:50]  # Последние 50 изображений
    }
    
    with open(f"{DOCS_DIR}/latest.json", 'w', encoding='utf-8') as f:
        json.dump(latest_info, f, ensure_ascii=False, indent=2)

def main():
    """Основная функция"""
    ensure_directories()
    
    timestamp = time.time()
    filename = f"wplace_{int(timestamp)}.png"
    
    print(f"Начинаем захват тайлов в {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Загружаем тайлы
    tile_data = []
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Wplace-Timelapse/1.0'
    })
    
    success_count = 0
    
    for x, y in TILE_COORDS:
        try:
            print(f"Загружаем тайл {x}/{y}...")
            data = download_tile(x, y, session)
            from io import BytesIO
            tile_data.append(BytesIO(data))
            success_count += 1
        except Exception as e:
            print(f"Не удалось загрузить тайл {x}/{y}: {e}")
            tile_data.append(None)
    
    if success_count == 0:
        print("Не удалось загрузить ни одного тайла!")
        return
    
    print(f"Успешно загружено {success_count}/{len(TILE_COORDS)} тайлов")
    
    # Объединяем тайлы
    print("Объединяем тайлы...")
    merged_image = merge_tiles(tile_data)
    
    # Сохраняем изображение
    image_path = f"{IMAGES_DIR}/{filename}"
    merged_image.save(image_path, 'PNG', optimize=True)
    
    # Копируем в docs для GitHub Pages
    docs_image_path = f"{DOCS_DIR}/images/{filename}"
    merged_image.save(docs_image_path, 'PNG', optimize=True)
    
    # Сохраняем также как latest.png
    latest_path = f"{DOCS_DIR}/latest.png"
    merged_image.save(latest_path, 'PNG', optimize=True)
    
    print(f"Изображение сохранено: {image_path}")
    
    # Сохраняем метаданные
    save_metadata(timestamp, success_count, len(TILE_COORDS))
    update_latest_info(timestamp, filename)
    
    print("Захват завершен!")

if __name__ == "__main__":
    main()
