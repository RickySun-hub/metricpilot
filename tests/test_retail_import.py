"""Hand-calculated source-import tests; do not derive expectations via SQL."""
from datetime import datetime
from decimal import Decimal
import hashlib
import json

import pytest


def row(**updates):
    result = {
        'InvoiceNo': '100', 'StockCode': 'X', 'Description': 'Example',
        'Quantity': 2, 'InvoiceDate': datetime(2011, 10, 4, 12),
        'UnitPrice': Decimal('0.10'), 'CustomerID': 12345,
        'Country': 'United Kingdom',
    }
    result.update(updates)
    return result


def summarize(rows):
    from backend import import_retail
    return import_retail.summarize_rows(iter(rows))


def test_positive_gross_sales_retains_duplicates_and_missing_customer_ids():
    sample = row()
    result = summarize([
        sample, sample.copy(),
        row(InvoiceNo='101', Quantity=3, UnitPrice=Decimal('0.20'), CustomerID=None, Description=None),
        row(InvoiceNo='102', Quantity=1, UnitPrice=Decimal('0.30'), Country='France'),
        row(InvoiceNo='103', Quantity=2, UnitPrice=Decimal('1.005'), InvoiceDate=datetime(2011, 11, 1)),
    ])
    assert result['monthly'] == [
        {'month': '2011-10', 'country': 'France', 'lines': 1, 'orders': 1, 'units': 1, 'gross_sales_gbp': '0.3'},
        {'month': '2011-10', 'country': 'United Kingdom', 'lines': 3, 'orders': 2, 'units': 7, 'gross_sales_gbp': '1'},
        {'month': '2011-11', 'country': 'United Kingdom', 'lines': 1, 'orders': 1, 'units': 2, 'gross_sales_gbp': '2.01'},
    ]
    assert result['audit']['exact_duplicate_rows'] == 1
    assert result['audit']['missing_customer_id_lines'] == 1
    assert result['audit']['missing_description_lines'] == 1
    assert result['audit']['included_lines'] == 5
    assert result['audit']['excluded_lines'] == 0
    assert result['audit']['country_count'] == 2
    assert result['reference']['before'] == {'gross_sales_gbp': '1.3', 'orders': 3, 'lines': 4, 'units': 8}
    assert result['reference']['after'] == {'gross_sales_gbp': '2.01', 'orders': 1, 'lines': 1, 'units': 2}
    assert result['reference']['delta_gbp'] == '0.71'
    assert result['reference']['country_totals'][0] == {
        'country': 'France',
        'before': {'gross_sales_gbp': '0.3', 'orders': 1, 'lines': 1, 'units': 1},
        'after': {'gross_sales_gbp': '0', 'orders': 0, 'lines': 0, 'units': 0},
        'delta_gbp': '-0.3',
    }


def test_exclusions_are_counted_separately_and_may_overlap():
    result = summarize([
        row(InvoiceNo='C100', Quantity=-2),
        row(InvoiceNo='C101', Quantity=2),
        row(Quantity=0), row(Quantity=-1, UnitPrice=0),
        row(UnitPrice=0), row(UnitPrice=-1), row(),
    ])
    audit = result['audit']
    assert audit['total_rows'] == 7
    assert audit['cancellation_lines'] == 2
    assert audit['nonpositive_quantity_lines'] == 3
    assert audit['nonpositive_price_lines'] == 3
    assert audit['invalid_lines'] == 0
    assert audit['included_lines'] == 1
    assert audit['excluded_lines'] == 6
    assert result['monthly'][0]['gross_sales_gbp'] == '0.2'


@pytest.mark.parametrize('updates', [
    {'Quantity': float('nan')}, {'Quantity': float('inf')}, {'Quantity': 1.5},
    {'UnitPrice': float('nan')}, {'UnitPrice': float('inf')}, {'UnitPrice': 'bad'},
    {'InvoiceDate': None}, {'InvoiceDate': 'not a date'},
    {'Country': None}, {'Country': '   '}, {'InvoiceNo': None},
])
def test_invalid_rows_are_excluded_without_crashing(updates):
    result = summarize([row(**updates)])
    assert result['audit']['invalid_lines'] == 1
    assert result['audit']['included_lines'] == 0
    assert result['audit']['excluded_lines'] == 1
    assert result['monthly'] == []


def test_canonical_output_is_deterministic_and_contains_no_customer_fields():
    rows = [row(), row(InvoiceNo='103', Country='Réunion', InvoiceDate=datetime(2011, 11, 1))]
    first = summarize(rows)
    assert first == summarize(reversed(rows))
    payload = {key: value for key, value in first.items() if key != 'hash'}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert first['hash'] == hashlib.sha256(canonical).hexdigest()
    encoded = json.dumps(first)
    assert 'CustomerID' not in encoded
    assert 'Description' not in encoded
    assert '12345' not in encoded
    assert first['audit']['source_date_min'] == '2011-10-04T12:00:00'
    assert first['audit']['source_date_max'] == '2011-11-01T00:00:00'


def test_workbook_contract_rejects_wrong_headers_and_dimensions():
    from backend.import_retail import EXPECTED_HEADERS, validate_workbook_contract
    validate_workbook_contract(EXPECTED_HEADERS, 541910, 8)
    with pytest.raises(ValueError, match='headers'):
        validate_workbook_contract(tuple(reversed(EXPECTED_HEADERS)), 541910, 8)
    with pytest.raises(ValueError, match='dimensions'):
        validate_workbook_contract(EXPECTED_HEADERS, 4, 8)


def test_output_validation_rejects_identifying_fields():
    from backend.import_retail import validate_public_aggregates
    payload = summarize([row()])
    validate_public_aggregates(payload)
    payload['monthly'][0]['CustomerID'] = 12345
    with pytest.raises(ValueError, match='aggregate fields'):
        validate_public_aggregates(payload)


def test_pinned_source_metadata_cannot_be_assigned_to_an_arbitrary_workbook(tmp_path):
    from backend.import_retail import import_workbook
    fake_workbook = tmp_path / 'not-the-source.xlsx'
    fake_workbook.write_bytes(b'not the UCI workbook')
    with pytest.raises(ValueError, match='SHA-256'):
        import_workbook(fake_workbook)
