# 🚀 Quick Start Guide - Seat Reservation System

Get the seat system up and running in 5 minutes!

## Step 1: Run Database Migrations

```bash
cd /path/to/smarttravels

# Create migrations for new seat models
python manage.py makemigrations

# Apply migrations
python manage.py migrate
```

**Expected output:**
```
Applying systemadmin.0001_initial_seats...OK
```

## Step 2: Initialize Seat Templates

```bash
python manage.py init_seat_templates
```

This creates:
- ✓ Seat classes (Economy, Business, First Class, VIP, etc.)
- ✓ 4 Bus templates (14, 25, 33, 49-seater)
- ✓ 2 Train templates (Standard + Madaraka Express)
- ✓ 3 Flight templates (Narrow body, Regional, Wide body)

## Step 3: Generate Seats for Your First Vehicle

### For Buses:

```python
from apps.systemadmin.models import VehicleLayout, Seat, SeatClass
from apps.buses.models import Bus

# Get your bus
bus = Bus.objects.get(id=1)

# Get a pre-made template
layout = VehicleLayout.objects.get(template_name='49-Seater Dreamline Style')

# Generate seats for this bus
seats = []
for row in range(1, layout.rows + 1):
    for col_idx in range(1, layout.columns + 1):
        col_letter = chr(64 + col_idx)
        if col_idx != layout.aisle_position:  # Skip aisle
            seat_number = f"{row}{col_letter}"
            seat_class = SeatClass.objects.filter(name='normal', transport_type='bus').first()
            
            seat = Seat.objects.create(
                content_type='bus',
                vehicle_id=bus.id,
                seat_number=seat_number,
                seat_row=row,
                seat_column=col_letter,
                seat_class=seat_class,
                position_x=col_idx * 50,
                position_y=row * 60,
                price=seat_class.base_price,
                is_window=(col_idx == 1 or col_idx == layout.columns),
                status='available'
            )
            seats.append(seat)

print(f"Created {len(seats)} seats for bus {bus.bus_number}")
```

**Or use the API:**

```bash
curl -X POST http://localhost:8000/systemadmin/api/seats/generate/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $(grep 'csrftoken' cookies.txt | cut -d' ' -f7)" \
  -d '{
    "layout_id": 1,
    "vehicle_type": "bus",
    "vehicle_id": 1
  }'
```

## Step 4: Add Seat Selection to Booking Flow

In your booking view (e.g., `buses/views.py`):

```python
from django.shortcuts import render
from apps.buses.models import Bus
from apps.systemadmin.models import VehicleLayout

def select_seats(request):
    bus_id = request.GET.get('bus_id')
    travel_date = request.GET.get('date')
    
    bus = Bus.objects.get(id=bus_id)
    
    context = {
        'vehicle_type': 'bus',
        'vehicle_id': bus.id,
        'travel_date': travel_date,
        'travel_time': bus.schedules.first().travel_time if bus.schedules.exists() else '14:00'
    }
    
    return render(request, 'shared/seat_selection.html', context)
```

Add to `urls.py`:

```python
urlpatterns = [
    # ... existing urls ...
    path('seats/select/', views.select_seats, name='select_seats'),
]
```

Link from booking page:

```html
<a href="{% url 'select_seats' %}?bus_id={{ bus.id }}&date={{ travel_date }}" 
   class="btn btn-primary">
   Select Seats
</a>
```

## Step 5: Handle Payment & Confirm Booking

After successful payment:

