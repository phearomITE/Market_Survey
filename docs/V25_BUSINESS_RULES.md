# V25 Business Rule Updates

## Offtake Movement Goal = 10

Report movement now uses the mode (most frequent movement score) across outlet submissions.

Rule:
- If final mode movement is 8, 9, or 10, the report shows 10.
- If final mode movement is 0-7, the report shows that mode value.

Example:
- CB LITE values: 8, 2, 8, 8
- Mode = 8
- Report final movement = 10

## Combine Location Visit

Dealer report Location of Visit combines all unique location text values from submitted outlets instead of showing only one repeated/location mode.

## Hanuman Original Removed

Hanuman Original / Hanuman is removed from:
- competitor aggregation list
- template competitor section
- Kobo XLSForm survey rows
- Kobo Bot_Data_Map

Hanuman Lite and Hanuman Black remain.
