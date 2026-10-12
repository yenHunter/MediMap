import os
import json
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from hospitals.models import Hospital

HOSPITAL_METADATA = {
    "National Heart Foundation Hospital": {
        "address": "Plot 4, Road 2, Section 2, Mirpur, Dhaka 1216",
        "specialization": "Cardiology, Cardiovascular Surgery, Emergency 24/7, CCU",
        "phone": "+880 2-9033442",
        "emergency_available": True,
        "rating": 4.8,
        "website": "https://nhf.org.bd"
    },
    "Dr. MR Khan Shishu Hospital": {
        "address": "Section 2, Mirpur, Dhaka 1216",
        "specialization": "Pediatrics, Neonatal Care, Child Surgery, Emergency 24/7, NICU",
        "phone": "+880 2-9013589",
        "emergency_available": True,
        "rating": 4.9,
        "website": "https://mrkhanshishuhospital.org"
    },
    "Kidney Foundation Hospital": {
        "address": "Plot 5/1, Road 2, Section 2, Mirpur, Dhaka 1216",
        "specialization": "Nephrology, Urology, Kidney Transplant, Dialysis Unit",
        "phone": "+880 2-9014167",
        "emergency_available": True,
        "rating": 4.7,
        "website": "https://kidneyfoundationbd.com"
    },
    "National Institute of Mental Health": {
        "address": "Sher-e-Bangla Nagar, Dhaka 1207",
        "specialization": "Psychiatry, Neurology, Mental Health, Clinical Psychology",
        "phone": "+880 2-9118171",
        "emergency_available": False,
        "rating": 4.5,
        "website": "http://nimh.gov.bd"
    },
    "Bangladesh Eye Hospital": {
        "address": "78 Satmasjid Road, Dhanmondi, Dhaka 1205",
        "specialization": "Ophthalmology, Cataract Surgery, Retina & Glaucoma, Lasik",
        "phone": "+880 9666-787878",
        "emergency_available": False,
        "rating": 4.7,
        "website": "https://bdeyehospital.com"
    },
    "Combined Military Hospital": {
        "address": "Dhaka Cantonment, Dhaka 1206",
        "specialization": "General Medicine, Cardiology, Neurology, Orthopedics, Emergency 24/7",
        "phone": "+880 2-9870011",
        "emergency_available": True,
        "rating": 4.9,
        "website": "https://army.mil.bd"
    },
    "United Hospital Limited": {
        "address": "Plot 15, Road 71, Gulshan-2, Dhaka 1212",
        "specialization": "Cardiology, Oncology, Neurology, Emergency 24/7, Multi-Specialty",
        "phone": "+880 2-8836444",
        "emergency_available": True,
        "rating": 4.8,
        "website": "https://unitedhospital.com.bd"
    },
    "Evercare Hospital": {
        "address": "Plot 81, Block E, Bashundhara R/A, Dhaka 1229",
        "specialization": "Cardiology, Neurology, Oncology, Orthopedics, Emergency 24/7, JCI Accredited",
        "phone": "+880 2-55668000",
        "emergency_available": True,
        "rating": 4.8,
        "website": "https://evercarebd.com"
    },
    "National Institute of CardioVascular Diseases": {
        "address": "Sher-e-Bangla Nagar, Dhaka 1207",
        "specialization": "Cardiology, Heart Surgery, CCU, Emergency 24/7",
        "phone": "+880 2-9122560",
        "emergency_available": True,
        "rating": 4.6,
        "website": "http://nicvd.gov.bd"
    },
    "National Institute of Traumatology and Orthopaedic Rehabilitation (NITOR)": {
        "address": "Sher-e-Bangla Nagar, Dhaka 1207",
        "specialization": "Orthopedics, Trauma & Fracture, Spine Surgery, Emergency 24/7",
        "phone": "+880 2-9114075",
        "emergency_available": True,
        "rating": 4.6,
        "website": "http://nitor.gov.bd"
    },
    "Ibn Sina Medical College Hospital": {
        "address": "1/1 B, Kallyanpur, Dhaka 1207",
        "specialization": "General Medicine, Surgery, Gynecology, Pediatrics, Emergency 24/7",
        "phone": "+880 2-9010396",
        "emergency_available": True,
        "rating": 4.7,
        "website": "https://ibnsinatrust.com"
    },
    "Bangladesh Spine & Orthopaedic Hospital -BSOH": {
        "address": "House 10, Road 4, Kallyanpur, Dhaka 1207",
        "specialization": "Orthopedics, Spine Surgery, Arthroscopy, Physiotherapy",
        "phone": "+880 1766-662888",
        "emergency_available": True,
        "rating": 4.6,
        "website": "https://bsoh.com.bd"
    },
    "Raddh MCH-FP Center": {
        "address": "Mirpur-10, Dhaka 1216",
        "specialization": "Gynecology, Obstetrics, Maternal & Child Health, Family Planning",
        "phone": "+880 2-9005432",
        "emergency_available": False,
        "rating": 4.4,
        "website": ""
    },
    "Islami Bank Hospital Mirpur": {
        "address": "Plot 31, Block D, Section 11, Mirpur, Dhaka 1216",
        "specialization": "General Medicine, Gynecology, Pediatrics, Nephrology, Emergency 24/7",
        "phone": "+880 2-9000103",
        "emergency_available": True,
        "rating": 4.6,
        "website": "https://ibfbd.org"
    },
    "Kurmitola General Hospital": {
        "address": "Airport Road, Dhaka Cantonment, Dhaka 1206",
        "specialization": "General Medicine, Surgery, ICU, Emergency 24/7, Government Tertiary",
        "phone": "+880 2-8711234",
        "emergency_available": True,
        "rating": 4.7,
        "website": "http://kgh.gov.bd"
    },
    "Ad-Din Medical College Hospital, MaghBazar": {
        "address": "2 Bara Moghbazar, Dhaka 1217",
        "specialization": "Gynecology & Obstetrics, Pediatrics, Neonatology, Emergency 24/7",
        "phone": "+880 2-9353391",
        "emergency_available": True,
        "rating": 4.8,
        "website": "https://ad-din.org"
    },
    "Uttara Adhunik Medical College Hospital (BMSRI)": {
        "address": "Sector 9, Uttara Model Town, Dhaka 1230",
        "specialization": "General Medicine, Cardiology, Orthopedics, Pediatrics, Emergency 24/7",
        "phone": "+880 2-8954753",
        "emergency_available": True,
        "rating": 4.6,
        "website": "https://uamc.edu.bd"
    },
    "Shaheed Suhrawardy Medical College and Hospital": {
        "address": "Sher-e-Bangla Nagar, Dhaka 1207",
        "specialization": "General Medicine, Cardiology, Surgery, ICU, Emergency 24/7",
        "phone": "+880 2-9130800",
        "emergency_available": True,
        "rating": 4.7,
        "website": "http://shsmc.gov.bd"
    },
    "National Center for Control of Rheumatic Fever & Heart Disease": {
        "address": "Sher-e-Bangla Nagar, Dhaka 1207",
        "specialization": "Cardiology, Rheumatic Fever, Pediatric Cardiology",
        "phone": "+880 2-9110461",
        "emergency_available": False,
        "rating": 4.5,
        "website": ""
    },
    "Lifewave - Hospital": {
        "address": "Sector 11, Uttara, Dhaka 1230",
        "specialization": "General Medicine, Orthopedics, Emergency 24/7",
        "phone": "+880 1711-223344",
        "emergency_available": True,
        "rating": 4.4,
        "website": ""
    },
    "East West Medical College & Hospital": {
        "address": "Aichi Nagar, Jigatola, Turag, Dhaka 1711",
        "specialization": "General Medicine, Cardiology, Pediatrics, Gynecology, Emergency 24/7",
        "phone": "+880 2-8981997",
        "emergency_available": True,
        "rating": 4.6,
        "website": "https://ewmch.com"
    },
    "Greenland Hospital Ltd.": {
        "address": "Plot 25, Road 2, Sector 10, Uttara, Dhaka 1230",
        "specialization": "General Surgery, Medicine, Orthopedics, Emergency 24/7",
        "phone": "+880 2-8958514",
        "emergency_available": True,
        "rating": 4.5,
        "website": ""
    },
    "Ahsania Mission Cancer and General Hospital": {
        "address": "Plot 3, Embankment Drive Way, Sector 10, Uttara, Dhaka 1230",
        "specialization": "Oncology, Cancer Surgery, Radiotherapy, Chemotherapy, Emergency 24/7",
        "phone": "+880 2-55092000",
        "emergency_available": True,
        "rating": 4.9,
        "website": "https://ahsaniacancer.org.bd"
    },
    "Ark Hospital Limited": {
        "address": "House 1, Road 2, Sector 4, Uttara, Dhaka 1230",
        "specialization": "General Medicine, Pediatrics, Gynecology, Emergency 24/7",
        "phone": "+880 2-8962451",
        "emergency_available": True,
        "rating": 4.5,
        "website": ""
    }
}