```python
from apps.systemadmin.models import SeatReservation, SeatBooking
from apps.buses.models import Booking as BusBooking

@login_required
def confirm_payment(request):
    # Get selected seats from session
    reservations = SeatReservation.objects.filter(
        user=request.user,
        status='active'
    )
    
    # Create bus booking
    bus_booking = BusBooking.objects.create(
        passenger_name=request.POST.get('name'),
        phone=request.POST.get('phone'),
        bus_id=request.POST.get('bus_id'),
        travel_date=request.POST.get('travel_date'),
        price=sum(r.seat.price for r in reservations),
        status='confirmed'
    )
    
    # Confirm seat bookings
    for reservation in reservations:
        SeatBooking.objects.create(
            content_type='bus',
            booking_id=bus_booking.id,
            seat=reservation.seat,
            user=request.user,
            booking_reference=bus_booking.booking_reference,
            passenger_name=bus_booking.passenger_name,
            price_paid=reservation.seat.price,
            status='confirmed'
        )
        
        # Update seat status
        seat = reservation.seat
        seat.status = 'booked'
        seat.save()
        
        # Update reservation
        reservation.status = 'confirmed'
        reservation.save()
    
    return redirect('booking_confirmation', booking_id=bus_booking.id)
```

## Step 6: Access Admin Interface

### View Seats in Django Admin
```
http://localhost:8000/admin/systemadmin/seat/
```

### View Bookings
```
http://localhost:8000/admin/systemadmin/seatbooking/
```

### Monitor Reservations
```
http://localhost:8000/admin/systemadmin/seatreservation/
```

---

## 📊 Testing the System

### Test Seat Availability

```bash
python manage.py shell

from apps.systemadmin.models import Seat

# Get all available seats for a bus
available = Seat.objects.filter(content_type='bus', vehicle_id=1, status='available')
print(f"Available seats: {available.count()}")

# Get a specific seat
seat = Seat.objects.get(seat_number='1A', vehicle_id=1)
print(f"Seat {seat.seat_number}: {seat.status} - KES {seat.price}")
```

### Test Seat Reservation

```bash
python manage.py shell

from apps.systemadmin.models import Seat, SeatReservation
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()
user = User.objects.first()
seat = Seat.objects.filter(content_type='bus', status='available').first()

# Create reservation
res = SeatReservation.objects.create(
    user=user,
    seat=seat,
    reservation_token='test-token-123',
    expires_at=timezone.now() + timedelta(minutes=10),
    travel_date='2025-06-15'
)

# Update seat
seat.status = 'reserved'
seat.held_by = user
seat.held_until = res.expires_at
seat.save()

print(f"Seat {seat.seat_number} reserved until {res.expires_at}")
```

---

## 🎯 Next Steps

1. **Customize Colors**: Edit seat class colors in Django admin
2. **Add Pricing Rules**: Set different prices per seat class
3. **Create Templates**: Add custom layouts via admin builder
4. **Test Mobile**: Verify seat selection works on mobile devices
5. **Connect Payment**: Integrate with your payment system
6. **Set Up Analytics**: Monitor bookings and occupancy

---

## 📋 Checklist

- [ ] Migrations applied
- [ ] Templates initialized
- [ ] Seats generated for at least one vehicle
- [ ] Booking view connected to seat selection
- [ ] Payment confirmation triggers seat booking
- [ ] Admin can view seats and bookings
- [ ] Tested on desktop and mobile
- [ ] Seat selection appearing in booking flow

---

## 🆘 Common Issues & Solutions

### Issue: "Seat not found" error

**Solution:**
```bash
# Make sure seats are generated for your vehicle
python manage.py shell

from apps.systemadmin.models import Seat
seats = Seat.objects.filter(vehicle_id=1, content_type='bus')
print(f"Total seats: {seats.count()}")
```

### Issue: Reservation expires too quickly

**Solution:**
Edit in `seat_views.py`:
```python
def reserve_seat(request, seat_id):
    hold_duration = data.get('hold_duration_minutes', 10)  # Change to 15 or 20
```

### Issue: API returning 404

**Solution:**
1. Verify URL includes `/systemadmin/` prefix
2. Check user is authenticated (for some endpoints)
3. Verify seat/vehicle IDs exist

---

## 📞 Support

For detailed documentation, see: `SEAT_SYSTEM_README.md`

For API reference, see: `SEAT_SYSTEM_README.md` → "API Endpoints"

---

**Happy booking! 🎉**
