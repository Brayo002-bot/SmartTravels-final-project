import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smarttravels.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.buses.models import Driver, Bus

User = get_user_model()

# Get Brian's user
user = User.objects.filter(email='odhiambo@gmail.com').first()
if user:
    print(f"User: {user.email}, role: {user.role}, company: {user.company}")
    
    # Check driver profile via property
    try:
        driver = user.driver_profile
        print(f"✓ Driver profile (via property): {driver.name}")
    except Exception as e:
        print(f"✗ Driver profile error: {e}")
    
    # Check direct query
    driver = Driver.objects.filter(user=user).first()
    if driver:
        buses = Bus.objects.filter(driver=driver)
        print(f"✓ Driver from DB: {driver.name}, bus count: {buses.count()}")
        for b in buses:
            print(f"  - Bus: {b.bus_number}")
    else:
        print("✗ No Driver found for user")
else:
    print("✗ User not found")
