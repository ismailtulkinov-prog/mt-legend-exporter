# MT Legend Exporter

Мод для `Мир Танков`, который считывает из клиента текущую планку ранга `Легенда` в режиме `Натиск`, сохраняет последнее значение локально и при необходимости отправляет его на ваш сервер.

## Что умеет мод

- получает актуальную планку `Легенды` прямо из клиента;
- сохраняет локальный снимок в `latest_snapshot.json`;
- пишет `status.json` с последним состоянием опроса и отправки;
- умеет отправлять JSON на ваш сервер по `HTTP/HTTPS`;
- подходит для схемы, где мод стоит у нескольких игроков и сервер получает свежие данные, пока кто-то находится в игре.

## Что лежит в репозитории

- `dist/install/mods/mod_mt_legend_exporter.mtmod` - готовый файл мода для публикации и быстрой установки;
- `source/scripts/client/gui/mods/mod_mt_legend_exporter.py` - исходник мода;
- `configs/mt_legend_exporter/config.example.json` - пример конфига без секретов;
- `dist/mt_legend_exporter_install.zip` - готовый архив для установки;
- `server_example/receiver.py` - минимальный пример сервера-приемника;
- `tools/build_mtmod.py` - сборка `.mtmod`;
- `tools/build_mtmod.bat` - сборка в Windows.

## Что открыть на GitHub для разбора

Если репозиторий публикуется на GitHub, людям обычно нужны две точки входа:

- `source/scripts/client/gui/mods/mod_mt_legend_exporter.py` - основной исходный код мода;
- `res/meta/MTLegendExporter.xml` - метаданные и версия мода;
- `dist/install/mods/mod_mt_legend_exporter.mtmod` - собранный мод;
- `dist/mt_legend_exporter_install.zip` - готовый install-архив.

То есть в репозитории лежит и исходник для чтения, и готовая собранная версия мода.

## Быстрый старт

1. Скачайте `dist/mt_legend_exporter_install.zip`.
2. Распакуйте содержимое в папку клиента `Мир Танков`.
3. Откройте `mods/configs/mt_legend_exporter/config.json`.
4. Заполните `endpoint`, `auth_token` и `client_label`.
5. Запустите игру и зайдите в клиент.

После запуска мод пишет:

- `mods/configs/mt_legend_exporter/latest_snapshot.json`
- `mods/configs/mt_legend_exporter/status.json`
- `mods/configs/mt_legend_exporter/exporter.log`

Если `endpoint` оставить пустым, мод ничего не отправляет на сервер, но продолжает сохранять локальный `latest_snapshot.json`. Это удобно для первой проверки.

## Пример config.json

```json
{
  "active_poll_interval_sec": 5,
  "auth_token": "replace-with-your-own-random-token",
  "client_label": "test-client",
  "debug": true,
  "enabled": true,
  "endpoint": "https://legend.example.com/mt/legend/ingest",
  "max_log_size_kb": 512,
  "poll_interval_sec": 300,
  "send_retry_base_delay_sec": 15,
  "send_retry_max_delay_sec": 300,
  "request_stall_timeout_sec": 8,
  "request_timeout_sec": 10,
  "ui_hook_retry_interval_sec": 30,
  "send_only_on_change": true,
  "send_player_name": false
}
```

Самые важные поля:

- `endpoint` - адрес вашего сервера, который принимает данные;
- `auth_token` - общий секретный токен между модом и сервером;
- `client_label` - имя клиента, например `player_1`;
- `poll_interval_sec` - обычный интервал опроса;
- `active_poll_interval_sec` - частый опрос в активном состоянии.
- `ui_hook_retry_interval_sec` - короткий интервал повтора, пока UI-хуки `Натиска` еще не установились.
- `send_retry_base_delay_sec` - через сколько секунд пробовать повторную отправку после первой сетевой ошибки.
- `send_retry_max_delay_sec` - максимальная пауза между повторными попытками отправки.

Для публичной раздачи мода не держите в шаблоне реальный IP и реальный токен.
Безопаснее использовать домен под `Cloudflare`, `HTTPS` и отдельные токены для клиентов.

## Как мод реально обновляет данные

- После входа в игру мод стартует не мгновенно, а с задержкой, затем делает первый опрос.
- Если UI-модули `Натиска` еще не загружены, мод теперь не ждет полные `poll_interval_sec`, а перепроверяет установку UI-хуков чаще, по `ui_hook_retry_interval_sec`.
- После установки UI-хуков мод продолжает обычный фоновый опрос по `poll_interval_sec`.
- Если значение порога не изменилось, мод все равно продолжает опрос, но при `send_only_on_change=true` повторно не отправляет одинаковый payload на сервер.
- Пустой `endpoint` теперь действительно означает режим "только локальный snapshot", без фоновых попыток отправки по сети.
- При сетевых ошибках мод теперь не спамит сервер повторными попытками, а уходит в мягкий `backoff`.
- Последний статус опроса и сети сохраняется в `status.json`.

## Пример JSON, который отправляет мод

```json
{
  "account_dbid": 123456789,
  "client_label": "player_1",
  "elite_rank_percent": 10,
  "game": "Mir Tankov",
  "last_recalculation_ts": 1773791100,
  "legend_position_threshold": 250,
  "legend_threshold": 1850,
  "mod_id": "mt_legend_exporter",
  "mod_version": "0.1.11",
  "player_is_elite": false,
  "player_rating": 1724,
  "polled_at_ts": 1773791220,
  "publisher": "Lesta",
  "season_number": 1
}
```

## Сборка

Для сборки нужен `Python 2.7`.

В Windows:

1. Установите `Python 2.7`.
2. Запустите `tools/build_mtmod.bat`.

Вручную:

```bash
python2.7 tools/build_mtmod.py
```

После сборки появятся:

- `dist/install/mods/mod_mt_legend_exporter.mtmod`
- `dist/install/mods/configs/mt_legend_exporter/config.json`
- `dist/mt_legend_exporter_install.zip`

## Пример сервера

В папке `server_example/` лежит простой приемник, который:

- принимает `POST /mt/legend/ingest`;
- проверяет заголовок `Authorization: Bearer <token>`;
- сохраняет последнее значение и историю.

Запуск:

```bash
MT_EXPORTER_TOKEN=change-me python3 server_example/receiver.py
```

## Что важно

- мод не берет данные с сайта, он получает их из клиента;
- если сезон не активен, полезных значений может не быть;
- рабочие токены и адреса сервера в репозиторий не добавляйте.
