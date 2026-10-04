Adds Code_Province, Code_District, Code_Commune to both dashboard CSV routes.
Uses the same bundled GPS polygon match as Province/District/Commune; no API calls or database backfill required.
Commune identifiers are normalized to six-digit text; province uses first two digits, district first four. Invalid or ambiguous GPS locations remain blank.
After deployment, refresh Power BI. Remove any fixed Columns=18/16 from Csv.Document. Set all three code columns to Text, preserving leading zeros.
Map_location COM_Code must also be text padded to six digits. Use a unique commune dimension if Map_location contains multiple rows per commune. Relationship: unique commune Code (1) -> dashboard Code_Commune (*), single direction.
The bundled GeoJSON fallback is older coverage; codes reflect bundled reference boundaries, not a newly verified official administrative revision.
