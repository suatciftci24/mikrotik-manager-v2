"""Pure read-only list projections. Never changes stored accounts or authority."""
from datetime import date, timedelta
from sqlalchemy import case, func, literal_column
import re
import unicodedata

GROUPS = ('EXPIRED', 'TODAY', 'WITHIN_3', 'WITHIN_7', 'WITHIN_30', 'ACTIVE', 'UNKNOWN')


def calendar_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return None
    try:
        return value if date.fromisoformat(value).isoformat() == value else None
    except ValueError:
        return None


def search_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).casefold().replace('ı', 'i')


def search_expression(session):
    if session.get_bind().dialect.name == 'sqlite':
        db = session.connection().connection.driver_connection
        db.create_function('subscriber_search_key', 1, search_key, deterministic=True)
        return func.subscriber_search_key

    def normalize(value):
        decomposed = func.normalize(value, literal_column('NFKD'))
        stripped = func.regexp_replace(decomposed, '[\u0300-\u036f]', '', 'g')
        folded = func.lower(func.replace(stripped, 'I', 'i'))
        return func.replace(func.translate(folded, 'ıς', 'iσ'), 'ß', 'ss')
    return normalize


def listing_expressions(session, expires_on, today):
    """Use database expressions so only the requested account page is hydrated."""
    normalize = search_expression(session)
    if session.get_bind().dialect.name == 'sqlite':
        db = session.connection().connection.driver_connection
        db.create_function('subscriber_calendar_date', 1, calendar_date, deterministic=True)
        valid_date = func.subscriber_calendar_date(expires_on)
    else:
        date_pattern = r'^[0-9]{4}-((01|03|05|07|08|10|12)-(0[1-9]|[12][0-9]|3[01])|(04|06|09|11)-(0[1-9]|[12][0-9]|30)|02-(0[1-9]|1[0-9]|2[0-8]))$'
        leap_pattern = r'^([0-9]{2}(0[48]|[2468][048]|[13579][26])|(0[48]|[2468][048]|[13579][26])00)-02-29$'
        valid_date = case(
            ((~expires_on.like('0000-%')) &
             (expires_on.regexp_match(date_pattern) | expires_on.regexp_match(leap_pattern)), expires_on)
        )
    day = today.isoformat()
    bucket = case(
        (valid_date < day, 0),
        (valid_date == day, 1),
        *((valid_date <= (today + timedelta(days=days)).isoformat(), index)
          for index, days in enumerate((3, 7, 30), 2)),
        (valid_date.is_not(None), 5),
        else_=6,
    )
    return normalize, valid_date, bucket
