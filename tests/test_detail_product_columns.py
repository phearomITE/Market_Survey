import tempfile
import unittest
from datetime import date
from types import SimpleNamespace as Row
from openpyxl import load_workbook
from app.services.outlet_detail_export import create_detail_export

class ProductDetailTests(unittest.TestCase):
    def test_product_rows_rates_and_outlet_fields(self):
        metrics = [Row(product_name='CB LITE ORD', available=True, movement_score=10),
                   Row(product_name='CB BLACK NCP', available=False, movement_score=7),
                   Row(product_name='CB Original NCP', available=True, movement_score=None),
                   Row(product_name='CBC 4.4 NCP', available=True, movement_score=0),
                   Row(product_name='CAMBODIA Sport 500mL ORD',available=True,movement_score=8),
                   Row(product_name='WURKZ ORD',available=True,movement_score=10)]
        outlet = Row(outlet_name='Shop',region='R1',dealer='CA2',phone_number='012345678',
                     gps_latitude=11.55,gps_longitude=104.93,product_metrics=metrics)
        with tempfile.TemporaryDirectory() as folder:
            path, visits, unresolved = create_detail_export([outlet],date(2026,1,3),folder,lambda *p:['P','D','C'])
            wb=load_workbook(path);ws=wb.active
            self.assertEqual((visits,unresolved),(1,0))
            self.assertEqual((ws.max_row,ws.max_column),(5,13))
            self.assertEqual([ws.cell(1,c).value for c in (12,13)],['Product_Beer','Movement Rate'])
            self.assertEqual([ws.cell(r,13).value for r in range(2,6)],[10,0,None,0])
            self.assertEqual([ws.cell(r,6).value for r in range(2,6)],['012345678']*4)
            self.assertEqual(ws['L3'].value,'CB BLACK NCP')
            wb.close()

    def test_horeca_beer_and_nonbeer_only_outlet(self):
        from app.services.outlet_detail_export import beer_metrics
        self.assertEqual([m.product_name for m in beer_metrics(Row(product_metrics=[
            Row(product_name='CBL Pint'), Row(product_name='CB Black Pint'), Row(product_name='DAZZ ORD')]))],
            ['CBL Pint','CB Black Pint'])
        with tempfile.TemporaryDirectory() as folder:
            path, visits, missing=create_detail_export([Row(outlet_name='Nonbeer',product_metrics=[Row(product_name='DAZZ ORD')])],date(2026,1,3),folder)
            wb=load_workbook(path)
            self.assertEqual((visits,missing,wb.active.max_row),(0,0,1))
            wb.close()

if __name__ == '__main__':
    unittest.main()