class Command(BaseCommand):
    help = "Seeds initial hospital points into PostGIS from Hospital_of_Dhaka.json"

    def handle(self, *args, **options):
        json_path = os.path.join(settings.BASE_DIR, 'map_application', 'static', 'json', 'Hospital_of_Dhaka.json')

        if not os.path.exists(json_path):
            self.stderr.write(self.style.ERROR(f"JSON file not found at {json_path}"))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        features = data.get('features', [])
        self.stdout.write(f"Found {len(features)} hospital features in JSON.")

        created_count = 0
        updated_count = 0

        for feat in features:
            props = feat.get('properties', {})
            geom = feat.get('geometry', {})
            coords = geom.get('coordinates', [])

            name = props.get('Name', '').strip()
            if not name or len(coords) < 2:
                continue

            lng, lat = coords[0], coords[1]
            point = Point(lng, lat, srid=4326)

            meta = HOSPITAL_METADATA.get(name, {
                "address": "Dhaka, Bangladesh",
                "specialization": "General Medicine, Emergency 24/7",
                "phone": "+880 2-9000000",
                "emergency_available": True,
                "rating": 4.5,
                "website": ""
            })

            hospital, created = Hospital.objects.update_or_create(
                name=name,
                defaults={
                    "address": meta["address"],
                    "specialization": meta["specialization"],
                    "location": point,
                    "phone": meta["phone"],
                    "emergency_available": meta["emergency_available"],
                    "opening_hours": "24/7",
                    "rating": meta["rating"],
                    "website": meta.get("website") or None,
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded hospitals: {created_count} created, {updated_count} updated. Total in DB: {Hospital.objects.count()}"
            )
        )
