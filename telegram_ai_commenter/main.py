import argparse
import asyncio
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from openai import AsyncOpenAI
try:
    import socks
except ImportError:  # pragma: no cover - optional until proxy env is used
    socks = None
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.custom.message import Message


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"
LOG_PATH = DATA_DIR / "actions.csv"
BOT_LOG_PATH = DATA_DIR / "bot.log"


@dataclass
class AccountConfig:
    name: str
    api_id_env: str
    api_hash_env: str
    session: str
    enabled: bool = True


@dataclass
class FiltersConfig:
    min_text_length: int = 20
    skip_if_contains: list[str] = field(default_factory=list)
    require_any_contains: list[str] = field(default_factory=list)


@dataclass
class SafetyConfig:
    dry_run: bool = True
    min_delay_per_account_seconds: int = 180
    max_actions_per_account_per_hour: int = 12


@dataclass
class CommenterConfig:
    enabled: bool = True
    source_channels: list[str] = field(default_factory=list)
    max_comment_length: int = 240
    language: str = "same_as_post"
    style: str = "natural, short, relevant, no links, no hashtags"
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    poll_interval_seconds: int = 20
    poll_recent_limit: int = 5
    process_existing_on_start: bool = False


@dataclass
class GrabberRuleConfig:
    name: str
    source: str
    target: str
    enabled: bool = True
    rewrite_with_ai: bool = True
    add_source_link: bool = False
    copy_media: bool = True
    filters: FiltersConfig = field(default_factory=FiltersConfig)


@dataclass
class GrabberConfig:
    enabled: bool = False
    rules: list[GrabberRuleConfig] = field(default_factory=list)
    dedupe_enabled: bool = True
    dedupe_similarity_threshold: float = 0.35
    dedupe_window: int = 500
    add_hashtags: bool = True
    hashtag_count: int = 3
    footer_channel: str = "@Apsny_Gid"
    ad_filter_enabled: bool = True
    block_external_links: bool = True
    block_phone_numbers: bool = True
    block_external_accounts: bool = True
    allowed_domains: list[str] = field(default_factory=list)
    allowed_accounts: list[str] = field(default_factory=list)


@dataclass
class OpenAIConfig:
    model: str = "gpt-5.2"


@dataclass
class AppConfig:
    accounts: list[AccountConfig]
    safety: SafetyConfig
    commenter: CommenterConfig
    grabber: GrabberConfig
    openai: OpenAIConfig


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"processed": [], "grabber_signatures": []}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_processed(self, key: str) -> bool:
        return key in set(self.data.get("processed", []))

    def mark_processed(self, key: str) -> None:
        processed = self.data.setdefault("processed", [])
        if key not in processed:
            processed.append(key)
        if len(processed) > 10000:
            del processed[: len(processed) - 10000]
        self.save()

    def recent_grabber_signatures(self) -> list[dict[str, Any]]:
        return self.data.setdefault("grabber_signatures", [])

    def add_grabber_signature(self, signature: dict[str, Any], window: int) -> None:
        signatures = self.recent_grabber_signatures()
        signatures.append(signature)
        if len(signatures) > window:
            del signatures[: len(signatures) - window]
        self.save()


class ActionLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(
                    ["timestamp", "module", "account", "source", "target", "post_id", "status", "text"]
                )

    def write(
        self,
        module: str,
        account: str,
        source: str,
        target: str,
        post_id: int,
        status: str,
        text: str,
    ) -> None:
        with self.path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([int(time.time()), module, account, source, target, post_id, status, text])


class AccountRuntime:
    def __init__(self, config: AccountConfig, client: TelegramClient) -> None:
        self.config = config
        self.client = client
        self.last_action_at = 0.0
        self.hourly_action_times: list[float] = []

    def can_act(self, safety: SafetyConfig) -> bool:
        now = time.time()
        self.hourly_action_times = [
            action_time for action_time in self.hourly_action_times if now - action_time < 3600
        ]
        if now - self.last_action_at < safety.min_delay_per_account_seconds:
            return False
        return len(self.hourly_action_times) < safety.max_actions_per_account_per_hour

    def mark_action(self) -> None:
        now = time.time()
        self.last_action_at = now
        self.hourly_action_times.append(now)


