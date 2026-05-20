# Generated manually for schedule model addition

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trains', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Schedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('travel_date', models.DateField()),
                ('travel_time', models.TimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('train', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='schedules', to='trains.train')),
            ],
        ),
    ]
