#!/usr/bin/env python3
"""
Скрипт для создания таймлапс видео из собранных изображений
"""

import os
import json
import glob
from datetime import datetime
import subprocess
import shutil

IMAGES_DIR = "images"
DOCS_DIR = "docs"

def get_image_list():
    """Получает отсортированный список изображений"""
    pattern = f"{IMAGES_DIR}/wplace_*.png"
    images = glob.glob(pattern)
    
    # Сортируем по timestamp в имени файла
    images.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
    
    return images

def create_image_list_file():
    """Создает файл списка изображений для ffmpeg"""
    images = get_image_list()
    
    if len(images) < 2:
        print(f"Недостаточно изображений для создания видео ({len(images)})")
        return None
    
    list_file = f"{DOCS_DIR}/image_list.txt"
    
    with open(list_file, 'w') as f:
        for img in images:
            # Копируем изображения в docs/images если они там еще нет
            basename = os.path.basename(img)
            target_path = f"{DOCS_DIR}/images/{basename}"
            
            if not os.path.exists(target_path):
                shutil.copy2(img, target_path)
            
            # Записываем путь относительно docs директории
            f.write(f"file 'images/{basename}'\n")
            f.write("duration 0.2\n")  # 0.2 секунды на кадр (5 FPS)
    
    return list_file, len(images)

def create_timelapse_with_ffmpeg():
    """Создает таймлапс видео используя ffmpeg"""
    list_file, frame_count = create_image_list_file()
    
    if not list_file:
        return False
    
    output_file = f"{DOCS_DIR}/timelapse.mp4"
    temp_output = f"{DOCS_DIR}/timelapse_temp.mp4"
    
    try:
        # Команда ffmpeg для создания видео
        cmd = [
            'ffmpeg', '-y',  # -y для перезаписи файла
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-vf', 'fps=5,scale=768:768:flags=lanczos',  # 5 FPS, масштабирование
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',  # Качество сжатия
            temp_output
        ]
        
        print(f"Создаем таймлапс из {frame_count} кадров...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=DOCS_DIR)
        
        if result.returncode == 0:
            # Перемещаем временный файл
            if os.path.exists(temp_output):
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(temp_output, output_file)
            
            print(f"Таймлапс создан: {output_file}")
            return True
        else:
            print(f"Ошибка ffmpeg: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("ffmpeg не найден, пытаемся создать таймлапс альтернативным способом...")
        return create_timelapse_fallback()
    except Exception as e:
        print(f"Ошибка создания видео: {e}")
        return False

def create_timelapse_fallback():
    """Альтернативный способ создания таймлапса без ffmpeg"""
    try:
        from PIL import Image
        import io
        
        images = get_image_list()
        
        if len(images) < 2:
            return False
        
        # Создаем анимированный GIF как fallback
        gif_frames = []
        
        print("Создаем анимированный GIF...")
        
        for img_path in images[-50:]:  # Берем последние 50 кадров
            try:
                img = Image.open(img_path)
                # Уменьшаем размер для GIF
                img = img.resize((384, 384), Image.Resampling.LANCZOS)
                gif_frames.append(img)
            except Exception as e:
                print(f"Ошибка обработки {img_path}: {e}")
        
        if gif_frames:
            gif_path = f"{DOCS_DIR}/timelapse.gif"
            gif_frames[0].save(
                gif_path,
                save_all=True,
                append_images=gif_frames[1:],
                duration=200,  # 200ms на кадр
                loop=0,
                optimize=True
            )
            print(f"GIF таймлапс создан: {gif_path}")
            return True
        
    except ImportError:
        print("PIL не доступен для создания GIF")
    except Exception as e:
        print(f"Ошибка создания GIF: {e}")
    
    return False

def update_timelapse_info():
    """Обновляет информацию о таймлапсе"""
    images = get_image_list()
    
    timelapse_info = {
        'total_frames': len(images),
        'latest_update': datetime.now().isoformat(),
        'has_video': os.path.exists(f"{DOCS_DIR}/timelapse.mp4"),
        'has_gif': os.path.exists(f"{DOCS_DIR}/timelapse.gif"),
        'duration_hours': len(images) * 5 / 60,  # 5 минут между кадрами
    }
    
    if images:
        first_timestamp = int(os.path.basename(images[0]).split('_')[1].split('.')[0])
        last_timestamp = int(os.path.basename(images[-1]).split('_')[1].split('.')[0])
        
        timelapse_info.update({
            'first_capture': datetime.fromtimestamp(first_timestamp).isoformat(),
            'last_capture': datetime.fromtimestamp(last_timestamp).isoformat(),
            'time_span_hours': (last_timestamp - first_timestamp) / 3600
        })
    
    with open(f"{DOCS_DIR}/timelapse_info.json", 'w', encoding='utf-8') as f:
        json.dump(timelapse_info, f, ensure_ascii=False, indent=2)

def main():
    """Основная функция"""
    os.makedirs(f"{DOCS_DIR}/images", exist_ok=True)
    
    # Создаем таймлапс
    success = create_timelapse_with_ffmpeg()
    
    if not success:
        print("Не удалось создать видео таймлапс")
    
    # Обновляем информацию
    update_timelapse_info()
    
    print("Генерация таймлапса завершена!")

if __name__ == "__main__":
    main()
