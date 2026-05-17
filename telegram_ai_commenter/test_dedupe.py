from main import combined_text_similarity, make_shingles, normalize_for_dedupe


def similarity(left: str, right: str) -> float:
    left_words = normalize_for_dedupe(left)
    right_words = normalize_for_dedupe(right)
    return combined_text_similarity(
        make_shingles(left_words),
        make_shingles(right_words),
        set(left_words),
        set(right_words),
    )


def test_similar_posts_are_close() -> None:
    left = "В Гагре открыли новую прогулочную зону у моря. Туристы уже гуляют по набережной вечером."
    right = "В Гагре открылась новая прогулочная зона возле моря, и туристы уже гуляют по набережной вечером."
    assert similarity(left, right) >= 0.35


def test_different_posts_are_far() -> None:
    left = "В Гагре открыли новую прогулочную зону у моря."
    right = "В Сухуме прошла конференция для IT-специалистов и разработчиков сайтов."
    assert similarity(left, right) < 0.25


if __name__ == "__main__":
    test_similar_posts_are_close()
    test_different_posts_are_far()
    print("dedupe tests passed")
