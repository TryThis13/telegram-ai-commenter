# Telegram AI Commenter

Сервис для безопасной автоматизации Telegram: нейрокомментинг ваших или разрешенных каналов и автопостинг разрешенного контента.

Проект работает через обычный Telegram-аккаунт по MTProto/Telethon. Первый запуск авторизует аккаунт по номеру телефона, коду Telegram и 2FA-паролю, если он включен. После этого сессия хранится локально в `telegram_ai_commenter\sessions\`.

## Что умеет

- `commenter` - следит за каналами, анализирует новые посты, генерирует короткий комментарий через OpenAI и публикует его в обсуждение поста.
- `grabber` - может переносить посты из разрешенного канала в ваш канал, при необходимости переписывая текст через ИИ.
- `dry_run` - тестовый режим без публикации.
- Фильтры по стоп-словам и обязательным словам.
- Лимиты частоты действий на аккаунт.
- Polling-режим: бот сам проверяет канал каждые несколько секунд, даже если Telegram realtime-событие не пришло.
- Логи действий и отдельный лог работы бота.
- Локальная веб-панель управления настройками.
- Фоновый запуск в Windows через Startup-ярлык.

Используйте только аккаунты и каналы, где у вас есть право на автоматизацию.

## Основные файлы

- `telegram_ai_commenter\main.py` - основной бот.
- `telegram_ai_commenter\config.json` - рабочие настройки.
- `telegram_ai_commenter\.env` - секретные ключи OpenAI и Telegram.
- `telegram_ai_commenter\manage.py` - локальная веб-панель.
- `telegram_ai_commenter\bot_control.py` - запуск, остановка и статус фонового бота.
- `telegram_ai_commenter\data\actions.csv` - журнал опубликованных действий.
- `telegram_ai_commenter\data\bot.log` - лог работы бота.
- `telegram_ai_commenter\data\bot_process.log` - вывод фонового процесса.

## Первый запуск

Откройте PowerShell и перейдите в папку проекта:

```powershell
cd "C:\Users\a-gid\Documents\New project"
```

Создайте виртуальное окружение и установите зависимости, если это еще не сделано:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r telegram_ai_commenter\requirements.txt
```

Если команда `python` не видна после установки Python, откройте новый PowerShell.

Создайте локальные файлы настроек:

```powershell
Copy-Item telegram_ai_commenter\.env.example telegram_ai_commenter\.env
Copy-Item telegram_ai_commenter\config.example.json telegram_ai_commenter\config.json
```

Откройте `.env`:

```powershell
notepad telegram_ai_commenter\.env
```

Заполните:

```env
OPENAI_API_KEY=sk-...
TG_API_ID_ACCOUNT_1=123456
TG_API_HASH_ACCOUNT_1=0123456789abcdef0123456789abcdef
```

Telegram `api_id` и `api_hash` берутся на сайте:

```text
https://my.telegram.org/apps
```

OpenAI API key создается здесь:

```text
https://platform.openai.com/api-keys
```

## Настройка каналов

Откройте конфиг:

```powershell
notepad telegram_ai_commenter\config.json
```

В блоке `commenter.source_channels` укажите каналы:

```json
"source_channels": [
  "@Apsny_Gid",
  "@vtoroy_kanal"
]
```

Важно:

- аккаунт должен видеть эти каналы;
- для приватного канала аккаунт должен быть добавлен в канал;
- для комментариев у канала должна быть включена группа обсуждений;
- аккаунт должен иметь право писать комментарии в обсуждениях.

## Проверка доступа к каналам

Команда ничего не публикует, только показывает, видит ли аккаунт каналы и последние посты:

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\main.py --config telegram_ai_commenter\config.json --check --check-limit 3
```

## Ручной тест комментария

Команда генерирует и публикует комментарий к последнему посту первого канала из `source_channels`:

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\main.py --config telegram_ai_commenter\config.json --comment-latest
```

