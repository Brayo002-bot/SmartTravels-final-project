import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('buses', '0003_schedule'),
    ]

    operations = [
        migrations.AddField(
            model_name='schedule',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
