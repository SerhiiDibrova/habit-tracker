from datetime import date, timedelta


def calculate_streaks(
    check_in_dates: list[date], today: date
) -> tuple[int, int, int, bool]:
    """Return (current_streak, best_streak, total_check_ins, completed_today).

    current_streak: consecutive days ending today (or yesterday if not checked in today).
    best_streak: historical maximum consecutive run in the date set.
    """
    if not check_in_dates:
        return 0, 0, 0, False

    date_set = set(check_in_dates)
    total = len(check_in_dates)
    completed_today = today in date_set

    sorted_dates = sorted(check_in_dates)

    # Best streak: scan for the longest consecutive run
    best = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            run += 1
            if run > best:
                best = run
        else:
            run = 1

    # Current streak: count consecutive days backwards from today (or yesterday)
    anchor = today if completed_today else today - timedelta(days=1)
    current = 0
    d = anchor
    while d in date_set:
        current += 1
        d -= timedelta(days=1)

    return current, best, total, completed_today