def read_filters(raw: dict[str, Any] | None) -> FiltersConfig:
    return FiltersConfig(**(raw or {}))


def load_config(path: Path) -> AppConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))

    commenter_raw = raw.get("commenter", {})
    grabber_raw = raw.get("grabber", {})
    legacy_source_channels = raw.get("source_channels", [])

    commenter = CommenterConfig(
        **{
            **commenter_raw,
            "source_channels": commenter_raw.get("source_channels", legacy_source_channels),
            "filters": read_filters(commenter_raw.get("filters", raw.get("commenting", {}).get("filters"))),
        }
    )

    grabber_rules = []
    for rule in grabber_raw.get("rules", []):
        grabber_rules.append(
            GrabberRuleConfig(
                **{
                    **rule,
                    "filters": read_filters(rule.get("filters")),
                }
            )
        )

    return AppConfig(
        accounts=[AccountConfig(**account) for account in raw["accounts"]],
        safety=SafetyConfig(**raw.get("safety", {})),
        commenter=commenter,
        grabber=GrabberConfig(
            enabled=grabber_raw.get("enabled", False),
            rules=grabber_rules,
            dedupe_enabled=grabber_raw.get("dedupe_enabled", True),
            dedupe_similarity_threshold=grabber_raw.get("dedupe_similarity_threshold", 0.35),
            dedupe_window=grabber_raw.get("dedupe_window", 500),
            add_hashtags=grabber_raw.get("add_hashtags", True),
            hashtag_count=grabber_raw.get("hashtag_count", 3),
            footer_channel=grabber_raw.get("footer_channel", "@Apsny_Gid"),
            ad_filter_enabled=grabber_raw.get("ad_filter_enabled", True),
            block_external_links=grabber_raw.get("block_external_links", True),
            block_phone_numbers=grabber_raw.get("block_phone_numbers", True),
            block_external_accounts=grabber_raw.get("block_external_accounts", True),
            allowed_domains=grabber_raw.get("allowed_domains", []),
            allowed_accounts=grabber_raw.get("allowed_accounts", []),
        ),
        openai=OpenAIConfig(**raw.get("openai", {})),
    )


def filter_reason(text: str, filters: FiltersConfig) -> str | None:
    clean_text = text.strip()
    lowered = clean_text.lower()
    if len(clean_text) < filters.min_text_length:
        return "text_too_short"
    for marker in filters.skip_if_contains:
        if marker.lower() in lowered:
            return f"blocked_word:{marker}"
    if filters.require_any_contains and not any(
        marker.lower() in lowered for marker in filters.require_any_contains
    ):
        return "missing_required_keyword"
    return None


def normalize_domain(domain: str) -> str:
    domain = domain.lower().strip()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.split("/", 1)[0]
    return domain[4:] if domain.startswith("www.") else domain


def normalize_account(account: str) -> str:
    account = account.strip().lower()
    if not account:
        return ""
    if account.startswith("https://t.me/") or account.startswith("http://t.me/"):
        account = account.rsplit("/", 1)[-1]
    if account.startswith("t.me/"):
        account = account.split("/", 1)[1]
    return account if account.startswith("@") else f"@{account}"


def domain_is_allowed(domain: str, allowed_domains: set[str]) -> bool:
    normalized = normalize_domain(domain)
    return any(normalized == allowed or normalized.endswith(f".{allowed}") for allowed in allowed_domains)


