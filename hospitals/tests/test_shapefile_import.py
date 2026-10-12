import os
import json
import tempfile
import zipfile
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.gis.geos import Point
from django.core.management import call_command
from hospitals.models import Hospital, ShapefileUpload
from hospitals.services.shapefile_importer import ShapefileImporter


class HospitalModelTest(TestCase):
    def test_hospital_creation_and_properties(self):
        point = Point(90.36195, 23.80372, srid=4326)
        hospital = Hospital.objects.create(
            name="Test Heart Hospital",
            address="Mirpur Road, Dhaka",
            specialization="Cardiology, Emergency 24/7, Surgery",
            location=point,
            phone="+880 123456",
            emergency_available=True,
            rating=4.8
        )

        self.assertEqual(hospital.name, "Test Heart Hospital")
        self.assertAlmostEqual(hospital.longitude, 90.36195, places=4)
        self.assertAlmostEqual(hospital.latitude, 23.80372, places=4)
        self.assertEqual(hospital.specializations_list, ["Cardiology", "Emergency 24/7", "Surgery"])
        self.assertEqual(str(hospital), "Test Heart Hospital")


class ShapefileImporterTest(TestCase):
    def test_import_geojson(self):
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [90.370, 23.770]},
                    "properties": {
                        "Name": "Sample Trauma Institute",
                        "Address": "Sher-e-Bangla Nagar",
                        "Specialty": "Orthopedics, Trauma",
                        "Phone": "01700000001",
                        "Emergency": "true"
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [90.410, 23.810]},
                    "properties": {
                        "Name": "Sample Children Care",
                        "Address": "Uttara",
                        "Specialty": "Pediatrics, Child Care",
                        "Phone": "01700000002",
                        "Emergency": "false"
                    }
                }
            ]
        }

        geojson_bytes = json.dumps(geojson_data).encode('utf-8')
        uploaded = SimpleUploadedFile("sample_hospitals.geojson", geojson_bytes, content_type="application/geo+json")

        upload_record = ShapefileUpload.objects.create(
            file=uploaded,
            mode='REPLACE'
        )

        importer = ShapefileImporter(upload_record)
        importer.run()

        upload_record.refresh_from_db()
        self.assertEqual(upload_record.status, 'SUCCESS')
        self.assertEqual(upload_record.records_imported, 2)
        self.assertEqual(Hospital.objects.count(), 2)

        h1 = Hospital.objects.get(name="Sample Trauma Institute")
        self.assertEqual(h1.address, "Sher-e-Bangla Nagar")
        self.assertTrue(h1.emergency_available)
        self.assertAlmostEqual(h1.longitude, 90.370, places=3)
        self.assertAlmostEqual(h1.latitude, 23.770, places=3)

    def test_import_csv(self):
        csv_content = (
            "Name,Address,Specialty,Longitude,Latitude,Phone,Emergency\n"
            "Central Eye Hospital,Dhanmondi,Ophthalmology,90.380,23.750,01900000001,no\n"
            "Neuro Center,Green Road,Neurology,90.385,23.755,01900000002,yes\n"
        ).encode('utf-8')

        uploaded = SimpleUploadedFile("hospitals.csv", csv_content, content_type="text/csv")
        upload_record = ShapefileUpload.objects.create(
            file=uploaded,
            mode='UPDATE'
        )

        importer = ShapefileImporter(upload_record)
        importer.run()

        upload_record.refresh_from_db()
        self.assertEqual(upload_record.status, 'SUCCESS')
        self.assertEqual(upload_record.records_imported, 2)
        self.assertEqual(Hospital.objects.count(), 2)


class SeedHospitalsCommandTest(TestCase):
    def test_seed_command(self):
        call_command('seed_hospitals')
        count = Hospital.objects.count()
        self.assertGreater(count, 0)
        self.assertTrue(Hospital.objects.filter(name__icontains="Heart").exists())
