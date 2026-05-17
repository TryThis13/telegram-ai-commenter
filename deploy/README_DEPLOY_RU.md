# Деплой Telegram AI Commenter на VPS

Эта папка содержит готовые Linux-скрипты для переноса бота на Ubuntu VPS.

Рекомендуемый путь установки на сервере:

```text
/opt/agid-telegram-bot
```

## Что переносить

Нужно перенести папку проекта с файлами:

```text
telegram_ai_commenter/
deploy/
```

На сервере также должны быть:

```text
telegram_ai_commenter/.env
telegram_ai_commenter/config.json
telegram_ai_commenter/sessions/
```

Важно: `.env` содержит секреты OpenAI и Telegram. Не публикуйте его в GitHub и не отправляйте в чат.

## Быстрый порядок действий

На Windows из папки проекта можно сначала создать архив:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\make_release_zip.ps1
```

Архив появится в:

```text
dist\agid-telegram-bot-release.zip
```

Загрузить архив на сервер:

```powershell
scp .\dist\agid-telegram-bot-release.zip root@IP_СЕРВЕРА:/opt/
```

На сервере:

```bash
cd /opt
apt update
apt install -y unzip
unzip agid-telegram-bot-release.zip -d agid-telegram-bot
cd /opt/agid-telegram-bot
bash deploy/install.sh
```

## Настроить секреты

Если `.env` и `sessions/` не переносились в архиве, создайте их вручную.

```bash
cp telegram_ai_commenter/.env.example telegram_ai_commenter/.env
nano telegram_ai_commenter/.env
```

Заполните:

```env
OPENAI_API_KEY=...
TG_API_ID_ACCOUNT_1=...
TG_API_HASH_ACCOUNT_1=...
```

Если папка `sessions/` не перенесена, при первом запуске бот попросит номер Telegram, код и 2FA-пароль.

## Проверка

```bash
bash deploy/check.sh
```

## Запуск вручную

```bash
bash deploy/start.sh
```

## Установка systemd-сервисов

Бот:

```bash
bash deploy/install_bot_service.sh
```

Панель управления:

```bash
bash deploy/install_panel_service.sh
```

После установки:

```bash
systemctl status agid-telegram-bot
systemctl status agid-telegram-panel
```

Логи:

```bash
bash deploy/logs.sh
bash deploy/panel_logs.sh
```

## Панель управления

Панель слушает только локальный адрес VPS:

```text
127.0.0.1:8787
```

Чтобы открыть ее на своем компьютере, используйте SSH-туннель:

```powershell
ssh -L 8787:127.0.0.1:8787 root@IP_СЕРВЕРА
```

После этого откройте в браузере на своем ПК:

```text
http://127.0.0.1:8787
```

## Остановка

```bash
bash deploy/stop.sh
systemctl stop agid-telegram-bot
systemctl stop agid-telegram-panel
```

## Обновление

1. Остановить сервис:

```bash
systemctl stop agid-telegram-bot
systemctl stop agid-telegram-panel
```

2. Заменить файлы проекта.

3. Установить зависимости:

```bash
bash deploy/install.sh
```

4. Запустить:

```bash
systemctl start agid-telegram-bot
systemctl start agid-telegram-panel
```
