from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import apps.parcels.models

class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name='Parcel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('parcel_id', models.CharField(default=apps.parcels.models.parcel_id, max_length=20, unique=True)),
                ('sender_name', models.CharField(max_length=150)),
                ('sender_phone', models.CharField(max_length=20)),
                ('recipient_name', models.CharField(max_length=150)),
                ('recipient_phone', models.CharField(max_length=20)),
                ('origin', models.CharField(max_length=100)),
                ('destination', models.CharField(max_length=100)),
                ('category', models.CharField(choices=[('documents','Documents'),('electronics','Electronics'),('clothing','Clothing'),('food','Food/Perishables'),('fragile','Fragile'),('other','Other')], default='other', max_length=20)),
                ('description', models.TextField()),
                ('weight_kg', models.DecimalField(decimal_places=2, default=1, max_digits=6)),
                ('declared_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('shipping_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('is_fragile', models.BooleanField(default=False)),
                ('is_paid', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('booked','Booked'),('dropped_off','Dropped Off'),('in_transit','In Transit'),('arrived','Arrived'),('collected','Collected'),('returned','Returned')], default='booked', max_length=20)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_parcels', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ParcelLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(max_length=20)),
                ('note', models.TextField(blank=True)),
                ('location', models.CharField(blank=True, max_length=100)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('parcel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='parcels.parcel')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['timestamp']},
        ),
    ]
