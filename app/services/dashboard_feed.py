"""Flat, own-brand product feed for dashboard reporting."""
from app.core.summary_marker import is_summary_name
from app.services.offline_locations import get_boundary_index
from app.reports.aggregator import OWN_PRODUCTS, HORECA_OWN_PRODUCTS, COMPETITOR_PRODUCTS, HORECA_COMPETITOR_PRODUCTS

HEADERS = ('Date', 'Region', 'Dealer', 'Outlet Name', 'Outlet Type',
           'Phone Number Outlet', 'Latitude', 'Longitude', 'Province', 'District',
           'Commune', 'Product', 'Movement Rate', 'Key Issues Detail', 'Suggestion', 'Submission ID', 'submit_time', 'id', 'Code_Province', 'Code_District', 'Code_Commune', 'Product Type', 'Report Type')


def dashboard_values(rows):
    """Rows are SQL mappings. One visit × own product; no summary markers."""
    index = get_boundary_index()
    previous_pin = object()
    admin = ['', '', '', '', '', '']
    for row in rows:
        if is_summary_name(row['outlet_name']):
            continue
        channel = str(row['report_type'] or 'GT').strip().upper()
        competitor = row.get('product_type') == 'Competitor'
        products = ((HORECA_COMPETITOR_PRODUCTS if competitor else HORECA_OWN_PRODUCTS)
                    if channel == 'HORECA' else
                    (COMPETITOR_PRODUCTS if competitor else OWN_PRODUCTS))
        if row['product_name'] not in products:
            continue
        pin = (row['gps_latitude'], row['gps_longitude'])
        if pin != previous_pin:
            admin = index.resolve_admin(*pin)
            previous_pin = pin
        rate = 0 if row['available'] is False else row['movement_score']
        yield (row['report_date'], row['region'], row['dealer'], row['outlet_name'],
               row['outlet_type'], row['phone_number'], *pin, *admin[:3],
               row['product_name'], rate, row['key_issue_text'], row['suggestion_text'], row['submission_id'],
               row['submission_time'], row['submission_id'], *admin[3:], row.get('product_type', 'Own Product'), channel)
