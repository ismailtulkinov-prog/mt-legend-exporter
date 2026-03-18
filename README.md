# MT Legend Exporter

Мод для `Мир Танков`, который считывает из клиента текущую планку ранга `Легенда` в режиме `Натиск`, сохраняет последнее значение локально и при необходимости отправляет его на ваш сервер.

## Что умеет мод

- получает актуальную планку `Легенды` прямо из клиента;
- сохраняет локальный снимок в `latest_snapshot.json`;
- умеет отправлять JSON на ваш сервер по `HTTP`;
- подходит для схемы, где мод стоит у нескольких игроков и сервер получает свежие данные, пока кто-то находится в игре.

## Что лежит в репозитории

- `source/scripts/client/gui/mods/mod_mt_legend_exporter.py` - исходник мода;
- `configs/mt_legend_exporter/config.example.json` - пример конфига без секретов;
- `dist/mt_legend_exporter_install.zip` - готовый архив для установки;
- `server_example/receiver.py` - минимальный пример сервера-приемника;
- `tools/build_mtmod.py` - сборка `.mtmod`;
- `tools/build_mtmod.bat` - сборка в Windows.

## Быстрый старт

1. Скачайте `dist/mt_legend_exporter_install.zip`.
2. Распакуйте содержимое в папку клиента `Мир Танков`.
3. Откройте `mods/configs/mt_legend_exporter/config.json`.
4. Заполните `endpoint`, `auth_token` и `client_label`.
5. Запустите игру и зайдите в клиент.

После запуска мод пишет:

- `mods/configs/mt_legend_exporter/latest_snapshot.json`
- `mods/configs/mt_legend_exporter/exporter.log`

Если `endpoint` оставить пустым, мод ничего не отправляет на сервер, но продолжает сохранять локальный `latest_snapshot.json`. Это удобно для первой проверки.

## Пример config.json

```json
{
  "active_poll_interval_sec": 5,
  "auth_token": "2ed8bc656c66a03192899ecbcf4a3821",
  "client_label": "test-client",
  "debug": true,
  "enabled": true,
  "endpoint": "http://77.91.77.218:18787/mt/legend/ingest",
  "max_log_size_kb": 512,
  "poll_interval_sec": 300,
  "request_stall_timeout_sec": 8,
  "request_timeout_sec": 10,
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
  "mod_version": "0.1.9",
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
