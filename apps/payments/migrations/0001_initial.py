from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_reference', models.CharField(max_length=30)),
                ('booking_type', models.CharField(default='bus', max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('method', models.CharField(choices=[('mpesa','M-Pesa'),('card','Card'),('cash','Cash'),('loyalty','Loyalty Points')], default='mpesa', max_length=10)),
                ('status', models.CharField(choices=[('pending','Pending'),('completed','Completed'),('failed','Failed'),('refunded','Refunded')], default='pending', max_length=10)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('mpesa_ref', models.CharField(blank=True, max_length=50)),
                ('mpesa_code', models.CharField(blank=True, max_length=30)),
                ('merchant_ref', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(null=True, blank=True)),
                ('passenger', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