def grabber_ad_reason(text: str, grabber: GrabberConfig, rule: GrabberRuleConfig) -> str | None:
    if not grabber.ad_filter_enabled:
        return None

    clean_text = text.strip()
    if not clean_text:
        return None

    allowed_domains = {normalize_domain(domain) for domain in grabber.allowed_domains if normalize_domain(domain)}
    allowed_accounts = {
        normalize_account(account)
        for account in [*grabber.allowed_accounts, rule.target, grabber.footer_channel]
        if normalize_account(account)
    }

    if grabber.block_external_links:
        url_pattern = r"(?i)\b(?:https?://|www\.)[^\s<>()]+|\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>()]*)?"
        for match in re.finditer(url_pattern, clean_text):
            url = match.group(0).rstrip(".,;:!?)]}")
            domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE).split("/", 1)[0]
            if domain.startswith("www."):
                domain = domain[4:]
            if not domain_is_allowed(domain, allowed_domains):
                return f"ad_external_link:{domain.lower()}"

    if grabber.block_phone_numbers:
        phone_pattern = r"(?<!\w)(?:\+?\d[\s().-]*){10,}(?!\w)"
        match = re.search(phone_pattern, clean_text)
        if match:
            digits = re.sub(r"\D", "", match.group(0))
            if len(digits) >= 10:
                return "ad_phone_number"

    if grabber.block_external_accounts:
        account_pattern = r"(?<![\w.])@[A-Za-z0-9_]{4,32}\b|\bt\.me/[A-Za-z0-9_]{4,32}\b"
        for match in re.finditer(account_pattern, clean_text, flags=re.IGNORECASE):
            account = normalize_account(match.group(0))
            if account and account not in allowed_accounts:
                return f"ad_external_account:{account}"

    return None


def normalize_for_dedupe(text: str) -> list[str]:
    lowered = text.lower().replace("ё", "е")
    lowered = re.sub(r"https?://\S+|t\.me/\S+", " ", lowered)
    words = re.findall(r"[a-zа-я0-9]{3,}", lowered, flags=re.IGNORECASE)
    return [light_stem_word(word) for word in words]


def light_stem_word(word: str) -> str:
    if len(word) <= 5:
        return word
    endings = (
        "иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ая", "яя", "ое", "ее",
        "ую", "юю", "ых", "их", "ый", "ий", "ой", "ом", "ем", "ам", "ям", "ах",
        "ях", "ов", "ев", "ия", "ие", "ый", "ого", "его", "лась", "лись", "ать",
        "ять", "или", "ыла", "ало", "ого",
    )
    for ending in endings:
        if word.endswith(ending) and len(word) - len(ending) >= 4:
            return word[: -len(ending)]
    return word


def make_shingles(words: list[str], size: int = 3) -> set[str]:
    if not words:
        return set()
    if len(words) < size:
        return {" ".join(words)}
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def text_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def combined_text_similarity(
    left_shingles: set[str],
    right_shingles: set[str],
    left_words: set[str],
    right_words: set[str],
) -> float:
    shingle_score = text_similarity(left_shingles, right_shingles)
    word_score = text_similarity(left_words, right_words)
    return max(shingle_score, word_score * 0.72)


def find_grabber_duplicate(
    state: StateStore,
    text: str,
    threshold: float,
) -> tuple[dict[str, Any] | None, float, list[str]]:
    words = normalize_for_dedupe(text)
    shingles = sorted(make_shingles(words))
    if not shingles:
        return None, 0.0, shingles

    current = set(shingles)
    current_words = set(words)
    best_match = None
    best_score = 0.0
    for signature in state.recent_grabber_signatures():
        existing = set(signature.get("shingles", []))
        existing_words = set(signature.get("words", []))
        score = combined_text_similarity(current, existing, current_words, existing_words)
        if score > best_score:
            best_score = score
            best_match = signature

    if best_match and best_score >= threshold:
        return best_match, best_score, shingles
    return None, best_score, shingles


