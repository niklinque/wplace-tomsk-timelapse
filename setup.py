#!/usr/bin/env python3
"""
Скрипт быстрой настройки проекта Wplace Timelapse
"""

import os
import subprocess
import sys

def check_git():
    """Проверяет наличие git"""
    try:
        subprocess.run(['git', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def check_python():
    """Проверяет версию Python"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        return True
    return False

def install_dependencies():
    """Устанавливает зависимости"""
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def create_github_repo():
    """Помогает создать GitHub репозиторий"""
    print("\n📝 Создание GitHub репозитория:")
    print("1. Перейдите на https://github.com/new")
    print("2. Назовите репозиторий: wplace-tomsk-timelapse")
    print("3. Сделайте его публичным")
    print("4. НЕ инициализируйте с README (у нас уже есть)")
    print("5. Создайте репозиторий")
    
    input("\nНажмите Enter когда создадите репозиторий...")
    
    username = input("Введите ваш GitHub username: ").strip()
    
    if username:
        try:
            # Инициализируем git
            subprocess.run(['git', 'init'], check=True)
            subprocess.run(['git', 'add', '.'], check=True)
            subprocess.run(['git', 'commit', '-m', 'Initial commit: Wplace Timelapse setup'], check=True)
            subprocess.run(['git', 'branch', '-M', 'main'], check=True)
            subprocess.run(['git', 'remote', 'add', 'origin', 
                          f'https://github.com/{username}/wplace-tomsk-timelapse.git'], check=True)
            subprocess.run(['git', 'push', '-u', 'origin', 'main'], check=True)
            
            print(f"✅ Репозиторий настроен: https://github.com/{username}/wplace-tomsk-timelapse")
            return username
        except subprocess.CalledProcessError as e:
            print(f"❌ Ошибка настройки git: {e}")
            return None
    
    return None

def setup_github_actions():
    """Инструкции по настройке GitHub Actions"""
    print("\n⚙️ Настройка GitHub Actions:")
    print("1. Перейдите в Settings вашего репозитория")
    print("2. Выберите Actions → General")
    print("3. Убедитесь что включено:")
    print("   - Allow all actions and reusable workflows")
    print("   - Read and write permissions для GITHUB_TOKEN")
    print("4. Сохраните настройки")

def setup_github_pages(username):
    """Инструкции по настройке GitHub Pages"""
    print("\n🌐 Настройка GitHub Pages:")
    print("1. Перейдите в Settings → Pages")
    print("2. В Source выберите 'GitHub Actions'")
    print("3. Сохраните настройки")
    
    if username:
        print(f"\nВаш сайт будет доступен по адресу:")
        print(f"https://{username}.github.io/wplace-tomsk-timelapse/")

def run_first_test():
    """Запускает первый тест"""
    print("\n🧪 Запуск тестового захвата...")
    try:
        import capture_tiles
        capture_tiles.main()
        print("✅ Тестовый захват прошел успешно!")
        
        # Показываем созданные файлы
        if os.path.exists("images"):
            images = [f for f in os.listdir("images") if f.endswith('.png')]
            print(f"📸 Создано изображений: {len(images)}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка тестового захвата: {e}")
        return False

def main():
    """Основная функция настройки"""
    print("🚀 Настройка Wplace Timelapse")
    print("=" * 40)
    
    # Проверки системы
    print("🔍 Проверка системы...")
    
    if not check_python():
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    
    if not check_git():
        print("❌ Git не найден. Установите Git: https://git-scm.com/")
        sys.exit(1)
    
    print("✅ Системные требования выполнены")
    
    # Установка зависимостей
    print("\n📦 Установка зависимостей...")
    if install_dependencies():
        print("✅ Зависимости установлены")
    else:
        print("❌ Ошибка установки зависимостей")
        sys.exit(1)
    
    # Тестовый запуск
    print("\n🧪 Тестовый запуск...")
    if not run_first_test():
        print("⚠️ Тестовый запуск не удался, но продолжаем настройку")
    
    # Настройка GitHub
    setup_choice = input("\n❓ Хотите настроить GitHub репозиторий? (y/n): ").lower()
    
    if setup_choice.startswith('y'):
        username = create_github_repo()
        setup_github_actions()
        setup_github_pages(username)
        
        print("\n🎉 Настройка завершена!")
        print("\nСледующие шаги:")
        print("1. Настройте GitHub Actions и Pages по инструкциям выше")
        print("2. Перейдите в Actions и запустите первый workflow")
        print("3. Подождите 5-10 минут и проверьте ваш сайт")
        
        if username:
            print(f"\n🌐 Ваш сайт: https://{username}.github.io/wplace-tomsk-timelapse/")
    else:
        print("\n✅ Локальная настройка завершена!")
        print("Для тестирования запустите: python test_local.py")

if __name__ == "__main__":
    main()
