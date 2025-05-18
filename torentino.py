import argparse
import logging
import os
import sys
import time


try:
    import libtorrent as lt
except ImportError:
    print(
        "Ошибка: Модуль 'libtorrent' не установлен. Установите его: pip install python-libtorrent"
    )
    sys.exit(10)

from dotenv import load_dotenv


def parse_args():
    """
    Парсит аргументы командной строки для конфигурации загрузчика торрентов.

    Returns:
        argparse.Namespace: Объект с атрибутами для каждого аргумента.
    """
    parser = argparse.ArgumentParser(
        description="Скрипт для скачивания файлов по .torrent через libtorrent."
    )
    parser.add_argument(
        "--torrent",
        help="Путь к .torrent-файлу (или переменная TORRENT_PATH)",
        required=False,
    )
    parser.add_argument(
        "--save-dir",
        help="Папка для сохранения файлов (или SAVE_PATH, по умолчанию /app/downloads)",
        required=False,
    )
    parser.add_argument(
        "--port-start",
        type=int,
        help="Начальный порт (или LISTEN_PORT_START, по умолчанию 6881)",
        required=False,
    )
    parser.add_argument(
        "--port-end",
        type=int,
        help="Конечный порт (или LISTEN_PORT_END, по умолчанию 6891)",
        required=False,
    )
    parser.add_argument(
        "--no-peers-timeout",
        type=int,
        default=300,
        help="Таймаут в секундах при отсутствии пиров (по умолчанию 300 секунд / 5 минут)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Включить подробный режим логирования (DEBUG)",
    )
    parser.add_argument(
        "--logfile",
        help="Путь к файлу лога (по умолчанию только консоль)",
        required=False,
    )
    return parser.parse_args()


