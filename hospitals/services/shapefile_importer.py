import os
import zipfile
import tempfile
import shutil
import csv
import json
import logging
from django.db import transaction
from django.contrib.gis.geos import Point
from django.contrib.gis.gdal import DataSource, CoordTransform, SpatialReference
from hospitals.models import Hospital

logger = logging.getLogger(__name__)


class ShapefileImporter:
    """
    Ingests ESRI Shapefile (.zip), GeoJSON, or CSV files into PostGIS.
    Handles coordinate transformations to EPSG:4326 and intelligent field auto-mapping.
    """

    NAME_ALIASES = ['name', 'hospital', 'hosp_name', 'facility', 'title', 'n']
    ADDRESS_ALIASES = ['address', 'addr', 'location', 'loc', 'place', 'street']
    SPECIALTY_ALIASES = ['specialization', 'specialty', 'speciality', 'specializa', 'spec', 'type', 'category', 'dept']
    PHONE_ALIASES = ['phone', 'contact', 'tel', 'telephone', 'mobile', 'cell']
    EMERGENCY_ALIASES = ['emergency', 'emerg', 'er_avail', 'er', 'emergency_available']
    RATING_ALIASES = ['rating', 'score', 'stars']
    HOURS_ALIASES = ['hours', 'opening_hours', 'time', 'open']
    WEBSITE_ALIASES = ['website', 'web', 'url']

    def __init__(self, upload_instance):
        self.upload = upload_instance
        self.file_path = upload_instance.file.path
        self.mode = upload_instance.mode
        self.logs = []
        self.imported_count = 0

    def log(self, message):
        self.logs.append(message)
        logger.info(message)

    def run(self):
        filename = os.path.basename(self.file_path).lower()
        self.log(f"Starting ingestion for file: {filename} (Mode: {self.mode})")

        temp_dir = None
        try:
            if filename.endswith('.zip'):
                temp_dir = tempfile.mkdtemp(prefix='shp_upload_')
                self._process_zip(temp_dir)
            elif filename.endswith('.geojson') or filename.endswith('.json'):
                self._process_geojson(self.file_path)
            elif filename.endswith('.csv'):
                self._process_csv(self.file_path)
            else:
                raise ValueError(f"Unsupported file format: {filename}. Please upload .ZIP, .GeoJSON, or .CSV.")

            self.upload.status = 'SUCCESS'
            self.upload.records_imported = self.imported_count
            self.log(f"Ingestion completed successfully. Total hospitals imported/updated: {self.imported_count}")

        except Exception as e:
            self.upload.status = 'FAILED'
            self.log(f"ERROR: Ingestion failed - {str(e)}")
            logger.exception("Shapefile ingestion failed")
            raise e
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

            self.upload.log = "\n".join(self.logs)
            self.upload.save()

    def _process_zip(self, temp_dir):
        self.log("Extracting ZIP archive...")
        with zipfile.ZipFile(self.file_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        shp_files = []
        for root, dirs, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith('.shp'):
                    shp_files.append(os.path.join(root, f))

        if not shp_files:
            raise FileNotFoundError("No .shp file found inside the uploaded ZIP archive.")

        shp_path = shp_files[0]
        self.log(f"Found shapefile: {os.path.basename(shp_path)}")
        self._process_shapefile(shp_path)

    def _process_shapefile(self, shp_path):
        ds = DataSource(shp_path)
        layer = ds[0]
        total_features = len(layer)
        self.log(f"Shapefile layer loaded with {total_features} features. Geometry type: {layer.geom_type}")

        source_srs = layer.srs
        target_srs = SpatialReference(4326)
        coord_transform = None

        if source_srs and source_srs.srid != 4326:
            self.log(f"Layer CRS detected: {source_srs.name or source_srs.srid}. Setting up transformation to EPSG:4326.")
            coord_transform = CoordTransform(source_srs, target_srs)
        else:
            self.log("Layer CRS is WGS 84 (EPSG:4326). No coordinate transformation needed.")

        fields = [f.lower() for f in layer.fields]
        self.log(f"Shapefile attribute fields: {', '.join(layer.fields)}")

        records_to_create = []

        with transaction.atomic():
            if self.mode == 'REPLACE':
                deleted_count, _ = Hospital.objects.all().delete()
                self.log(f"REPLACE mode: Deleted {deleted_count} existing hospital records.")

            for i, feat in enumerate(layer):
                geom = feat.geom
                if not geom:
                    continue

                if coord_transform:
                    geom.transform(coord_transform)

                if geom.geom_type.name not in ('Point', 'MultiPoint'):
                    self.log(f"Skipping feature {i}: geometry is {geom.geom_type.name}, expected Point.")
                    continue

                # Point geometry
                point_geom = Point(geom.x, geom.y, srid=4326)

                # Attribute extraction
                feat_dict = {f.lower(): feat.get(f) for f in layer.fields}
                data = self._map_attributes(feat_dict, point_geom)

                if self.mode == 'UPDATE':
                    self._upsert_hospital(data)
                else:
                    records_to_create.append(Hospital(**data))

                self.imported_count += 1

            if records_to_create:
                Hospital.objects.bulk_create(records_to_create, batch_size=200)

    def _process_geojson(self, file_path):
        self.log("Processing GeoJSON file...")
        with open(file_path, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)

        features = geojson_data.get('features', [])
        self.log(f"Loaded GeoJSON with {len(features)} features.")

        records_to_create = []

        with transaction.atomic():
            if self.mode == 'REPLACE':
                deleted_count, _ = Hospital.objects.all().delete()
                self.log(f"REPLACE mode: Deleted {deleted_count} existing hospital records.")

            for i, feat in enumerate(features):
                geometry = feat.get('geometry')
                if not geometry or geometry.get('type') != 'Point':
                    continue

                coords = geometry.get('coordinates', [])
                if len(coords) < 2:
                    continue

                point_geom = Point(coords[0], coords[1], srid=4326)
                properties = {str(k).lower(): v for k, v in feat.get('properties', {}).items()}

                data = self._map_attributes(properties, point_geom)

                if self.mode == 'UPDATE':
                    self._upsert_hospital(data)
                else:
                    records_to_create.append(Hospital(**data))

                self.imported_count += 1

            if records_to_create:
                Hospital.objects.bulk_create(records_to_create, batch_size=200)

    def _process_csv(self, file_path):
        self.log("Processing CSV file...")
        records_to_create = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.log(f"Loaded CSV with {len(rows)} rows.")

        with transaction.atomic():
            if self.mode == 'REPLACE':
                deleted_count, _ = Hospital.objects.all().delete()
                self.log(f"REPLACE mode: Deleted {deleted_count} existing hospital records.")

            for i, row in enumerate(rows):
                norm_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

                lat_str = norm_row.get('latitude') or norm_row.get('lat') or norm_row.get('y')
                lng_str = norm_row.get('longitude') or norm_row.get('lng') or norm_row.get('lon') or norm_row.get('x')

                if not lat_str or not lng_str:
                    continue

                try:
                    lat = float(lat_str)
                    lng = float(lng_str)
                except ValueError:
                    continue

                point_geom = Point(lng, lat, srid=4326)
                data = self._map_attributes(norm_row, point_geom)

                if self.mode == 'UPDATE':
                    self._upsert_hospital(data)
                else:
                    records_to_create.append(Hospital(**data))

                self.imported_count += 1

            if records_to_create:
                Hospital.objects.bulk_create(records_to_create, batch_size=200)

    def _map_attributes(self, props, point_geom):
        name = self._find_field_value(props, self.NAME_ALIASES) or f"Hospital #{self.imported_count + 1}"
        address = self._find_field_value(props, self.ADDRESS_ALIASES) or ""
        specialty = self._find_field_value(props, self.SPECIALTY_ALIASES)
        phone = self._find_field_value(props, self.PHONE_ALIASES) or ""
        emergency_val = self._find_field_value(props, self.EMERGENCY_ALIASES)
        rating_val = self._find_field_value(props, self.RATING_ALIASES)
        hours = self._find_field_value(props, self.HOURS_ALIASES) or "24/7"
        website = self._find_field_value(props, self.WEBSITE_ALIASES) or ""

        # Default smart specialty inference from name if missing
        if not specialty:
            specialty = self._infer_specialty_from_name(name)

        # Emergency boolean conversion
        emergency_available = True
        if emergency_val is not None:
            val_str = str(emergency_val).strip().lower()
            emergency_available = val_str in ('1', 'true', 'yes', 'y', 't', 'available')

        # Rating float conversion
        rating = 4.5
        if rating_val is not None:
            try:
                rating = float(rating_val)
            except ValueError:
                pass

        return {
            'name': str(name)[:255],
            'address': str(address),
            'specialization': str(specialty),
            'location': point_geom,
            'phone': str(phone)[:100] if phone else None,
            'emergency_available': emergency_available,
            'opening_hours': str(hours)[:100],
            'rating': rating,
            'website': str(website) if website.startswith(('http://', 'https://')) else None,
        }

    def _find_field_value(self, props, aliases):
        for alias in aliases:
            for key, val in props.items():
                if key == alias or alias in key:
                    if val is not None and str(val).strip() != '':
                        return val
        return None

    def _infer_specialty_from_name(self, name):
        name_lower = name.lower()
        specs = []
        if 'heart' in name_lower or 'cardio' in name_lower or 'vascular' in name_lower:
            specs.append('Cardiology')
        if 'shishu' in name_lower or 'child' in name_lower or 'pediatric' in name_lower:
            specs.append('Pediatrics')
        if 'eye' in name_lower or 'vision' in name_lower or 'ophthal' in name_lower:
            specs.append('Ophthalmology')
        if 'kidney' in name_lower or 'renal' in name_lower or 'nephro' in name_lower:
            specs.append('Nephrology')
        if 'mental' in name_lower or 'psychiat' in name_lower:
            specs.append('Psychiatry & Neurology')
        if 'neuro' in name_lower or 'brain' in name_lower or 'spine' in name_lower:
            specs.append('Neurology & Spine')
        if 'ortho' in name_lower or 'trauma' in name_lower or 'bone' in name_lower:
            specs.append('Orthopedics & Trauma')
        if 'cancer' in name_lower or 'oncol' in name_lower:
            specs.append('Oncology')
        if 'mch' in name_lower or 'mother' in name_lower or 'mat' in name_lower or 'gyne' in name_lower:
            specs.append('Gynecology & Obstetrics')

        if not specs:
            specs.append('General Medicine')
        
        # Add emergency if prominent
        if 'emergency' not in [s.lower() for s in specs]:
            specs.append('Emergency 24/7')

        return ", ".join(specs)

    def _upsert_hospital(self, data):
        Hospital.objects.update_or_create(
            name=data['name'],
            defaults=data
        )
