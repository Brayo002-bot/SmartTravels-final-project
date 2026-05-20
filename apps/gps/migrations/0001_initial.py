from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='GPSPoint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('vehicle_id', models.PositiveIntegerField()),
                ('vehicle_type', models.CharField(default='bus', max_length=10)),
                ('latitude', models.DecimalField(decimal_places=7, max_digits=10)),
                ('longitude', models.DecimalField(decimal_places=7, max_digits=10)),
                ('speed_kmh', models.DecimalField(decimal_places=1, default=0, max_digits=5)),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gps_points', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-recorded_at']},
        ),
    ]