def setup_logging(verbose=False, logfile=None):
    """
    Настраивает систему логирования по уровню и выводу в консоль/файл.

    Args:
        verbose (bool): Включить режим DEBUG, если True.
        logfile (str, optional): Путь к файлу для логов.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "[%(asctime)s] %(levelname)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if logfile:
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    for handler in handlers:
        handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(handler)


def find_torrent_file():
    """
    Ищет самый свежий .torrent файл в папках torrents или /app/torrents.

    Returns:
        str or None: Путь к найденному .torrent-файлу, либо None если не найдено.
    """
    search_dirs = ["torrents", "/app/torrents"]
    candidates = []
    for folder in search_dirs:
        if os.path.isdir(folder):
            torrents = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.endswith(".torrent")
            ]
            candidates.extend(torrents)
    if not candidates:
        return None
    # Сортировка по времени создания — самый свежий сверху
    candidates.sort(key=lambda f: os.path.getctime(f), reverse=True)
    return candidates[0]


def get_torrent_name(h):
    """
    Универсально получает имя торрента из handle h для разных сборок libtorrent.
    """
    try:
        tf = h.torrent_file
        if callable(tf):
            tf = tf()
        if hasattr(tf, "name"):
            name_attr = tf.name
            if callable(name_attr):
                return name_attr()
            return name_attr
    except Exception:
        pass
    try:
        info = h.get_torrent_info()
        if hasattr(info, "name"):
            name_attr = info.name
            if callable(name_attr):
                return name_attr()
            return name_attr
    except Exception:
        pass
    return "Безымянный торрент"


def main():
    """
    Основная функция загрузки торрент-файлов через libtorrent.

    Последовательно:
    1. Парсит аргументы командной строки и окружение.
    2. Ищет или выбирает .torrent-файл.
    3. Настраивает libtorrent с нужными портами.
    4. Запускает скачивание, отображает прогресс и пишет логи.
    5. Следит за таймаутом по отсутствию пиров, логирует среднюю скорость и ETA.
    """
    load_dotenv()
    args = parse_args()
    setup_logging(verbose=args.verbose, logfile=args.logfile)

    # Поиск .torrent файла: приоритет — аргумент, потом переменная окружения, потом авто-поиск
    torrent_path = args.torrent or os.getenv("TORRENT_PATH")
    if not torrent_path:
        torrent_path = find_torrent_file()
        if torrent_path:
            logging.info(f"Автоматически выбран торрент-файл: {torrent_path}")
        else:
            logging.error(
                "Не найден ни один .torrent файл и не задан TORRENT_PATH."
            )
            logging.shutdown()
            sys.exit(1)

    if not torrent_path or not os.path.exists(torrent_path):
        logging.error(f"Файл не найден: {torrent_path}")
        sys.exit(1)

    # Подготовка путей и портов
    save_path = args.save_dir or os.getenv("SAVE_PATH", "/app/downloads")
    port_start = args.port_start or int(os.getenv("LISTEN_PORT_START", "6881"))
    port_end = args.port_end or int(os.getenv("LISTEN_PORT_END", "6891"))

    logging.info("Запуск загрузчика торрентов")
    logging.info(f"libtorrent version: {lt.version}")
    logging.info(f"TORRENT_PATH: {torrent_path}")
    logging.info(f"SAVE_PATH: {save_path}")
    logging.info(f"LISTEN_PORT_START: {port_start}")
    logging.info(f"LISTEN_PORT_END: {port_end}")
    logging.info(f"NO_PEERS_TIMEOUT: {args.no_peers_timeout} секунд")

    try:
        os.makedirs(save_path, exist_ok=True)
    except Exception as e:
        logging.error(f"Не удалось создать папку {save_path}: {e}")
        sys.exit(1)

    try:
        # Инициализация сессии libtorrent и настройка портов
        logging.info("Инициализация libtorrent...")
        ses = lt.session()
        ses.apply_settings(
            {"listen_interfaces": f"0.0.0.0:{port_start}-{port_end}"}
        )

        # Чтение .torrent-файла и подготовка параметров для скачивания
        logging.info(f"Чтение .torrent файла: {torrent_path}")
        info = lt.torrent_info(torrent_path)
        params = {
            "save_path": save_path,
            "storage_mode": lt.storage_mode_t(2),  # Используем sparse storage
            "ti": info,
        }

        # Добавление торрента в сессию
        logging.info("Добавление торрента в сессию...")
        h = ses.add_torrent(params)

        # Универсальный способ получить имя торрента (любая версия libtorrent)
        torrent_name = get_torrent_name(h)
        logging.info(f"Скачивание файла: {torrent_name}")

        last_progress = -1
        start_time = time.time()
        no_peers_time = 0
        no_peers_timer_active = (
            False  # Флаг для отслеживания логов по старту таймера
        )

        try:
            while True:
                s = h.status()
                progress = int(s.progress * 100)
                # 1. Отслеживаем таймаут по отсутствию пиров
                if s.num_peers == 0:
                    no_peers_time += 1
                    if not no_peers_timer_active:
                        print()  # Перевод строки после прогресс-бара
                        logging.warning(
                            "Нет подключённых пиров. Запущен таймер автоостановки по отсутствию пиров."
                        )
                        no_peers_timer_active = True
                    if no_peers_time >= args.no_peers_timeout:
                        logging.error(
                            f"Пиров нет {args.no_peers_timeout} секунд подряд. Загрузка прервана."
                        )
                        print()
                        sys.exit(5)
                else:
                    if no_peers_timer_active:
                        print()  # Перевод строки после прогресс-бара
                        logging.info(
                            f"Появились пиры спустя {no_peers_time} секунд ожидания. Сбрасываем таймер."
                        )
                        no_peers_timer_active = False
                    no_peers_time = 0

                # 2. Вывод прогресса с ETA
                if progress != last_progress:
                    downloaded = s.total_done / (1024 * 1024)
                    total = s.total_wanted / (1024 * 1024)
                    speed = s.download_rate / 1024  # KB/s
                    # ETA расчёт
                    if s.download_rate > 0:
                        eta_seconds = int(
                            (s.total_wanted - s.total_done) / s.download_rate
                        )
                        if eta_seconds > 3600:
                            eta_str = f"{eta_seconds // 3600}ч {(eta_seconds % 3600) // 60}м"
                        elif eta_seconds > 60:
                            eta_str = (
                                f"{eta_seconds // 60}м {eta_seconds % 60}с"
                            )
                        else:
                            eta_str = f"{eta_seconds}с"
                    else:
                        eta_str = "—"
                    sys.stdout.write(
                        f"\rПрогресс: {progress}% | "
                        f"Скачано: {downloaded:.2f}/{total:.2f} MB | "
                        f"Скорость: {speed:.2f} KB/s | "
                        f"ETA: {eta_str} | "
                        f"Пиров: {s.num_peers}   "
                    )
                    sys.stdout.flush()
                    last_progress = progress
                if s.state == lt.torrent_status.seeding:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            logging.warning(
                "Операция скачивания прервана пользователем (Ctrl+C)."
            )
            sys.exit(4)

        elapsed = time.time() - start_time
        print()
        logging.info("Скачивание завершено!")
        logging.info(f"Файлы сохранены в: {save_path}")

        # Итоговая средняя скорость (MB/s)
        try:
            total = s.total_wanted / (1024 * 1024)
            average_speed_mb = total / elapsed if elapsed > 0 else 0
            average_speed_kb = average_speed_mb * 1024
            logging.info(
                f"Средняя скорость за сессию: {average_speed_kb:.2f} KB/s"
            )
        except Exception as e:
            logging.warning(f"Не удалось вычислить среднюю скорость: {e}")

        # Выводим список загруженных файлов
        logging.info("Список файлов:")
        for root, dirs, files in os.walk(save_path):
            for file in files:
                logging.info(f"- {os.path.join(root, file)}")

        logging.info(f"Общее время скачивания: {elapsed:.1f} сек.")

    except Exception as e:
        msg = str(e).lower()
        if "invalid" in msg and "torrent" in msg:
            logging.error("Неверный .torrent-файл или повреждён.")
            sys.exit(2)
        else:
            logging.error(f"{type(e).__name__}: {e}")
            sys.exit(3)


if __name__ == "__main__":
    main()
