import os

def should_exclude(name):
    """Определяет, нужно ли исключить файл или папку."""
    exclude_list = [
        '__pycache__',  # Служебная папка Python
        'config.py',    # Исключаем config.py
        'for_llm.py',
        'db_schema.py',
        'make_root.py',
        'listing_',
        'venv',
        '.env',
        'video-434117-191174d88f42.json',
        '.pyc',         # Скомпилированные файлы Python
        '__init__.py',  # Пустые файлы инициализации
    ]
    return any(excluded in name for excluded in exclude_list)

def generate_listing(directory, output_file, base_dir='.'):
    """Генерирует листинг для указанной директории и записывает в файл."""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"==================================================\n")
        f.write(f"Directory: {directory}\n")
        f.write(f"==================================================\n\n")

        for root, dirs, files in os.walk(directory):
            # Исключаем служебные папки
            dirs[:] = [d for d in dirs if not should_exclude(d)]
            # Исключаем служебные файлы
            files = [file for file in files if not should_exclude(file)]

            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, base_dir)
                f.write(f"File: .\\{relative_path}\n")
                f.write(f"----------------------------------------\n")
                try:
                    with open(file_path, 'r', encoding='utf-8') as file_content:
                        f.write(file_content.read())
                        f.write("\n\n")
                except Exception as e:
                    f.write(f"Error reading file: {str(e)}\n\n")

def main():
    # Текущая директория
    current_dir = '.'
    
    # Листинг для файлов в текущей директории (без подпапок)
    root_files_output = 'listing_root.txt'
    with open(root_files_output, 'w', encoding='utf-8') as f:
        f.write(f"==================================================\n")
        f.write(f"Directory: {current_dir}\n")
        f.write(f"==================================================\n\n")
        for file in os.listdir(current_dir):
            if os.path.isfile(file) and not should_exclude(file):
                f.write(f"File: .\\{file}\n")
                f.write(f"----------------------------------------\n")
                try:
                    with open(file, 'r', encoding='utf-8') as file_content:
                        f.write(file_content.read())
                        f.write("\n\n")
                except Exception as e:
                    f.write(f"Error reading file: {str(e)}\n\n")
    print(f"Сгенерирован листинг корневой директории: {root_files_output}")

    # Листинг для каждой подпапки
    for dir_name in os.listdir(current_dir):
        dir_path = os.path.join(current_dir, dir_name)
        if os.path.isdir(dir_path) and not should_exclude(dir_name):
            output_file = f"listing_{dir_name}.txt"
            generate_listing(dir_path, output_file, base_dir=current_dir)
            print(f"Сгенерирован листинг для папки '{dir_name}': {output_file}")

if __name__ == "__main__":
    main()