"""Pure read-only list projections. Never changes stored accounts or authority."""
from datetime import date
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


def expiry_group(value, today):
    end = calendar_date(value)
    if end is None:
        return 'UNKNOWN'
    days = (date.fromisoformat(end) - today).days
    return ('EXPIRED' if days < 0 else 'TODAY' if days == 0 else 'WITHIN_3' if days <= 3
            else 'WITHIN_7' if days <= 7 else 'WITHIN_30' if days <= 30 else 'ACTIVE')


def search_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).casefold().replace('ı', 'i')


def grouped_listing(rows, query, selected, today):
    terms = search_key(query).split()
    matches = []
    counts = dict.fromkeys(GROUPS, 0)
    for account, router in rows:
        fields = account.fields
        text = search_key(' '.join(str(v or '') for v in (
            fields.get('username'), fields.get('customer_name'), fields.get('plan'),
            fields.get('ip_address'), account.id, router.fields.get('name') if router else None)))
        if not all(term in text for term in terms):
            continue
        group = expiry_group(fields.get('expires_on'), today)
        counts[group] += 1
        if selected == 'ALL' or selected == group:
            matches.append((account, router))
    matches.sort(key=lambda pair: (GROUPS.index(expiry_group(pair[0].fields.get('expires_on'), today)),
                                   calendar_date(pair[0].fields.get('expires_on')) or '9999-12-31',
                                   search_key(pair[0].fields.get('username')), pair[0].id))
    return matches, counts
