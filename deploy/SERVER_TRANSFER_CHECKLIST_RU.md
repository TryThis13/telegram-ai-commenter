# Перенос бота на сервер

Куда ставить на сервере:

```bash
/opt/agid-telegram-bot
```

## Что уже подготовлено

- Код бота: `telegram_ai_commenter/main.py`
- Панель управления: `telegram_ai_commenter/manage.py`
- Рабочие настройки: `telegram_ai_commenter/config.json`
- Linux-скрипты и systemd-сервисы: `deploy/`
- Фильтр рекламы для граббера включен:
  - блокирует сторонние ссылки;
  - блокирует номера телефонов;
  - блокирует сторонние `@аккаунты` и `t.me/...`;
  - разрешает свой аккаунт `@Apsny_Gid`.

## Что не входит в релизный архив

Эти файлы специально не кладутся в архив, потому что содержат секреты или локальное состояние:

- `telegram_ai_commenter/.env`
- `telegram_ai_commenter/sessions/`
- `telegram_ai_commenter/data/`
- `telegram_ai_commenter/__pycache__/`

Если хотите перенести уже авторизованную Telegram-сессию без повторного входа, скопируйте `telegram_ai_commenter/sessions/` на сервер отдельно и храните ее как пароль.

## Команды на Windows

Создать архив:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\make_release_zip.ps1
```

Архив будет здесь:

```text
dist\agid-telegram-bot-release.zip
```

Отправить на сервер:

```powershell
scp .\dist\agid-telegram-bot-release.zip root@SERVER_IP:/opt/
```

Если переносите сессию отдельно:

```powershell
scp -r .\telegram_ai_commenter\sessions root@SERVER_IP:/opt/agid-telegram-bot/telegram_ai_commenter/
```

## Команды на сервере

Распаковать и установить зависимости:

```bash
cd /opt
apt update
apt install -y unzip
rm -rf /opt/agid-telegram-bot
unzip /opt/agid-telegram-bot-release.zip -d /opt/agid-telegram-bot
cd /opt/agid-telegram-bot
bash deploy/install.sh
```

Заполнить секреты:

```bash
nano telegram_ai_commenter/.env
```

Нужны значения:

```env
OPENAI_API_KEY=...
TG_API_ID_ACCOUNT_1=...
TG_API_HASH_ACCOUNT_1=...
```

Если сервер не подключается к Telegram напрямую и проверка показывает `TimeoutError`, добавьте SOCKS5-прокси:

```env
TG_PROXY_TYPE=socks5
TG_PROXY_HOST=proxy.example.com
TG_PROXY_PORT=1080
TG_PROXY_USERNAME=
TG_PROXY_PASSWORD=
```

Если у прокси есть логин и пароль, заполните `TG_PROXY_USERNAME` и `TG_PROXY_PASSWORD`. Если авторизации нет, оставьте их пустыми.

Проверить доступ к каналам без публикации:

```bash
bash deploy/check.sh
```

## Первый вход в Telegram

Если `sessions/` не перенесена, первый запуск должен быть ручным, чтобы ввести телефон, код Telegram и 2FA-пароль:

```bash
bash deploy/start.sh
```

После успешной авторизации остановите ручной процесс `Ctrl+C` и запускайте через systemd.

## Запуск через systemd

```bash
bash deploy/install_bot_service.sh
bash deploy/install_panel_service.sh
```

Статус:

```bash
systemctl status agid-telegram-bot --no-pager
systemctl status agid-telegram-panel --no-pager
```

Логи:

```bash
bash deploy/logs.sh
bash deploy/panel_logs.sh
```

## Панель управления

Панель слушает локально на сервере:

```text
127.0.0.1:8787
```

Открыть с компьютера через SSH-туннель:

```powershell
ssh -L 8787:127.0.0.1:8787 root@SERVER_IP
```

Потом открыть:

```text
http://127.0.0.1:8787
```

После изменения настроек в панели перезапустите бота:

```bash
systemctl restart agid-telegram-bot
```
