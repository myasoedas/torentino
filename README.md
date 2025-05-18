# 🧲 torentino — Production-ready CLI торрент-загрузчик с поддержкой Telegram-уведомлений

**torentino** — современный CLI-торрент-загрузчик на Python 3 + libtorrent, оптимизированный для запуска в Docker-контейнерах и CI/CD пайплайнах.
Главная фишка — подробное логирование и интеграция с Telegram: все статусы (старт, прогресс, завершение, ошибки) приходят прямо в личные сообщения.
Скрипт автоматически выбирает наиболее свежий .torrent-файл, пишет лог (в консоль и/или файл), выводит прогресс с ETA, завершает работу по таймауту при отсутствии пиров и легко адаптируется под любые сценарии.

---

## 🚀 Быстрый старт

1. **Клонируй репозиторий:**

   ```bash
   git clone https://github.com/myasoedas/torentino.git
   cd torentino
   ```

2. **Положи .torrent-файл(ы) в папку `torrents/`:**

   * Можно добавить один или несколько файлов — скрипт найдёт самый свежий.
   * Либо явно укажи файл через переменную окружения или CLI-аргумент.

3. **Проверь и настрой `.env`:**

   ```env
   SAVE_PATH=/app/downloads
   LISTEN_PORT_START=6881
   LISTEN_PORT_END=6891
   NO_PEERS_TIMEOUT=300
   # TORRENT_PATH=...         # опционально — если нужен конкретный файл
   # TELEGRAM_BOT_TOKEN=...   # опционально, если нужны уведомления
   # TELEGRAM_CHAT_ID=...     # опционально, если нужны уведомления
   ```

4. **Собери Docker-образ:**

   ```bash
   docker build -t torentino .
   ```

---

## ⚡ Использование

### Запуск с автоопределением .torrent

```bash
docker run --rm -it \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/torrents:/app/torrents \
  --env-file .env \
  torentino
```

### Явное указание файла и параметров

```bash
docker run --rm -it \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/torrents:/app/torrents \
  --env-file .env \
  torentino \
  --torrent /app/torrents/yourfile.torrent \
  --save-dir /app/downloads
```

### Включить подробный лог и лог-файл

```bash
docker run --rm -it \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/torrents:/app/torrents \
  --env-file .env \
  torentino \
  --verbose \
  --logfile /app/downloads/torentino.log
```

---

## 📝 CLI Аргументы и переменные окружения

| Аргумент             | Описание                                  | Значение по умолчанию |
| -------------------- | ----------------------------------------- | --------------------- |
| `--torrent`          | Путь к .torrent-файлу                     | Самый свежий из папки |
| `--save-dir`         | Куда скачивать                            | `/app/downloads`      |
| `--port-start`       | Начальный порт для соединения             | 6881                  |
| `--port-end`         | Конечный порт для соединения              | 6891                  |
| `--no-peers-timeout` | Таймаут по отсутствию пиров, сек          | 300                   |
| `--verbose`          | Подробный режим логирования (DEBUG)       | INFO                  |
| `--logfile`          | Путь к файлу лога (stdout, если не задан) | stdout                |

Все параметры можно задать через CLI или через `.env`.

---

## 📲 Telegram-уведомления: как подключить

**torentino** может отправлять уведомления о начале, ходе и завершении загрузки (а также об ошибках) в Telegram — **только при наличии настроенного собственного бота и вашего user ID**.

### Как настроить Telegram-уведомления для себя:

1. **Создай своего Telegram-бота:**

   * Открой [@BotFather](https://t.me/BotFather) в Telegram.
   * Выполни `/newbot`, задай имя и username, получи токен (`TELEGRAM_BOT_TOKEN`).

2. **Узнай свой user ID:**

   * Добавь своего бота в Telegram и **обязательно напиши ему любое сообщение** — иначе Telegram не даст ему право писать тебе первым.
   * Получи свой user ID через [@userinfobot](https://t.me/userinfobot) (это просто, безопасно и быстро).

3. **Добавь настройки в `.env`:**

   ```env
   TELEGRAM_BOT_TOKEN=твой_токен_бота
   TELEGRAM_CHAT_ID=твой_user_id
   ```

   * `TELEGRAM_BOT_TOKEN` — токен твоего бота.
   * `TELEGRAM_CHAT_ID` — твой user ID (без минуса!). Для группы — group chat ID (с минусом).

4. **Пример запуска (с логом и уведомлениями):**

   ```bash
   docker run --rm -it \
     -v $(pwd)/downloads:/app/downloads \
     -v $(pwd)/torrents:/app/torrents \
     --env-file .env \
     torentino --verbose --logfile /app/downloads/torentino.log
   ```

   > Если `TELEGRAM_BOT_TOKEN` или `TELEGRAM_CHAT_ID` не заданы, уведомления отправляться не будут.

**Внимание:**

* Никогда не публикуй свой токен бота в публичном репозитории!
* Для теста можно использовать чужого бота (например, [@Torentino\_ru\_bot](https://t.me/Torentino_ru_bot)), но это только для примера. Рекомендуется регистрировать своего.

---

## 🚦 Ключевые возможности

* **Production-ready:** минимальные зависимости, полностью изолирован Docker-образ, строгий PEP8.
* **Telegram-уведомления:** push-уведомления по ключевым этапам и ошибкам.
* **Автоматический выбор .torrent:** всегда используется наиболее свежий файл.
* **Прогресс-бар:** процент, размер, скорость, ETA, число пиров.
* **Логирование:** раздельно в консоль и/или файл, чистый вывод.
* **Таймаут по отсутствию пиров:** завершение процесса, если нет пиров дольше заданного времени.
* **Корректное завершение:** обработка ошибок, сигналов, Ctrl+C.
* **Кроссплатформенно:** работает в Docker на любом Linux/Windows/MacOS.
* **Совместим с CI/CD:** для автозагрузки в автоматизированных пайплайнах.
* **Лёгкая доработка:** поддержка magnet-ссылок, web-интерфейса и пр.

---

## 📦 Структура проекта

```
torentino/
├── Dockerfile
├── torentino.py
├── .env
├── downloads/         # файлы после загрузки (монтируется)
├── torrents/          # .torrent-файлы (монтируется)
└── README.md
```

---

## 💡 FAQ

* **Как выбрать конкретный .torrent?**
  Укажи через `--torrent /app/torrents/yourfile.torrent` или через `TORRENT_PATH` в `.env`.

* **Что, если .torrent не найден?**
  Скрипт завершится с ошибкой и сообщением в лог.

* **Что, если нет пиров?**
  Если не появилось пиров за время, заданное в `--no-peers-timeout`, загрузка будет остановлена.

* **Можно ли использовать magnet-ссылки?**
  Сейчас только .torrent-файлы. Для поддержки magnet — создай issue или pull request.

---

## 👨‍💻 Автор и вклад

**Aleksandr Myasoed**
[GitHub](https://github.com/myasoedas)
Лицензия: MIT

PR, issue и предложения по доработкам приветствуются!
Хочешь интеграцию с Telegram, web-интерфейс или что-то ещё — создавай issue.

---

## ⭐️ Вклад

Fork, PR, issue — приветствуются!
