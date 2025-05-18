import argparse
import logging
import os
import sys
import time
import requests
import traceback

try:
    import libtorrent as lt
except ImportError:
    print(
        "Ошибка: Модуль 'libtorrent' не установлен. Установите его: pip install python-libtorrent"
    )
    sys.exit(10)

from dotenv import load_dotenv


def send_telegram(message, token=None, chat_id=None):
    """
    Отправляет уведомление в Telegram-бот.
    chat_id = user_id (без минуса) — сообщение себе в личку
    chat_id = id группы (с минусом) — в группу
    """
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logging.warning("TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID не заданы — уведомление не отправлено.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, data={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if resp.status_code != 200:
            logging.warning(f"Не удалось отправить сообщение в Telegram: {resp.text}")
    except Exception as e:
        logging.warning(f"Ошибка при отправке в Telegram: {e}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Скрипт для скачивания файлов по .torrent через libtorrent."
    )
    parser.add_argument("--torrent", help="Путь к .torrent-файлу (или переменная TORRENT_PATH)", required=False)
    parser.add_argument("--save-dir", help="Папка для сохранения файлов (или SAVE_PATH, по умолчанию /app/downloads)", required=False)
    parser.add_argument("--port-start", type=int, help="Начальный порт (или LISTEN_PORT_START, по умолчанию 6881)", required=False)
    parser.add_argument("--port-end", type=int, help="Конечный порт (или LISTEN_PORT_END, по умолчанию 6891)", required=False)
    parser.add_argument("--no-peers-timeout", type=int, default=300, help="Таймаут в секундах при отсутствии пиров (по умолчанию 300 секунд / 5 минут)")
    parser.add_argument("--verbose", action="store_true", help="Включить подробный режим логирования (DEBUG)")
    parser.add_argument("--logfile", help="Путь к файлу лога (по умолчанию только консоль)", required=False)
    return parser.parse_args()


def setup_logging(verbose=False, logfile=None):
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
    candidates.sort(key=lambda f: os.path.getctime(f), reverse=True)
    return candidates[0]


def get_torrent_name(h):
    try:
        tf = h.torrent_file
        if callable(tf):
            tf = tf()
        if hasattr(tf, 'name'):
            name_attr = tf.name
            if callable(name_attr):
                return name_attr()
            return name_attr
    except Exception:
        pass
    try:
        info = h.get_torrent_info()
        if hasattr(info, 'name'):
            name_attr = info.name
            if callable(name_attr):
                return name_attr()
            return name_attr
    except Exception:
        pass
    return "Безымянный торрент"


def main():
    # === Настройка шага прогресса (в процентах) для Telegram ===
    report_step = 20  # Каждые 20% отправляется уведомление, если есть скорость

    load_dotenv()
    args = parse_args()
    setup_logging(verbose=args.verbose, logfile=args.logfile)

    torrent_path = args.torrent or os.getenv("TORRENT_PATH")
    if not torrent_path:
        torrent_path = find_torrent_file()
        if torrent_path:
            logging.info(f"Автоматически выбран торрент-файл: {torrent_path}")
        else:
            logging.error("Не найден ни один .torrent файл и не задан TORRENT_PATH.")
            logging.shutdown()
            sys.exit(1)

    if not torrent_path or not os.path.exists(torrent_path):
        logging.error(f"Файл не найден: {torrent_path}")
        sys.exit(1)

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
        logging.info("Инициализация libtorrent...")
        ses = lt.session()
        ses.apply_settings({"listen_interfaces": f"0.0.0.0:{port_start}-{port_end}"})

        logging.info(f"Чтение .torrent файла: {torrent_path}")
        info = lt.torrent_info(torrent_path)
        params = {
            "save_path": save_path,
            "storage_mode": lt.storage_mode_t(2),
            "ti": info,
        }

        logging.info("Добавление торрента в сессию...")
        h = ses.add_torrent(params)

        torrent_name = get_torrent_name(h)
        logging.info(f"Скачивание файла: {torrent_name}")

        log_start = [
            f"🧲 <b>Старт загрузки</b>",
            f"<b>Имя:</b> {torrent_name}",
            f"<b>Путь к .torrent:</b> <code>{torrent_path}</code>",
            f"<b>Сохраняем в:</b> <code>{save_path}</code>",
            f"<b>Порты:</b> {port_start}-{port_end}",
            f"<b>Размер:</b> {info.total_size() / (1024*1024):.2f} MB",
            f"<b>libtorrent:</b> {lt.version}",
        ]
        send_telegram('\n'.join(log_start))

        last_progress = -1
        last_reported_percent = 0
        start_time = time.time()
        no_peers_time = 0
        no_peers_timer_active = False

        try:
            while True:
                s = h.status()
                progress = int(s.progress * 100)

                if s.num_peers == 0:
                    no_peers_time += 1
                    if not no_peers_timer_active:
                        print()
                        logging.warning("Нет подключённых пиров. Запущен таймер автоостановки по отсутствию пиров.")
                        send_telegram(
                            f"⚠️ Нет пиров для загрузки <b>{torrent_name}</b> "
                            f"дольше {args.no_peers_timeout} сек. Загрузка будет остановлена, если пиры не появятся."
                        )
                        no_peers_timer_active = True
                    if no_peers_time >= args.no_peers_timeout:
                        logging.error(f"Пиров нет {args.no_peers_timeout} секунд подряд. Загрузка прервана.")
                        send_telegram(
                            f"⚠️ Нет пиров для загрузки <b>{torrent_name}</b> "
                            f"дольше {args.no_peers_timeout} сек. Загрузка остановлена."
                        )
                        print()
                        sys.exit(5)
                else:
                    if no_peers_timer_active:
                        print()
                        downloaded = s.total_done / (1024 * 1024)
                        total = s.total_wanted / (1024 * 1024)
                        speed = s.download_rate / 1024
                        if s.download_rate > 0:
                            eta_seconds = int((s.total_wanted - s.total_done) / s.download_rate)
                            if eta_seconds > 3600:
                                eta_str = f"{eta_seconds // 3600}ч {(eta_seconds % 3600) // 60}м"
                            elif eta_seconds > 60:
                                eta_str = f"{eta_seconds // 60}м {eta_seconds % 60}с"
                            else:
                                eta_str = f"{eta_seconds}с"
                        else:
                            eta_str = "—"
                        logging.info(f"Появились пиры спустя {no_peers_time} секунд ожидания. Сбрасываем таймер.")
                        send_telegram(
                            f"✅ Появились пиры для загрузки <b>{torrent_name}</b> спустя {no_peers_time} сек. "
                            f"Статус: <b>{progress}%</b> | ETA: {eta_str} | "
                            f"Скачано: {downloaded:.2f}/{total:.2f} MB"
                        )
                        no_peers_timer_active = False
                    no_peers_time = 0

                # Отправка прогресса только если есть скорость скачивания > 0
                downloaded = s.total_done / (1024 * 1024)
                total = s.total_wanted / (1024 * 1024)
                speed = s.download_rate / 1024  # KB/s
                if s.download_rate > 0:
                    if s.download_rate > 0:
                        eta_seconds = int((s.total_wanted - s.total_done) / s.download_rate)
                        if eta_seconds > 3600:
                            eta_str = f"{eta_seconds // 3600}ч {(eta_seconds % 3600) // 60}м"
                        elif eta_seconds > 60:
                            eta_str = f"{eta_seconds // 60}м {eta_seconds % 60}с"
                        else:
                            eta_str = f"{eta_seconds}с"
                    else:
                        eta_str = "—"
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

                # Отправка прогресса каждые report_step% только если есть скорость
                if (progress // report_step > last_reported_percent // report_step and 
                        progress != 100 and s.download_rate > 0):
                    send_telegram(
                        f"📊 Прогресс: <b>{progress}%</b> | ETA: {eta_str} | "
                        f"Скачано: {downloaded:.2f}/{total:.2f} MB | "
                        f"Пиров: {s.num_peers}"
                    )
                    last_reported_percent = progress
                last_progress = progress

                if s.state == lt.torrent_status.seeding:
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            logging.warning("Операция скачивания прервана пользователем (Ctrl+C).")
            send_telegram(
                f"⛔️ Скачивание <b>{torrent_name}</b> остановлено пользователем (Ctrl+C)."
            )
            sys.exit(4)

        elapsed = time.time() - start_time
        print()
        logging.info("Скачивание завершено!")

        try:
            total = s.total_wanted / (1024 * 1024)
            average_speed_mb = total / elapsed if elapsed > 0 else 0
            average_speed_kb = average_speed_mb * 1024
            logging.info(f"Средняя скорость за сессию: {average_speed_kb:.2f} KB/s")
        except Exception as e:
            average_speed_kb = 0
            logging.warning(f"Не удалось вычислить среднюю скорость: {e}")

        log_end = [
            f"✅ <b>Загрузка завершена</b>",
            f"<b>Имя:</b> {torrent_name}",
            f"<b>Время:</b> {elapsed:.1f} сек",
            f"<b>Средняя скорость:</b> {average_speed_kb:.2f} KB/s",
            f"<b>Файлы:</b>",
        ]
        for root, dirs, files in os.walk(save_path):
            for file in files:
                log_end.append(f"• <code>{os.path.join(root, file)}</code>")

        send_telegram('\n'.join(log_end))
        logging.info(f"Общее время скачивания: {elapsed:.1f} сек.")

    except Exception as e:
        msg = str(e).lower()
        logging.error(f"{type(e).__name__}: {e}")
        logging.error(traceback.format_exc())
        send_telegram(
            f"❌ Ошибка при загрузке: <b>{locals().get('torrent_name', 'N/A')}</b>\n"
            f"Проблема: {type(e).__name__}: {e}\n\n<pre>{traceback.format_exc()}</pre>"
        )
        sys.exit(3)


if __name__ == "__main__":
    main()
