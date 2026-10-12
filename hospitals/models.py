from django.contrib.gis.db import models as gis_models
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Hospital(gis_models.Model):
    name = models.CharField(max_length=255, db_index=True)
    address = models.TextField(blank=True, default='')
    specialization = models.TextField(
        help_text="Comma-separated specializations e.g. Cardiology, Neurology, Pediatrics, Emergency 24/7",
        default="General Medicine"
    )
    location = gis_models.PointField(srid=4326, spatial_index=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    emergency_available = models.BooleanField(default=True, db_index=True)
    opening_hours = models.CharField(max_length=100, default="24/7")
    rating = models.FloatField(default=4.5)
    website = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Hospital'
        verbose_name_plural = 'Hospitals'

    def __str__(self):
        return self.name

    @property
    def latitude(self):
        return self.location.y if self.location else None

    @property
    def longitude(self):
        return self.location.x if self.location else None

    @property
    def specializations_list(self):
        if not self.specialization:
            return []
        return [s.strip() for s in self.specialization.split(',') if s.strip()]


class ShapefileUpload(models.Model):
    MODE_CHOICES = (
        ('REPLACE', 'Replace all existing records (Weekly Full Refresh)'),
        ('UPDATE', 'Update & Append records'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    )

    file = models.FileField(
        upload_to='shapefiles/%Y/%m/',
        help_text="Upload ArcGIS export as .ZIP (containing .shp, .shx, .dbf, .prj) or .GeoJSON / .CSV"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='REPLACE')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    records_imported = models.PositiveIntegerField(default=0)
    log = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Shapefile Upload'
        verbose_name_plural = 'Shapefile Uploads'

    def __str__(self):
        filename = self.file.name.split('/')[-1] if self.file else 'Upload'
        return f"{filename} ({self.get_status_display()} - {self.uploaded_at.strftime('%Y-%m-%d %H:%M')})"
