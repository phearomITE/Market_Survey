"""Shared final-summary Outlet Name recognition for reports and alerts."""
import unicodedata

SUMMARY_MARKERS = (
    'បូកសរុបរួម', 'បូកសរុបរូម', 'សរុបរួម',
    'បួកសរុបរួម', 'សរុបចុងក្រោយ', 'បូកសរុបចុងក្រោយ',
)


def is_summary_name(value):
    text = unicodedata.normalize('NFC', str(value or ''))
    for hidden in ('\u200b', '\u200c', '\u200d', '\ufeff'):
        text = text.replace(hidden, '')
    text = ''.join(text.split())
    return any(marker in text for marker in SUMMARY_MARKERS)
