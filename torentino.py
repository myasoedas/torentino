"""
torentino.py

Скрипт для скачивания файлов по .torrent через libtorrent.
Поддерживает переменные окружения и аргументы командной строки.
Работает в Docker-контейнере, поддерживает прогресс-бар и логирование.
"""

import argparse
import os
import sys
import time

import libtorrent as lt
from dotenv import load_dotenv


def log(msg):
    print(f"[INFO] {msg}")


def log_error(msg):
    print(f"[ERROR] {msg}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Скрипт для скачивания файлов по .torrent через libtorrent."
    )
    parser.add_argument(
        "--torrent",
        help="Путь к .torrent-файлу (или переменная TORRENT_PATH)",
        required=False
    )
    parser.add_argument(
        "--save-dir",
        help="Папка для сохранения файлов (или SAVE_PATH, по умолчанию /app/downloads)",
        required=False
    )
    parser.add_argument(
        "--port-start",
        type=int,
        help="Начальный порт (или LISTEN_PORT_START, по умолчанию 6881)",
        required=False
    )
    parser.add_argument(
        "--port-end",
        type=int,
        help="Конечный порт (или LISTEN_PORT_END, по умолчанию 6891)",
        required=False
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    torrent_path = args.torrent or os.getenv("TORRENT_PATH")
    save_path = args.save_dir or os.getenv("SAVE_PATH", "/app/downloads")
    port_start = args.port_start or int(os.getenv("LISTEN_PORT_START", "6881"))
    port_end = args.port_end or int(os.getenv("LISTEN_PORT_END", "6891"))

    log("Запуск загрузчика торрентов")
    log(f"TORRENT_PATH: {torrent_path}")
    log(f"SAVE_PATH: {save_path}")
    log(f"LISTEN_PORT_START: {port_start}")
    log(f"LISTEN_PORT_END: {port_end}")

    if not torrent_path:
        log_error("Не указан путь к торрент-файлу (TORRENT_PATH или --torrent).")
        sys.exit(1)
    if not os.path.exists(torrent_path):
        log_error(f"Файл не найден: {torrent_path}")
        sys.exit(1)
    if not os.path.exists(save_path):
        os.makedirs(save_path)
        log(f"Создана папка для сохранения: {save_path}")

    try:
        log("Инициализация libtorrent...")
        ses = lt.session()
        ses.listen_on(port_start, port_end)

        log(f"Чтение .torrent файла: {torrent_path}")
        info = lt.torrent_info(torrent_path)
        params = {
            "save_path": save_path,
            "storage_mode": lt.storage_mode_t(2),
            "ti": info,
        }

        log("Добавление торрента в сессию...")
        h = ses.add_torrent(params)

        log(f"Скачивание файла: {h.name()}")
        last_progress = -1
        start_time = time.time()

        while not h.is_seed():
            s = h.status()
            progress = int(s.progress * 100)
            if progress != last_progress:
                downloaded = s.total_done / (1024 * 1024)
                total = s.total_wanted / (1024 * 1024)
                speed = s.download_rate / 1024
                sys.stdout.write(
                    f"\rПрогресс: {progress}% | "
                    f"Скачано: {downloaded:.2f}/{total:.2f} MB | "
                    f"Скорость: {speed:.2f} KB/s | "
                    f"Пиров: {s.num_peers}   "
                )
                sys.stdout.flush()
                last_progress = progress
            time.sleep(1)

        elapsed = time.time() - start_time
        print()
        log("Скачивание завершено!")
        log(f"Файлы сохранены в: {save_path}")

        log("Список файлов:")
        for root, dirs, files in os.walk(save_path):
            for file in files:
                print(f"- {os.path.join(root, file)}")

        log(f"Общее время скачивания: {elapsed:.1f} сек.")

    except lt.InvalidTorrentFileError:
        log_error("Неверный .torrent-файл или повреждён.")
        sys.exit(2)
    except Exception as e:
        log_error(f"{type(e).__name__}: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
