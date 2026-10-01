from ocr_capture.text_diff import CaptionTracker, diff_caption_words


def words(text: str) -> list[str]:
    return text.split()


def new(previous: str, current: str) -> str:
    return " ".join(diff_caption_words(words(previous), words(current)).new_words)


def test_identical_screen_has_nothing_new():
    assert new("Yeah, I can start", "Yeah, I can start") == ""


def test_words_added_at_the_end():
    assert new("Yeah, I can start", "Yeah, I can start immediately once I get") == "immediately once I get"


def test_scrolling_and_rewrap_only_return_the_tail():
    previous = "Yeah, I can start immediately once I get the offer and."
    current = "the offer and. Yeah, I do have another opportunity"
    assert new(previous, current) == "Yeah, I do have another opportunity"


def test_punctuation_and_case_changes_are_not_new():
    assert new("offer and", "Offer and.") == ""


def test_corrected_last_word_is_retracted_and_replaced():
    update = diff_caption_words(words("I want to go to the stor"), words("I want to go to the store today"))
    assert update.new_words == ("store", "today")
    assert update.retracted == 1


def test_misread_word_inside_overlap_is_tolerated():
    assert new("one two three four five six", "one two thr3e four five six seven") == "seven"


def test_completely_new_screen_returns_everything():
    assert new("old caption here", "brand new sentence") == "brand new sentence"


def test_single_chance_match_is_not_an_anchor():
    assert new("we went to the park", "the weather is nice") == "the weather is nice"


def test_tracker_first_screen_is_new_in_full():
    tracker = CaptionTracker()
    tracker.observe(words("already on screen"))
    tracker.observe(words("already on screen"))
    assert tracker.take_pending() == "already on screen"
    assert tracker.take_pending() == ""


def test_tracker_collects_between_takes_and_survives_scrolling():
    tracker = CaptionTracker()
    tracker.observe(words("Yeah, I can start"))
    assert tracker.take_pending() == "Yeah, I can start"
    tracker.observe(words("Yeah, I can start immediately once"))
    tracker.observe(words("start immediately once I get the offer"))
    assert tracker.take_pending() == "immediately once I get the offer"
    assert tracker.take_pending() == ""
    tracker.observe(words("start immediately once I get the offer"))
    assert tracker.take_pending() == ""


def test_tracker_retracts_unsent_corrections_only():
    tracker = CaptionTracker()
    tracker.observe(words("we can meet on"))
    tracker.take_pending()
    tracker.observe(words("we can meet on Mundy"))
    tracker.observe(words("we can meet on Monday at noon"))
    assert tracker.take_pending() == "Monday at noon"


def test_tracker_ignores_empty_screens():
    tracker = CaptionTracker()
    tracker.observe(words("hello there"))
    tracker.take_pending()
    tracker.observe([])
    tracker.observe(words("hello there"))
    assert tracker.take_pending() == ""


def test_tracker_reset_makes_the_whole_screen_new_again():
    tracker = CaptionTracker()
    tracker.observe(words("one two"))
    tracker.take_pending()
    tracker.reset()
    tracker.observe(words("one two three"))
    assert tracker.take_pending() == "one two three"
