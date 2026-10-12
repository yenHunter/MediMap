from django.contrib import admin, messages
from django.contrib.gis import admin as gis_admin
from django.utils.html import format_html
from hospitals.models import Hospital, ShapefileUpload
from hospitals.services.shapefile_importer import ShapefileImporter


@admin.register(Hospital)
class HospitalAdmin(gis_admin.GISModelAdmin):
    list_display = (
        'name',
        'specialization_short',
        'phone',
        'emergency_badge',
        'rating',
        'latitude_display',
        'longitude_display',
    )
    list_filter = ('emergency_available',)
    search_fields = ('name', 'specialization', 'address', 'phone')
    ordering = ('name',)
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,
            'default_lon': 90.40,
            'default_lat': 23.77,
        }
    }

    def specialization_short(self, obj):
        if not obj.specialization:
            return '-'
        return obj.specialization[:60] + ('...' if len(obj.specialization) > 60 else '')
    specialization_short.short_description = 'Specialization'

    def emergency_badge(self, obj):
        if obj.emergency_available:
            return format_html(
                '<span style="background-color: #fee2e2; color: #dc2626; padding: 2px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">24/7 YES</span>'
            )
        return format_html(
            '<span style="background-color: #f3f4f6; color: #6b7280; padding: 2px 8px; border-radius: 9999px; font-size: 11px;">NO</span>'
        )
    emergency_badge.short_description = 'Emergency'

    def latitude_display(self, obj):
        return f"{obj.latitude:.5f}" if obj.latitude else "-"
    latitude_display.short_description = 'Latitude'

    def longitude_display(self, obj):
        return f"{obj.longitude:.5f}" if obj.longitude else "-"
    longitude_display.short_description = 'Longitude'


@admin.register(ShapefileUpload)
class ShapefileUploadAdmin(admin.ModelAdmin):
    list_display = (
        'filename',
        'uploaded_at',
        'mode',
        'status_badge',
        'records_imported',
        'uploaded_by',
    )
    list_filter = ('status', 'mode', 'uploaded_at')
    readonly_fields = ('uploaded_at', 'status', 'records_imported', 'log_display')
    fields = ('file', 'mode', 'uploaded_by', 'uploaded_at', 'status', 'records_imported', 'log_display')

    def filename(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return '-'
    filename.short_description = 'Uploaded File'

    def status_badge(self, obj):
        if obj.status == 'SUCCESS':
            return format_html(
                '<span style="background-color: #dcfce7; color: #16a34a; padding: 3px 10px; border-radius: 9999px; font-weight: bold; font-size: 11px;">SUCCESS</span>'
            )
        elif obj.status == 'FAILED':
            return format_html(
                '<span style="background-color: #fee2e2; color: #dc2626; padding: 3px 10px; border-radius: 9999px; font-weight: bold; font-size: 11px;">FAILED</span>'
            )
        return format_html(
            '<span style="background-color: #fef9c3; color: #ca8a04; padding: 3px 10px; border-radius: 9999px; font-weight: bold; font-size: 11px;">PENDING</span>'
        )
    status_badge.short_description = 'Status'

    def log_display(self, obj):
        if not obj.log:
            return "(No execution log available yet)"
        return format_html(
            '<pre style="background: #111827; color: #38bdf8; padding: 12px; border-radius: 8px; max-height: 300px; overflow-y: auto; font-family: monospace; font-size: 12px; line-height: 1.4;">{}</pre>',
            obj.log
        )
    log_display.short_description = 'Ingestion Logs'

    def save_model(self, request, obj, form, change):
        if not obj.uploaded_by and request.user.is_authenticated:
            obj.uploaded_by = request.user

        super().save_model(request, obj, form, change)

        # Trigger ingestion automatically when file is saved
        try:
            importer = ShapefileImporter(obj)
            importer.run()
            messages.success(
                request,
                f"Successfully processed {obj.file.name}! {obj.records_imported} hospital records updated in PostGIS."
            )
        except Exception as e:
            messages.error(
                request,
                f"Error processing shapefile: {str(e)}. Check the ingestion logs for details."
            )
