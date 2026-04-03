from datetime import date, timedelta


def get_last_n_trading_days(n: int) -> list[date]:
    """
    Return the last N trading days (Mon-Fri) up to and including yesterday.
    Simple heuristic: skip weekends. Taiwan holidays are not accounted for here.
    """
    result = []
    d = date.today() - timedelta(days=1)
    while len(result) < n:
        if d.weekday() < 5:  # 0=Mon ... 4=Fri
            result.append(d)
        d -= timedelta(days=1)
    return sorted(result)


def date_to_taifex_str(d: date) -> str:
    """TAIFEX uses Republic of China calendar for some endpoints, but most
    download APIs also accept Gregorian yyyy/mm/dd or yyyymmdd.
    Returns 'yyyy/mm/dd' string."""
    return d.strftime("%Y/%m/%d")
