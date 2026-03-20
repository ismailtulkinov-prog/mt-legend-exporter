# MT Legend Exporter

Мод для `Мир Танков`.

## Файлы в репозитории

- `dist/install/mods/mod_mt_legend_exporter.mtmod` - готовый файл мода.
- `dist/mt_legend_exporter_install.zip` - готовый архив для установки.
- `source/scripts/client/gui/mods/mod_mt_legend_exporter.py` - исходный код мода.
- `res/meta/MTLegendExporter.xml` - метаданные и версия мода.
- `configs/mt_legend_exporter/config.example.json` - пример конфига.
- `tools/build_mtmod.py` - сборка `.mtmod`.
- `tools/build_mtmod.bat` - сборка `.mtmod` в Windows.

## Установка `.mtmod`

1. Скачать файл `dist/install/mods/mod_mt_legend_exporter.mtmod`.
2. Открыть папку клиента `Мир Танков`.
3. Скопировать файл в папку `mods/`.

Итоговый путь должен выглядеть так:

```text
<папка_игры>/mods/mod_mt_legend_exporter.mtmod
```

## Установка конфига

Если нужен конфиг:

1. Взять `configs/mt_legend_exporter/config.example.json`.
2. Скопировать его в папку:

```text
<папка_игры>/mods/configs/mt_legend_exporter/config.json
```

3. При необходимости отредактировать `endpoint`, `auth_token` и `client_label`.
