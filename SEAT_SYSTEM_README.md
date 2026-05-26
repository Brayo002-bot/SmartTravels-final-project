# 🎫 Smart Travels Seat Reservation System

A production-ready, interactive seat reservation system for buses, trains, and flights with real-time updates, dynamic pricing, and comprehensive admin controls.

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Database Models](#database-models)
- [API Endpoints](#api-endpoints)
- [Frontend Components](#frontend-components)
- [Integration Guide](#integration-guide)
- [Admin Configuration](#admin-configuration)
- [Usage Examples](#usage-examples)

---

## ✨ Features

### For Passengers
- **Interactive Seat Maps** - Real-time, visually-realistic seat selection
- **Multi-Mode Support** - Buses, trains, and flights with specific layouts
- **Seat Holds** - 10-minute temporary holds during checkout
- **Dynamic Pricing** - Different prices for different seat classes
- **Visual Indicators** - Color-coded seat statuses (Available, Booked, Reserved, Blocked)
- **Mobile Responsive** - Full support for mobile and desktop booking
- **Cabin Navigation** - For trains: switch between cabins/coaches
- **Group Booking** - Select up to 8 seats per booking

### For Admins
- **Layout Templates** - Pre-configured templates for common vehicle types
- **Drag-and-Drop Builder** - Create custom seat layouts
- **Bulk Seat Generation** - Auto-generate seats from template
- **Class Management** - Configure seat classes and pricing
- **Occupancy Analytics** - Real-time booking statistics
- **QR Code Tracking** - For check-in verification
- **Seat Locking** - Prevent double-bookings

### Technical Features
- **Real-Time Updates** - Live seat status synchronization
- **Transaction Safety** - Prevents double-booking with database locks
- **Reservation Hold Timer** - Automatic hold expiration
- **Audit Trail** - Complete booking and modification history
- **API-Driven** - RESTful API for flexible integration

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│        Passenger Frontend                        │
│   (Seat Selection UI - Interactive Map)         │
└──────────────────────┬──────────────────────────┘
                       │ HTTP/AJAX
┌──────────────────────▼──────────────────────────┐
│        Django REST API                           │
│   (systemadmin/seat_views.py)                   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│        Database Layer                            │
│   (SeatClass, VehicleLayout, Seat, etc.)       │
└─────────────────────────────────────────────────┘
```

---

## 📊 Database Models

### Core Models

#### `SeatClass`
Defines seat types and pricing for each transport mode

```python
- name: 'economy', 'business', 'first_class', 'vip', etc.
- transport_type: 'bus', 'train', 'flight'
- display_name: 'Economy Seat'
- base_price: Decimal (e.g., 1200 KES)
- color_code: Hex color for UI
- icon: Icon representation
```

#### `VehicleLayout`
Template for vehicle seating arrangements

```python
- company: ForeignKey to Company
- vehicle_type: 'bus', 'train', 'flight'
- template_name: 'Dreamline VIP 49-Seater'
- total_seats: Integer
- rows, columns, aisle_position: Layout dimensions
- cabins: JSON (for trains)
- emergency_exits, lavatories: JSON (for flights)
- layout_data: Complete configuration as JSON
```

#### `Seat`
Individual seat record

```python
- content_type: 'bus'|'train'|'flight' (vehicle type)
- vehicle_id: Link to specific bus/train/flight
- seat_number: '1A', '12B', etc.
- seat_row, seat_column: Numeric position
- seat_class: ForeignKey to SeatClass
- price: Decimal (inherits from class, customizable)
- status: 'available'|'booked'|'reserved'|'blocked'
- is_extra_legroom, is_window, is_aisle, etc.: Features
- held_until, held_by: Reservation tracking
```

#### `SeatReservation`
Temporary seat holds during checkout

```python
- user: ForeignKey to User
- seat: ForeignKey to Seat
- reservation_token: UUID for API tracking
- status: 'active'|'confirmed'|'released'|'expired'
- held_at, expires_at: Time tracking
- travel_date, travel_time: Booking context
```

#### `SeatBooking`
Links seats to actual bookings

```python
- booking_id, content_type: Link to bus/train/flight booking
- seat: ForeignKey to Seat
- booking_reference: '123ABC'
- status: 'pending'|'confirmed'|'checked_in'|'cancelled'
- price_paid: Final price
- passenger_name, phone, ID: Passenger info
- qr_code: For check-in verification
- is_checked_in, checked_in_at: Check-in tracking
```

---

## 🔌 API Endpoints

All endpoints are under `/systemadmin/api/seats/`

### Seat Information

```
GET /api/seats/vehicle/<type>/<vehicle_id>/<date>/
```
Get all seats for a vehicle on a specific date with statuses

**Response:**
```json
{
  "vehicle_id": 1,
  "vehicle_type": "bus",
  "travel_date": "2025-06-15",
  "total_seats": 49,
  "layout": { "rows": 7, "columns": 7, "aisle_position": 4 },
  "seats": [
    {
      "id": 123,
      "seat_number": "1A",
      "status": "available",
      "price": 1200,
      "class": "normal",
      "color": "#2ecc71",
      "features": { "window": true, "extra_legroom": false }
    }
  ],
  "summary": { "available": 40, "booked": 5, "reserved": 2, "blocked": 2 }
}
```

### Reserve Seat

```
POST /api/seats/<seat_id>/reserve/
```
Hold a seat temporarily

**Request:**
```json
{
  "hold_duration_minutes": 10,
  "travel_date": "2025-06-15",
  "travel_time": "14:30"
}
```

**Response:**
```json
{
  "success": true,
  "reservation_token": "uuid-string",
  "expires_at": "2025-06-15T14:40:00Z",
  "seat": { "id": 123, "seat_number": "1A", "price": 1200 }
}
```

### Confirm Booking

```
POST /api/seats/confirm-booking/
```
Finalize seat booking after payment

**Request:**
```json
{
  "reservation_token": "uuid-string",
  "booking_id": 456,
  "booking_reference": "BK123456",
  "content_type": "bus",
  "passenger_name": "John Doe",
  "passenger_phone": "0712345678",
  "passenger_id": "12345678",
  "price_paid": 1200
}
```

### Release Seat

```
POST /api/seats/<seat_id>/release/
```
Cancel a seat hold

### List Templates

```
GET /api/seats/templates/<vehicle_type>/
```
Get available layout templates

---

## 🎨 Frontend Components

### 1. Seat Selection Interface (`templates/shared/seat_selection.html`)

**Features:**
- Interactive seat map with real-time updates
- Vehicle-specific layouts (Bus, Train, Flight)
- Cabin tabs for trains
- Cockpit illustration for flights
- Color-coded seat statuses
- Booking summary panel
- Automatic hold expiration timer
- Mobile responsive

**Usage:**
```html
{% include 'shared/seat_selection.html' %}
```

**Context Variables:**
```python
{
    'vehicle_type': 'bus',  # or 'train', 'flight'
    'vehicle_id': 1,
    'travel_date': '2025-06-15',
    'travel_time': '14:30'
}
```

### 2. Seat Layout Builder (`templates/system_admin/seat_layout_builder.html`)

**Features:**
- 4-step guided configuration
- Template selector
- Custom layout editor
- Seat class assignment
- Live preview
- Save as reusable template

---

## 🔧 Integration Guide

### Step 1: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Initialize Templates

```bash
python manage.py init_seat_templates
```

### Step 3: Generate Seats for a Vehicle

Call the generation API:

```bash
curl -X POST http://localhost:8000/systemadmin/api/seats/generate/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <token>" \
  -d '{
    "layout_id": 1,
    "vehicle_type": "bus",
    "vehicle_id": 1
  }'
```

### Step 4: Integrate with Booking Flow

Add to your booking view:

```python
from apps.systemadmin.models import VehicleLayout

def bus_booking(request):
    # ... existing code ...
    
    vehicle_id = request.GET.get('bus_id')
    travel_date = request.GET.get('date')
    
    # Get layout template
    layout = VehicleLayout.objects.filter(
        vehicle_type='bus',
        is_template=True
    ).first()
    
    context = {
        'vehicle_type': 'bus',
        'vehicle_id': vehicle_id,
        'travel_date': travel_date,
        'layout': layout,
    }
    
    return render(request, 'shared/seat_selection.html', context)
```

### Step 5: Handle Payment Integration

After payment confirmation:

```python
from apps.systemadmin.models import SeatReservation, SeatBooking

@login_required
def confirm_payment(request):
    seat_ids = request.session.get('selected_seats', [])
    
    for reservation in SeatReservation.objects.filter(
        user=request.user,
        status='active'
    ):
        SeatBooking.objects.create(
            content_type='bus',
            booking_id=booking.id,
            seat=reservation.seat,
            user=request.user,
            booking_reference=booking.booking_reference,
            passenger_name=booking.passenger_name,
            price_paid=booking.price,
            status='confirmed'
        )
        
        # Mark seat as booked
        reservation.seat.status = 'booked'
        reservation.seat.save()
        
        reservation.status = 'confirmed'
        reservation.save()
    
    return redirect('booking_confirmation')
```

---

## 👨‍💼 Admin Configuration

### Creating a Seat Layout

1. **Access Admin Panel**
   ```
   /admin/systemadmin/vehiclelayout/
   ```

2. **Create New Layout**
   - Click "Add Vehicle Layout"
   - Select company and vehicle type
   - Choose aisle arrangement
   - Configure dimensions

3. **Generate Seats**
   - After creating layout
   - Call `/systemadmin/api/seats/generate/`
   - Seats are auto-created with proper numbering

### Configuring Seat Classes

1. **Access Seat Class Admin**
   ```
   /admin/systemadmin/seatclass/
   ```

2. **Define Classes**
   - Economy/Normal: Base price
   - Business: Premium price
   - First Class: Luxury price
   - Set color codes for UI

### Monitoring Occupancy

View seat status in real-time:

```python
from apps.systemadmin.models import Seat
from django.db.models import Count

# Get occupancy stats
stats = Seat.objects.filter(
    content_type='bus',
    vehicle_id=1
).values('status').annotate(count=Count('status'))

# Example output:
# {'status': 'available', 'count': 40}
# {'status': 'booked', 'count': 8}
# {'status': 'reserved', 'count': 1}
```

---

## 📝 Usage Examples

### Example 1: Bus Booking Flow

```python
# 1. User selects bus and date
bus = Bus.objects.get(id=1)
travel_date = '2025-06-15'

# 2. Display seat map
context = {
    'vehicle_type': 'bus',
    'vehicle_id': bus.id,
    'travel_date': travel_date,
}
render(request, 'shared/seat_selection.html', context)

# 3. User selects seats (JavaScript handles this)
# 4. Seats are held for 10 minutes

# 5. After payment
booking = Booking.objects.create(
    passenger_name='John Doe',
    bus=bus,
    travel_date=travel_date,
    price=2400,  # 2 seats × 1200
    status='pending'
)

# 6. Confirm seat bookings via API
```

### Example 2: Train Booking with Cabins

```python
# Train layout with cabins
train_layout = VehicleLayout.objects.create(
    vehicle_type='train',
    template_name='Madaraka Express',
    total_seats=200,
    cabins=[
        {'name': 'First Class', 'class': 'first_class', 'rows': 20},
        {'name': 'Standard', 'class': 'business', 'rows': 30},
    ]
)

# Generate seats with cabin mapping
generate_vehicle_seats(
    layout=train_layout,
    vehicle_id=1,
    cabin_mappings={
        'First Class': {'class': 'first_class', 'rows': 20},
        'Standard': {'class': 'business', 'rows': 30},
    }
)

# Passengers see cabin tabs and select seats within cabins
```

### Example 3: Flight Booking with Emergency Exits

```python
# Flight layout with emergency exits
flight_layout = VehicleLayout.objects.create(
    vehicle_type='flight',
    template_name='A320 Standard',
    total_seats=180,
    rows=30,
    columns=6,
    emergency_exits=4,
    lavatory_locations=['front', 'rear']
)

# Seats can be marked as emergency exit rows
seat = Seat.objects.create(
    seat_number='15A',
    seat_row=15,
    seat_column='A',
    is_emergency_exit_row=True,
    price=8500  # Extra charge for exit row
)
```

---

## 🚀 Performance Optimization

### Database Indexes
The system includes indexes on:
- `Seat`: `(content_type, vehicle_id, status)`
- `SeatReservation`: `(user, status)`, `(expires_at)`
- `SeatBooking`: `(booking_reference)`, `(status)`

### Caching Strategy
```python
from django.core.cache import cache

# Cache seat availability
def get_cached_seats(vehicle_type, vehicle_id, date):
    cache_key = f'seats_{vehicle_type}_{vehicle_id}_{date}'
    seats = cache.get(cache_key)
    
    if not seats:
        seats = Seat.objects.filter(
            content_type=vehicle_type,
            vehicle_id=vehicle_id
        )
        cache.set(cache_key, seats, 300)  # 5 min cache
    
    return seats
```

### Real-Time Updates with WebSockets (Future)
```python
# Optional: Add Django Channels for real-time updates
# When a seat status changes, broadcast to all connected clients
```

---

## 🐛 Troubleshooting

### Seats Not Appearing
- Verify layout template exists
- Run `init_seat_templates` command
- Check seat_vehicle relationships

### Hold Expiration Issues
- Ensure `held_until` is set correctly
- Check background task runner
- Verify timezone settings in Django

### Double Booking Prevention
- Use database transaction with SELECT FOR UPDATE
- Verify reservation token uniqueness
- Check payment confirmation logic

---

## 📱 Mobile Responsiveness

The seat selection UI is fully responsive:
- Horizontal scroll for large seat maps
- Touch-friendly seat controls
- Collapsible cabin tabs
- Summary panel stacks on mobile

---

## 🔐 Security Considerations

1. **Authentication**: All operations require login
2. **Authorization**: Staff-only for admin operations
3. **CSRF Protection**: All POST requests require CSRF token
4. **Rate Limiting**: Consider adding to prevent abuse
5. **Audit Trail**: All changes logged in AuditLog

---

## 📊 Analytics & Reporting

```python
# Get booking statistics
from django.db.models import Count, Sum
from apps.systemadmin.models import SeatBooking

stats = SeatBooking.objects.filter(
    status='confirmed'
).aggregate(
    total_bookings=Count('id'),
    total_revenue=Sum('price_paid'),
    avg_price=Avg('price_paid')
)

# Get most popular seats
popular_seats = SeatBooking.objects.filter(
    status='confirmed'
).values('seat__seat_class__name').annotate(
    count=Count('id')
).order_by('-count')
```

---

## 📞 Support & Contributions

For issues, feature requests, or contributions, please contact the development team.

---

**Last Updated:** May 2026  
**Version:** 1.0.0  
**Status:** Production Ready ✓
