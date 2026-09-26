"""Munich calendar dates used to avoid inventing weekly markets on holidays."""
from datetime import date, timedelta


def easter(year: int) -> date:
    # Gregorian computus (Meeus/Jones/Butcher).
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def munich_holidays(year: int) -> set[date]:
    # StMI Feiertagsgesetz; Mariä Himmelfahrt applies in Munich, Augsburger Friedensfest does not.
    fixed = {(1,1),(1,6),(5,1),(8,15),(10,3),(11,1),(12,25),(12,26)}
    return {date(year,m,d) for m,d in fixed} | {easter(year)+timedelta(days=n) for n in (-2,1,39,50,60)}
