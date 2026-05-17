from main import GrabberConfig, GrabberRuleConfig, grabber_ad_reason


def make_grabber(**overrides) -> GrabberConfig:
    values = {
        "enabled": True,
        "allowed_accounts": ["@Apsny_Gid"],
        "allowed_domains": ["a-gid.com"],
    }
    values.update(overrides)
    return GrabberConfig(**values)


def make_rule() -> GrabberRuleConfig:
    return GrabberRuleConfig(
        name="test",
        source="@source_channel",
        target="@Apsny_Gid",
    )


def test_ad_filter_blocks_external_links() -> None:
    text = "Лучшее предложение недели: https://example.com/order"
    assert grabber_ad_reason(text, make_grabber(), make_rule()) == "ad_external_link:example.com"


def test_ad_filter_allows_configured_domains() -> None:
    text = "Подробности на сайте https://a-gid.com/news"
    assert grabber_ad_reason(text, make_grabber(), make_rule()) is None


def test_ad_filter_blocks_phone_numbers() -> None:
    text = "Бронирование и реклама по телефону +7 940 123-45-67"
    assert grabber_ad_reason(text, make_grabber(), make_rule()) == "ad_phone_number"


def test_ad_filter_blocks_external_accounts() -> None:
    text = "Для заказа пишите @some_manager"
    assert grabber_ad_reason(text, make_grabber(), make_rule()) == "ad_external_account:@some_manager"


def test_ad_filter_allows_own_account() -> None:
    text = "Больше материалов в @Apsny_Gid"
    assert grabber_ad_reason(text, make_grabber(), make_rule()) is None