async def generate_comment(
    openai_client: AsyncOpenAI,
    model: str,
    post_text: str,
    commenter: CommenterConfig,
) -> str:
    response = await openai_client.responses.create(
        model=model,
        instructions=(
            "Write one natural Telegram comment to a channel post. "
            "Use the same language as the post when language is same_as_post. "
            "Do not include links, hashtags, direct ads, insults, political persuasion, "
            "fake personal claims, or promises on behalf of the author. "
            "The result must be only the comment text."
        ),
        input=(
            f"Language mode: {commenter.language}\n"
            f"Style: {commenter.style}\n"
            f"Max length: {commenter.max_comment_length} characters\n\n"
            f"Post:\n{post_text[:4000]}"
        ),
        max_output_tokens=140,
    )
    comment = response.output_text.strip().strip('"')
    return comment[: commenter.max_comment_length].strip()


async def rewrite_post(
    openai_client: AsyncOpenAI,
    model: str,
    post_text: str,
) -> str:
    response = await openai_client.responses.create(
        model=model,
        instructions=(
            "Rewrite this Telegram post for reposting in an owned or permitted channel. "
            "Preserve facts and meaning, keep the same language, do not invent details, "
            "and do not add aggressive advertising. Return only the rewritten post."
        ),
        input=post_text[:6000],
        max_output_tokens=600,
    )
    return response.output_text.strip()


async def generate_hashtags(
    openai_client: AsyncOpenAI,
    model: str,
    post_text: str,
    count: int,
) -> list[str]:
    if not post_text.strip():
        return []
    response = await openai_client.responses.create(
        model=model,
        instructions=(
            "Generate Telegram hashtags for this post. "
            "Use the same language as the post where possible. "
            "Return only hashtags separated by spaces. "
            "No explanations, no punctuation except # and underscores."
        ),
        input=f"Count: {count}\nPost:\n{post_text[:4000]}",
        max_output_tokens=80,
    )
    raw = response.output_text.strip()
    tags = []
    for token in raw.replace("\n", " ").split():
        token = token.strip().strip(",.;:!?")
        if not token:
            continue
        if not token.startswith("#"):
            token = f"#{token}"
        token = token.replace("-", "_")
        if len(token) > 1 and token not in tags:
            tags.append(token)
        if len(tags) >= count:
            break
    return tags


async def add_grabber_signature_block(
    openai_client: AsyncOpenAI,
    model: str,
    text: str,
    source_text: str,
    grabber: GrabberConfig,
) -> str:
    additions: list[str] = []
    if grabber.add_hashtags and grabber.hashtag_count > 0:
        tags = await generate_hashtags(openai_client, model, source_text or text, grabber.hashtag_count)
        if tags:
            additions.append(" ".join(tags[: grabber.hashtag_count]))
    if grabber.footer_channel:
        additions.append(f"Больше об Абхазии: {grabber.footer_channel}")
    if not additions:
        return text
    base = text.strip()
    if base:
        return f"{base}\n\n" + "\n".join(additions)
    return "\n".join(additions)


def pick_account(accounts: list[AccountRuntime], safety: SafetyConfig) -> AccountRuntime | None:
    eligible = [account for account in accounts if account.can_act(safety)]
    if not eligible:
        return None
    return random.choice(eligible)


def console_print(text: str) -> None:
    print(text.encode("cp1251", errors="replace").decode("cp1251"))


