import csv
import html
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
CONFIG_PATH = BASE_DIR / "config.json"
ACTIONS_PATH = BASE_DIR / "data" / "actions.csv"
BOT_LOG_PATH = BASE_DIR / "data" / "bot.log"
MAX_GRABBER_RULES = 5


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def multiline_to_list(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def list_to_multiline(value: list[str]) -> str:
    return "\n".join(value or [])


def bool_select(name: str, value: bool, true_label: str, false_label: str) -> str:
    true_selected = "selected" if value else ""
    false_selected = "" if value else "selected"
    return (
        f'<select name="{html.escape(name)}">'
        f'<option value="true" {true_selected}>true - {html.escape(true_label)}</option>'
        f'<option value="false" {false_selected}>false - {html.escape(false_label)}</option>'
        "</select>"
    )


def run_command(args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, output.strip()
    except Exception as exc:
        return 1, str(exc)


def startup_shortcut_path() -> Path:
    appdata = Path.home() / "AppData" / "Roaming"
    return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "AgidTelegramCommenter.lnk"


def bot_status() -> str:
    python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    code, output = run_command([str(python), str(BASE_DIR / "bot_control.py"), "status"], timeout=10)
    if code != 0:
        return f"Не удалось получить статус: {output}"
    startup = "установлен" if startup_shortcut_path().exists() else "не установлен"
    return f"Bot process: {output}\nStartup shortcut: {startup}\nShortcut path: {startup_shortcut_path()}"


def read_tail(path: Path, lines: int = 80) -> str:
    if not path.exists():
        return ""
    data = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(data[-lines:])


def read_actions(limit: int = 20) -> list[dict[str, str]]:
    if not ACTIONS_PATH.exists():
        return []
    with ACTIONS_PATH.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return rows[-limit:]


def page(title: str, body: str, notice: str = "") -> bytes:
    notice_html = f"<div class='notice'>{html.escape(notice)}</div>" if notice else ""
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f6f7f8;
      --panel: #ffffff;
      --text: #182026;
      --muted: #68727d;
      --line: #d9dee3;
      --accent: #1f7a8c;
      --danger: #a23b3b;
    }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 Arial, sans-serif; }}
    header {{
      background: #fff; border-bottom: 1px solid var(--line); padding: 14px 22px;
      display: flex; align-items: center; justify-content: space-between; gap: 16px;
    }}
    main {{ max-width: 1220px; margin: 22px auto 60px; padding: 0 18px; display: grid; grid-template-columns: 1fr 360px; gap: 18px; }}
    section {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; margin-bottom: 18px; }}
    h1 {{ font-size: 18px; margin: 0; }}
    h2 {{ font-size: 16px; margin: 0 0 14px; }}
    h3 {{ font-size: 14px; margin: 18px 0 8px; }}
    label {{ display: block; margin: 12px 0 6px; font-weight: 700; }}
    input[type=text], input[type=number], textarea, select {{
      width: 100%; box-sizing: border-box; border: 1px solid var(--line); border-radius: 6px;
      padding: 9px 10px; font: inherit; background: #fff;
    }}
    textarea {{ min-height: 80px; resize: vertical; }}
    .row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
    .two {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }}
    .rule {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; margin-top: 12px; background: #fbfcfd; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }}
    button, .button {{
      border: 0; border-radius: 6px; padding: 9px 12px; background: var(--accent); color: #fff;
      font: inherit; cursor: pointer; text-decoration: none; display: inline-block;
    }}
    button.secondary {{ background: #44515c; }}
    button.danger {{ background: var(--danger); }}
    pre {{ white-space: pre-wrap; word-break: break-word; background: #f0f3f5; border-radius: 6px; padding: 12px; max-height: 360px; overflow: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; }}
    .notice {{ margin: 14px 22px 0; background: #e7f4f6; border: 1px solid #b8dfe6; padding: 10px 12px; border-radius: 6px; }}
    .hint {{ color: var(--muted); font-size: 12px; margin-top: 6px; }}
    @media (max-width: 900px) {{ main {{ grid-template-columns: 1fr; }} .row, .two {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(title)}</h1>
    <div><a class="button" href="/">Обновить</a></div>
  </header>
  {notice_html}
  {body}
</body>
</html>""".encode("utf-8")


def render_grabber_rules(grabber: dict) -> str:
    rules = list(grabber.get("rules", []))
    while len(rules) < MAX_GRABBER_RULES:
        rules.append({
            "name": "",
            "source": "",
            "target": "",
            "enabled": False,
            "rewrite_with_ai": True,
            "add_source_link": False,
            "copy_media": True,
            "filters": {"min_text_length": 20, "skip_if_contains": [], "require_any_contains": []},
        })

    html_parts = []
    for index, rule in enumerate(rules[:MAX_GRABBER_RULES]):
        filters = rule.get("filters", {})
        html_parts.append(f"""
        <div class="rule">
          <h3>Правило {index + 1}</h3>
          <div class="row">
            <div>
              <label>Включено</label>
              {bool_select(f"grabber_rule_{index}_enabled", bool(rule.get("enabled", False)), "активно", "выключено")}
            </div>
            <div>
              <label>Название правила</label>
              <input type="text" name="grabber_rule_{index}_name" value="{html.escape(rule.get("name", ""))}">
            </div>
            <div>
              <label>Мин. длина текста</label>
              <input type="number" name="grabber_rule_{index}_min_text_length" value="{int(filters.get("min_text_length", 20))}">
            </div>
          </div>

          <div class="two">
            <div>
              <label>Источник</label>
              <input type="text" name="grabber_rule_{index}_source" value="{html.escape(rule.get("source", ""))}" placeholder="@source_channel">
            </div>
            <div>
              <label>Куда публиковать</label>
              <input type="text" name="grabber_rule_{index}_target" value="{html.escape(rule.get("target", ""))}" placeholder="@my_target_channel">
            </div>
          </div>

          <div class="two">
            <div>
              <label>Переписывать через ИИ</label>
              {bool_select(f"grabber_rule_{index}_rewrite_with_ai", bool(rule.get("rewrite_with_ai", True)), "переписывать", "копировать как есть")}
            </div>
            <div>
              <label>Добавлять ссылку на источник</label>
              {bool_select(f"grabber_rule_{index}_add_source_link", bool(rule.get("add_source_link", False)), "добавлять", "не добавлять")}
            </div>
          </div>

          <div class="two">
            <div>
              <label>Копировать картинки и медиа</label>
              {bool_select(f"grabber_rule_{index}_copy_media", bool(rule.get("copy_media", True)), "копировать медиа", "только текст")}
            </div>
            <div>
              <label>Медиа-посты без текста</label>
              <input type="text" value="переносятся, если копирование медиа включено" disabled>
            </div>
          </div>

          <label>Стоп-слова для этого правила</label>
          <textarea name="grabber_rule_{index}_skip_if_contains">{html.escape(list_to_multiline(filters.get("skip_if_contains", [])))}</textarea>

          <label>Обязательные слова для этого правила</label>
          <textarea name="grabber_rule_{index}_require_any_contains">{html.escape(list_to_multiline(filters.get("require_any_contains", [])))}</textarea>
        </div>
        """)
    return "\n".join(html_parts)


def render_index(notice: str = "") -> bytes:
    config = load_config()
    commenter = config.setdefault("commenter", {})
    safety = config.setdefault("safety", {})
    filters = commenter.setdefault("filters", {})
    grabber = config.setdefault("grabber", {"enabled": False, "rules": []})
    openai_config = config.setdefault("openai", {})
    actions = read_actions()

    actions_rows = ""
    for row in reversed(actions):
        actions_rows += "<tr>" + "".join(
            f"<td>{html.escape(str(row.get(column, ''))[:300])}</td>"
            for column in ["timestamp", "module", "account", "source", "post_id", "status", "text"]
        ) + "</tr>"
    if not actions_rows:
        actions_rows = "<tr><td colspan='7'>Пока нет действий</td></tr>"

    body = f"""
<main>
  <div>
    <form method="post" action="/save">
      <section>
        <h2>Комментер</h2>
        <label>Каналы для отслеживания</label>
        <textarea name="source_channels">{html.escape(list_to_multiline(commenter.get("source_channels", [])))}</textarea>
        <div class="hint">Один канал на строку, например @Apsny_Gid.</div>

        <div class="row">
          <div>
            <label>Dry run</label>
            {bool_select("dry_run", bool(safety.get("dry_run", True)), "только лог", "публиковать")}
          </div>
          <div>
            <label>Модель OpenAI</label>
            <input type="text" name="model" value="{html.escape(openai_config.get("model", "gpt-4o-mini"))}">
          </div>
          <div>
            <label>Макс. длина комментария</label>
            <input type="number" name="max_comment_length" value="{int(commenter.get("max_comment_length", 240))}">
          </div>
        </div>

        <label>Стиль комментариев</label>
        <textarea name="style">{html.escape(commenter.get("style", ""))}</textarea>

        <div class="row">
          <div>
            <label>Пауза между действиями, сек.</label>
            <input type="number" name="min_delay" value="{int(safety.get("min_delay_per_account_seconds", 180))}">
          </div>
          <div>
            <label>Действий в час</label>
            <input type="number" name="max_hour" value="{int(safety.get("max_actions_per_account_per_hour", 12))}">
          </div>
          <div>
            <label>Опрос канала, сек.</label>
            <input type="number" name="poll_interval" value="{int(commenter.get("poll_interval_seconds", 20))}">
          </div>
        </div>

        <label>Стоп-слова комментера</label>
        <textarea name="skip_if_contains">{html.escape(list_to_multiline(filters.get("skip_if_contains", [])))}</textarea>

        <label>Обязательные слова комментера</label>
        <textarea name="require_any_contains">{html.escape(list_to_multiline(filters.get("require_any_contains", [])))}</textarea>
      </section>

      <section>
        <h2>Grabber / автопостинг</h2>
        <div class="row">
          <div>
            <label>Grabber включен</label>
            {bool_select("grabber_enabled", bool(grabber.get("enabled", False)), "включен", "выключен")}
          </div>
          <div>
            <label>Антидубль</label>
            {bool_select("grabber_dedupe_enabled", bool(grabber.get("dedupe_enabled", True)), "включен", "выключен")}
          </div>
          <div>
            <label>Порог похожести</label>
            <input type="text" name="grabber_dedupe_similarity_threshold" value="{html.escape(str(grabber.get("dedupe_similarity_threshold", 0.35)))}">
          </div>
        </div>
        <div class="row">
          <div>
            <label>Окно памяти дублей</label>
            <input type="number" name="grabber_dedupe_window" value="{int(grabber.get("dedupe_window", 500))}">
          </div>
          <div>
            <label>Количество правил</label>
            <input type="number" value="{MAX_GRABBER_RULES}" disabled>
          </div>
          <div>
            <label>Общий лимит</label>
            <input type="text" value="использует общий лимит действий" disabled>
          </div>
        </div>
        <div class="row">
          <div>
            <label>Добавлять хештеги</label>
            {bool_select("grabber_add_hashtags", bool(grabber.get("add_hashtags", True)), "добавлять", "не добавлять")}
          </div>
          <div>
            <label>Количество хештегов</label>
            <input type="number" name="grabber_hashtag_count" value="{int(grabber.get("hashtag_count", 3))}">
          </div>
          <div>
            <label>Канал в конце поста</label>
            <input type="text" name="grabber_footer_channel" value="{html.escape(grabber.get("footer_channel", "@Apsny_Gid"))}">
          </div>
        </div>
        <div class="row">
          <div>
            <label>Фильтр рекламы</label>
            {bool_select("grabber_ad_filter_enabled", bool(grabber.get("ad_filter_enabled", True)), "включен", "выключен")}
          </div>
          <div>
            <label>Блокировать ссылки</label>
            {bool_select("grabber_block_external_links", bool(grabber.get("block_external_links", True)), "блокировать", "разрешать")}
          </div>
          <div>
            <label>Блокировать телефоны</label>
            {bool_select("grabber_block_phone_numbers", bool(grabber.get("block_phone_numbers", True)), "блокировать", "разрешать")}
          </div>
        </div>
        <div class="row">
          <div>
            <label>Блокировать @аккаунты</label>
            {bool_select("grabber_block_external_accounts", bool(grabber.get("block_external_accounts", True)), "блокировать сторонние", "разрешать")}
          </div>
          <div>
            <label>Разрешенные домены</label>
            <textarea name="grabber_allowed_domains">{html.escape(list_to_multiline(grabber.get("allowed_domains", [])))}</textarea>
          </div>
          <div>
            <label>Разрешенные аккаунты</label>
            <textarea name="grabber_allowed_accounts">{html.escape(list_to_multiline(grabber.get("allowed_accounts", [])))}</textarea>
          </div>
        </div>
        <div class="hint">Фильтр рекламы пропускает посты с разрешенными доменами и аккаунтами, но не репостит публикации со сторонними ссылками, телефонами или чужими @аккаунтами.</div>
        <div class="hint">Если включено, grabber добавит смысловые хештеги и строку “Больше об Абхазии: @Apsny_Gid” в конец публикации.</div>
        <div class="hint">Антидубль сравнивает похожесть текстов по фрагментам слов. Чем выше порог, тем меньше постов будет считаться дублями. Обычно 0.35-0.60.</div>
        <div class="hint">Источник должен быть вашим или разрешенным каналом. Аккаунт должен иметь право публиковать в целевой канал.</div>
        {render_grabber_rules(grabber)}
      </section>

      <section>
        <div class="actions">
          <button type="submit">Сохранить все настройки</button>
        </div>
      </section>
    </form>

    <section>
      <h2>Последние действия</h2>
      <table>
        <thead><tr><th>time</th><th>module</th><th>account</th><th>source</th><th>post</th><th>status</th><th>text</th></tr></thead>
        <tbody>{actions_rows}</tbody>
      </table>
    </section>
  </div>

  <aside>
    <section>
      <h2>Управление</h2>
      <form method="post" action="/bot/start" class="actions"><button>Запустить бота в фоне</button></form>
      <form method="post" action="/bot/stop" class="actions"><button class="danger">Остановить бота</button></form>
      <form method="post" action="/check" class="actions"><button class="secondary">Проверить каналы</button></form>
      <form method="post" action="/comment-latest" class="actions"><button class="secondary">Комментировать последний пост</button></form>
      <div class="hint">После сохранения настроек остановите и снова запустите бота, чтобы он перечитал config.json.</div>
    </section>

    <section>
      <h2>Статус фонового режима</h2>
      <pre>{html.escape(bot_status())}</pre>
    </section>

    <section>
      <h2>Лог бота</h2>
      <pre>{html.escape(read_tail(BOT_LOG_PATH, 80))}</pre>
    </section>
  </aside>
</main>
"""
    return page("A-Gid Telegram Commenter", body, notice)


def save_from_form(data: dict[str, list[str]]) -> None:
    config = load_config()
    commenter = config.setdefault("commenter", {})
    safety = config.setdefault("safety", {})
    filters = commenter.setdefault("filters", {})
    grabber = config.setdefault("grabber", {})
    openai_config = config.setdefault("openai", {})

    commenter["source_channels"] = multiline_to_list(data.get("source_channels", [""])[0])
    commenter["style"] = data.get("style", [""])[0]
    commenter["max_comment_length"] = int(data.get("max_comment_length", ["240"])[0] or 240)
    commenter["poll_interval_seconds"] = int(data.get("poll_interval", ["20"])[0] or 20)
    safety["dry_run"] = data.get("dry_run", ["true"])[0] == "true"
    safety["min_delay_per_account_seconds"] = int(data.get("min_delay", ["180"])[0] or 180)
    safety["max_actions_per_account_per_hour"] = int(data.get("max_hour", ["12"])[0] or 12)
    filters["skip_if_contains"] = multiline_to_list(data.get("skip_if_contains", [""])[0])
    filters["require_any_contains"] = multiline_to_list(data.get("require_any_contains", [""])[0])
    openai_config["model"] = data.get("model", ["gpt-4o-mini"])[0]

    grabber["enabled"] = data.get("grabber_enabled", ["false"])[0] == "true"
    grabber["dedupe_enabled"] = data.get("grabber_dedupe_enabled", ["true"])[0] == "true"
    grabber["dedupe_similarity_threshold"] = float(
        data.get("grabber_dedupe_similarity_threshold", ["0.35"])[0] or 0.35
    )
    grabber["dedupe_window"] = int(data.get("grabber_dedupe_window", ["500"])[0] or 500)
    grabber["ad_filter_enabled"] = data.get("grabber_ad_filter_enabled", ["true"])[0] == "true"
    grabber["block_external_links"] = data.get("grabber_block_external_links", ["true"])[0] == "true"
    grabber["block_phone_numbers"] = data.get("grabber_block_phone_numbers", ["true"])[0] == "true"
    grabber["block_external_accounts"] = data.get("grabber_block_external_accounts", ["true"])[0] == "true"
    grabber["allowed_domains"] = multiline_to_list(data.get("grabber_allowed_domains", [""])[0])
    grabber["allowed_accounts"] = multiline_to_list(data.get("grabber_allowed_accounts", [""])[0])
    grabber["add_hashtags"] = data.get("grabber_add_hashtags", ["true"])[0] == "true"
    grabber["hashtag_count"] = int(data.get("grabber_hashtag_count", ["3"])[0] or 3)
    grabber["footer_channel"] = data.get("grabber_footer_channel", ["@Apsny_Gid"])[0].strip()
    rules = []
    for index in range(MAX_GRABBER_RULES):
        name = data.get(f"grabber_rule_{index}_name", [""])[0].strip()
        source = data.get(f"grabber_rule_{index}_source", [""])[0].strip()
        target = data.get(f"grabber_rule_{index}_target", [""])[0].strip()
        enabled = data.get(f"grabber_rule_{index}_enabled", ["false"])[0] == "true"

        if not any([name, source, target, enabled]):
            continue

        rules.append({
            "name": name or f"grabber_rule_{index + 1}",
            "source": source,
            "target": target,
            "enabled": enabled,
            "rewrite_with_ai": data.get(f"grabber_rule_{index}_rewrite_with_ai", ["true"])[0] == "true",
            "add_source_link": data.get(f"grabber_rule_{index}_add_source_link", ["false"])[0] == "true",
            "copy_media": data.get(f"grabber_rule_{index}_copy_media", ["true"])[0] == "true",
            "filters": {
                "min_text_length": int(data.get(f"grabber_rule_{index}_min_text_length", ["20"])[0] or 20),
                "skip_if_contains": multiline_to_list(data.get(f"grabber_rule_{index}_skip_if_contains", [""])[0]),
                "require_any_contains": multiline_to_list(data.get(f"grabber_rule_{index}_require_any_contains", [""])[0]),
            },
        })
    grabber["rules"] = rules
    save_config(config)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path != "/":
            self.send_error(404)
            return
        self.respond(render_index())

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        data = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))

        if parsed.path == "/save":
            save_from_form(data)
            self.respond(render_index("Настройки сохранены. Перезапустите фонового бота, чтобы применить изменения."))
            return

        python = ROOT_DIR / ".venv" / "Scripts" / "python.exe"

        if parsed.path == "/bot/start":
            code, output = run_command([str(python), str(BASE_DIR / "bot_control.py"), "start"])
            self.respond(render_index(f"Запуск бота: код {code}. {output}"))
            return

        if parsed.path == "/bot/stop":
            code, output = run_command([str(python), str(BASE_DIR / "bot_control.py"), "stop"])
            self.respond(render_index(f"Остановка бота: код {code}. {output}"))
            return

        if parsed.path == "/check":
            code, output = run_command([
                str(python), str(BASE_DIR / "main.py"), "--config", str(CONFIG_PATH), "--check", "--check-limit", "2"
            ], timeout=120)
            self.respond(render_index(f"Проверка каналов: код {code}\n{output}"))
            return

        if parsed.path == "/comment-latest":
            code, output = run_command([
                str(python), str(BASE_DIR / "main.py"), "--config", str(CONFIG_PATH), "--comment-latest"
            ], timeout=180)
            self.respond(render_index(f"Комментарий последнего поста: код {code}\n{output}"))
            return

        self.send_error(404)

    def respond(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = "127.0.0.1"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Management UI: http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
