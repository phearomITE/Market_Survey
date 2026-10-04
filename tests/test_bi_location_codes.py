from app.services.offline_locations import BoundaryIndex, get_boundary_index


def test_codes_and_existing_names_api():
    index = get_boundary_index()
    result = index.resolve_admin(11.55, 104.93)
    assert result == ['Phnom Penh', 'Chamkar Mon', 'Tonle Basak', '12', '1201', '120101']
    assert index.resolve(11.55, 104.93) == result[:3]
    assert index.resolve_admin(None, None) == [''] * 6


def test_leading_zero_and_ambiguous_boundary():
    record = dict(priority=0, code='10201', names=['P', 'D', 'C'],
                  polygons=[[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]])
    assert BoundaryIndex([record]).resolve_admin(.5, .5)[3:] == ['01', '0102', '010201']
    other = dict(record, code='010202')
    assert BoundaryIndex([record, other]).resolve_admin(.5, .5) == [''] * 6