def setup_logging() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(isinstance(handler, logging.StreamHandler) for handler in root.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    if not any(
        isinstance(handler, RotatingFileHandler)
        and getattr(handler, "baseFilename", "") == str(BOT_LOG_PATH)
        for handler in root.handlers
    ):
        file_handler = RotatingFileHandler(
            BOT_LOG_PATH,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def telegram_proxy() -> tuple[Any, ...] | None:
    host = os.getenv("TG_PROXY_HOST", "").strip()
    if not host:
        return None
    if socks is None:
        raise RuntimeError("TG_PROXY_HOST is set, but PySocks is not installed. Run pip install PySocks.")

    port_raw = os.getenv("TG_PROXY_PORT", "").strip()
    if not port_raw:
        raise RuntimeError("TG_PROXY_PORT is required when TG_PROXY_HOST is set.")
    username = os.getenv("TG_PROXY_USERNAME", "").strip() or None
    password = os.getenv("TG_PROXY_PASSWORD", "").strip() or None
    proxy_type = os.getenv("TG_PROXY_TYPE", "socks5").strip().lower()
    proxy_map = {
        "socks5": socks.SOCKS5,
        "socks4": socks.SOCKS4,
        "http": socks.HTTP,
    }
    if proxy_type not in proxy_map:
        raise RuntimeError("TG_PROXY_TYPE must be one of: socks5, socks4, http.")
    return (proxy_map[proxy_type], host, int(port_raw), True, username, password)


async def build_clients(config: AppConfig) -> list[AccountRuntime]:
    runtimes: list[AccountRuntime] = []
    (BASE_DIR / "sessions").mkdir(exist_ok=True)
    proxy = telegram_proxy()
    if proxy:
        logging.info("Telegram proxy enabled: %s:%s", proxy[1], proxy[2])

    for account in config.accounts:
        if not account.enabled:
            continue

        api_id = os.getenv(account.api_id_env)
        api_hash = os.getenv(account.api_hash_env)
        if not api_id or not api_hash:
            raise RuntimeError(
                f"Missing Telegram credentials for {account.name}: "
                f"{account.api_id_env}/{account.api_hash_env}"
            )

        session_path = BASE_DIR / account.session
        session_path.parent.mkdir(parents=True, exist_ok=True)
        client = TelegramClient(str(session_path), int(api_id), api_hash, proxy=proxy)
        await client.start()
        runtimes.append(AccountRuntime(account, client))
        logging.info("Telegram account connected: %s", account.name)

    return runtimes


async def check_sources(config_path: Path, limit: int) -> None:
    load_dotenv(BASE_DIR / ".env")
    setup_logging()

    config = load_config(config_path)
    accounts = await build_clients(config)
    if not accounts:
        raise RuntimeError("No enabled Telegram accounts configured.")

    client = accounts[0].client
    sources = list(config.commenter.source_channels)
    if config.grabber.enabled:
        sources.extend(rule.source for rule in config.grabber.rules if rule.enabled)
    if not sources:
        raise RuntimeError("No sources configured.")

    for source in sources:
        console_print(f"\nSource: {source}")
        entity = await client.get_entity(source)
        console_print(f"Resolved: {getattr(entity, 'title', None) or getattr(entity, 'username', source)}")
        messages = await client.get_messages(entity, limit=limit)
        if not messages:
            console_print("No recent posts visible for this account.")
            continue
        for message in messages:
            text = (message.raw_text or "").replace("\n", " ").strip()
            console_print(f"- id={message.id} date={message.date} text={text[:120]}")

    for account in accounts:
        await account.client.disconnect()


async def comment_latest(config_path: Path) -> None:
    load_dotenv(BASE_DIR / ".env")
    setup_logging()

    config = load_config(config_path)
    if not config.commenter.enabled or not config.commenter.source_channels:
        raise RuntimeError("Commenter is disabled or has no source channels.")

    accounts = await build_clients(config)
    if not accounts:
        raise RuntimeError("No enabled Telegram accounts configured.")

    openai_client = AsyncOpenAI()
    client = accounts[0].client
    source = config.commenter.source_channels[0]
    entity = await client.get_entity(source)
    messages = await client.get_messages(entity, limit=1)
    if not messages:
        raise RuntimeError(f"No recent posts visible in {source}.")

    message = messages[0]
    post_text = (message.raw_text or "").strip()
    reason = filter_reason(post_text, config.commenter.filters)
    if reason:
        raise RuntimeError(f"Latest post was skipped by filters: {reason}")

    account = pick_account(accounts, config.safety)
    if not account:
        raise RuntimeError("No account is currently within action limits.")

    comment = await generate_comment(openai_client, config.openai.model, post_text, config.commenter)
    console_print(f"Latest post id={message.id}")
    console_print(f"Generated comment: {comment}")
    status = await publish_comment(
        event=type(
            "ManualCommentEvent",
            (),
            {"chat": entity, "message": message},
        )(),
        account=account,
        comment=comment,
        dry_run=config.safety.dry_run,
    )
    console_print(f"Status: {status}")

    for account in accounts:
        await account.client.disconnect()


def message_source_name(event: events.NewMessage.Event) -> str:
    chat = getattr(event, "chat", None)
    return getattr(chat, "username", None) or str(event.chat_id)


def source_link(event: events.NewMessage.Event, message: Message) -> str:
    chat = getattr(event, "chat", None)
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{message.id}"
    return ""


async def publish_comment(
    event: events.NewMessage.Event,
    account: AccountRuntime,
    comment: str,
    dry_run: bool,
) -> Literal["dry_run", "sent"]:
    if dry_run:
        logging.info("[DRY RUN] Would comment with %s: %s", account.config.name, comment)
        return "dry_run"

    await account.client.send_message(
        entity=event.chat,
        message=comment,
        comment_to=event.message.id,
    )
    account.mark_action()
    return "sent"


async def publish_grabbed_post(
    account: AccountRuntime,
    target: str,
    text: str,
    source_message: Message,
    copy_media: bool,
    dry_run: bool,
) -> Literal["dry_run", "sent"]:
    has_media = bool(getattr(source_message, "media", None))
    if dry_run:
        logging.info(
            "[DRY RUN] Would post to %s with %s: media=%s text=%s",
            target,
            account.config.name,
            has_media and copy_media,
            text,
        )
        return "dry_run"

    if copy_media and has_media:
        await account.client.send_file(
            entity=target,
            file=source_message.media,
            caption=text or None,
        )
    else:
        await account.client.send_message(entity=target, message=text)
    account.mark_action()
    return "sent"


async def handle_comment_post(
    source_name: str,
    chat_entity: Any,
    message: Message,
    config: AppConfig,
    state: StateStore,
    action_logger: ActionLogger,
    accounts: list[AccountRuntime],
    openai_client: AsyncOpenAI,
) -> None:
    post_key = f"commenter:{source_name}:{message.id}"
    if state.is_processed(post_key):
        return

    post_text = (message.raw_text or "").strip()
    reason = filter_reason(post_text, config.commenter.filters)
    if reason:
        logging.info("Commenter skipped %s: %s", post_key, reason)
        state.mark_processed(post_key)
        return

    account = pick_account(accounts, config.safety)
    if not account:
        logging.warning("No account is within limits for commenter post %s", post_key)
        return

    try:
        logging.info("Generating comment for %s", post_key)
        comment = await generate_comment(
            openai_client=openai_client,
            model=config.openai.model,
            post_text=post_text,
            commenter=config.commenter,
        )
        if not comment:
            logging.warning("OpenAI returned an empty comment for %s", post_key)
            state.mark_processed(post_key)
            return

        if config.safety.dry_run:
            logging.info("[DRY RUN] Would comment with %s: %s", account.config.name, comment)
            status = "dry_run"
        else:
            await account.client.send_message(
                entity=chat_entity,
                message=comment,
                comment_to=message.id,
            )
            account.mark_action()
            status = "sent"

        state.mark_processed(post_key)
        action_logger.write(
            "commenter",
            account.config.name,
            source_name,
            source_name,
            message.id,
            status,
            comment,
        )
        logging.info("Commenter status for %s: %s", post_key, status)
    except FloodWaitError as exc:
        logging.warning("Telegram flood wait for %s: %s seconds", account.config.name, exc.seconds)
    except RPCError as exc:
        logging.exception("Telegram RPC error while commenting %s: %s", post_key, exc)
        state.mark_processed(post_key)
    except Exception:
        logging.exception("Unexpected commenter error for %s", post_key)


async def poll_commenter_sources(
    watcher: TelegramClient,
    config: AppConfig,
    state: StateStore,
    action_logger: ActionLogger,
    accounts: list[AccountRuntime],
    openai_client: AsyncOpenAI,
) -> None:
    resolved_sources: list[tuple[str, Any]] = []
    for source in config.commenter.source_channels:
        entity = await watcher.get_entity(source)
        resolved_sources.append((source, entity))
        logging.info("Polling source resolved: %s", source)

        if not config.commenter.process_existing_on_start:
            messages = await watcher.get_messages(entity, limit=config.commenter.poll_recent_limit)
            for message in messages:
                state.mark_processed(f"commenter:{source}:{message.id}")
            logging.info("Marked existing recent posts as already seen for %s", source)

    while True:
        for source, entity in resolved_sources:
            try:
                messages = await watcher.get_messages(entity, limit=config.commenter.poll_recent_limit)
                for message in reversed(messages):
                    await handle_comment_post(
                        source_name=source,
                        chat_entity=entity,
                        message=message,
                        config=config,
                        state=state,
                        action_logger=action_logger,
                        accounts=accounts,
                        openai_client=openai_client,
                    )
            except Exception:
                logging.exception("Polling failed for source %s", source)
        await asyncio.sleep(config.commenter.poll_interval_seconds)


async def run(config_path: Path) -> None:
    load_dotenv(BASE_DIR / ".env")
    setup_logging()

    config = load_config(config_path)
    if not config.accounts:
        raise RuntimeError("No Telegram accounts configured.")

    state = StateStore(STATE_PATH)
    action_logger = ActionLogger(LOG_PATH)
    accounts = await build_clients(config)
    if not accounts:
        raise RuntimeError("No enabled Telegram accounts configured.")

    openai_client = AsyncOpenAI()
    watcher = accounts[0].client

    if config.commenter.enabled and config.commenter.source_channels:
        @watcher.on(events.NewMessage(chats=config.commenter.source_channels))
        async def on_comment_source_post(event: events.NewMessage.Event) -> None:
            await handle_comment_post(
                source_name=message_source_name(event),
                chat_entity=event.chat,
                message=event.message,
                config=config,
                state=state,
                action_logger=action_logger,
                accounts=accounts,
                openai_client=openai_client,
            )

        asyncio.create_task(
            poll_commenter_sources(
                watcher=watcher,
                config=config,
                state=state,
                action_logger=action_logger,
                accounts=accounts,
                openai_client=openai_client,
            )
        )

    if config.grabber.enabled:
        for rule in config.grabber.rules:
            if not rule.enabled:
                continue

            @watcher.on(events.NewMessage(chats=rule.source))
            async def on_grabber_post(event: events.NewMessage.Event, rule: GrabberRuleConfig = rule) -> None:
                message = event.message
                post_key = f"grabber:{rule.name}:{event.chat_id}:{message.id}"
                if state.is_processed(post_key):
                    return

                post_text = (message.raw_text or "").strip()
                reason = filter_reason(post_text, rule.filters)
                if reason == "text_too_short" and rule.copy_media and message.media:
                    reason = None
                if reason:
                    logging.info("Grabber skipped %s: %s", post_key, reason)
                    state.mark_processed(post_key)
                    return
                reason = grabber_ad_reason(post_text, config.grabber, rule)
                if reason:
                    logging.info("Grabber skipped ad-like post %s: %s", post_key, reason)
                    state.mark_processed(post_key)
                    action_logger.write(
                        "grabber",
                        "",
                        rule.source,
                        rule.target,
                        message.id,
                        reason,
                        post_text[:300],
                    )
                    return

                account = pick_account(accounts, config.safety)
                if not account:
                    logging.warning("No account is within limits for grabber post %s", post_key)
                    return

                try:
                    duplicate = None
                    duplicate_score = 0.0
                    shingles: list[str] = []
                    if config.grabber.dedupe_enabled:
                        duplicate, duplicate_score, shingles = find_grabber_duplicate(
                            state=state,
                            text=post_text,
                            threshold=config.grabber.dedupe_similarity_threshold,
                        )
                        if duplicate:
                            logging.info(
                                "Grabber skipped duplicate %s: similar to %s with score %.3f",
                                post_key,
                                duplicate.get("post_key", "unknown"),
                                duplicate_score,
                            )
                            state.mark_processed(post_key)
                            action_logger.write(
                                "grabber",
                                account.config.name,
                                rule.source,
                                rule.target,
                                message.id,
                                f"duplicate:{duplicate_score:.3f}",
                                post_text[:300],
                            )
                            return

                    output_text = post_text
                    if rule.rewrite_with_ai:
                        if post_text:
                            output_text = await rewrite_post(openai_client, config.openai.model, post_text)
                        else:
                            output_text = ""
                    if rule.add_source_link:
                        link = source_link(event, message)
                        if link:
                            output_text = f"{output_text}\n\nSource: {link}"

                    output_text = await add_grabber_signature_block(
                        openai_client=openai_client,
                        model=config.openai.model,
                        text=output_text,
                        source_text=post_text,
                        grabber=config.grabber,
                    )

                    status = await publish_grabbed_post(
                        account=account,
                        target=rule.target,
                        text=output_text,
                        source_message=message,
                        copy_media=rule.copy_media,
                        dry_run=config.safety.dry_run,
                    )
                    state.mark_processed(post_key)
                    if config.grabber.dedupe_enabled:
                        state.add_grabber_signature(
                            {
                                "post_key": post_key,
                                "source": rule.source,
                                "target": rule.target,
                                "post_id": message.id,
                                "timestamp": int(time.time()),
                                "shingles": shingles or sorted(make_shingles(normalize_for_dedupe(post_text))),
                                "words": sorted(set(normalize_for_dedupe(post_text))),
                                "sample": post_text[:300],
                            },
                            window=config.grabber.dedupe_window,
                        )
                    action_logger.write(
                        "grabber",
                        account.config.name,
                        rule.source,
                        rule.target,
                        message.id,
                        status,
                        output_text,
                    )
                except FloodWaitError as exc:
                    logging.warning("Telegram flood wait for %s: %s seconds", account.config.name, exc.seconds)
                except RPCError as exc:
                    logging.exception("Telegram RPC error while grabbing %s: %s", post_key, exc)
                    state.mark_processed(post_key)
                except Exception:
                    logging.exception("Unexpected grabber error for %s", post_key)

    watched_sources = set(config.commenter.source_channels if config.commenter.enabled else [])
    if config.grabber.enabled:
        watched_sources.update(rule.source for rule in config.grabber.rules if rule.enabled)
    if not watched_sources:
        raise RuntimeError("No enabled sources to watch. Enable commenter or grabber rules.")

    logging.info("Dry run: %s", config.safety.dry_run)
    logging.info("Watching sources: %s", ", ".join(sorted(watched_sources)))
    await watcher.run_until_disconnected()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safe Telegram AI commenter and autoposter")
    parser.add_argument(
        "--config",
        default=str(BASE_DIR / "config.json"),
        help="Path to JSON config file",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check that Telegram account can resolve configured sources and see recent posts",
    )
    parser.add_argument(
        "--check-limit",
        type=int,
        default=3,
        help="How many recent posts to print for each source in --check mode",
    )
    parser.add_argument(
        "--comment-latest",
        action="store_true",
        help="Generate and publish a comment for the latest post in the first commenter source",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.check:
        asyncio.run(check_sources(Path(args.config), args.check_limit))
    elif args.comment_latest:
        asyncio.run(comment_latest(Path(args.config)))
    else:
        asyncio.run(run(Path(args.config)))