Если в `config.json` стоит:

```json
"dry_run": true
```

то бот только покажет, что он бы написал, но не опубликует.

## Обычный запуск в PowerShell

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\main.py --config telegram_ai_commenter\config.json
```

Окно PowerShell должно оставаться открытым. Если закрыть окно или нажать `Ctrl + C`, бот остановится.

## Фоновый запуск

Запустить бота в фоне:

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\bot_control.py start
```

Проверить статус:

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\bot_control.py status
```

Остановить:

```powershell
.\.venv\Scripts\python.exe telegram_ai_commenter\bot_control.py stop
```

## Автозапуск Windows

Установить автозапуск при входе в Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_startup_shortcut.ps1
```

Удалить автозапуск:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_startup_shortcut.ps1
```

Автозапуск сделан через ярлык в папке Startup текущего пользователя. Это проще, чем Task Scheduler, потому что на некоторых Windows создание задач блокируется ошибкой `Access is denied`.

## Панель управления

Запустить локальную панель:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_panel.ps1
```

Открыть в браузере:

```text
http://127.0.0.1:8787
```

В панели можно:

- менять каналы;
- менять модель OpenAI;
- включать/выключать `dry_run`;
- менять лимиты;
- менять стиль комментариев;
- редактировать стоп-слова;
- включать и настраивать `grabber`;
- добавлять правила `source -> target` для автопостинга;
- выбирать, переписывать ли посты через ИИ;
- копировать картинки и медиа из исходных постов;
- добавлять 3 смысловых хештега к grabber-постам;
- добавлять в конец grabber-поста ссылку на канал, например `@Apsny_Gid`;
- включать добавление ссылки на источник;
- смотреть логи;
- проверять каналы;
- комментировать последний пост;
- запускать и останавливать фонового бота.

После изменения настроек нажмите “Сохранить настройки”, затем остановите и снова запустите бота, чтобы он перечитал `config.json`.

## Важные настройки config.json

- `safety.dry_run` - `true` для теста, `false` для реальной публикации.
- `safety.min_delay_per_account_seconds` - пауза между действиями одного аккаунта.
- `safety.max_actions_per_account_per_hour` - лимит действий в час.
- `commenter.source_channels` - каналы для отслеживания.
- `commenter.max_comment_length` - максимальная длина комментария.
- `commenter.style` - стиль комментария для нейросети.
- `commenter.poll_interval_seconds` - как часто проверять новые посты.
- `commenter.poll_recent_limit` - сколько последних постов смотреть при проверке.
- `commenter.process_existing_on_start` - комментировать ли старые посты при запуске. Обычно должно быть `false`.
- `commenter.filters.skip_if_contains` - стоп-слова.
- `commenter.filters.require_any_contains` - обязательные слова, если нужно.
- `openai.model` - модель OpenAI, сейчас используется `gpt-4o-mini`.

## Логи

Журнал действий:

```text
telegram_ai_commenter\data\actions.csv
```

Лог работы:

```text
telegram_ai_commenter\data\bot.log
```

Лог фонового процесса:

```text
telegram_ai_commenter\data\bot_process.log
```

## Частые проблемы

**Нет комментария после публикации поста**

Проверьте:

- бот запущен: `bot_control.py status`;
- канал указан правильно;
- аккаунт видит канал;
- у канала есть группа обсуждений;
- аккаунт может писать в обсуждения;
- в `bot.log` нет ошибок;
- OpenAI API-ключ работает и есть баланс.

**OpenAI insufficient_quota**

Нужно включить оплату или пополнить баланс в OpenAI Platform. Смена модели на более дешевую снижает расход, но не помогает при нулевой квоте.

**PowerShell не запускает ps1**

Используйте:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_panel.ps1
```

**Task Scheduler не установился**

Это нормально для некоторых систем без повышенных прав. Используйте Startup-ярлык через `install_startup_shortcut.ps1`.
