from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum
from apps.buses.models import Booking as BusBooking
from apps.trains.models import Booking as TrainBooking
from apps.flights.models import Booking as FlightBooking

@login_required
def my_bookings(request):
    name = request.user.get_full_name() or request.user.username
    bus_bookings    = BusBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]
    train_bookings  = TrainBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]
    flight_bookings = FlightBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]

    # Compute loyalty points for display (same logic as passenger_loyalty)
    try:
        from apps.payments.models import Payment
        payments = Payment.objects.filter(passenger=request.user)
        payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
        point_balance = payments.count() * 100 + int(payment_total)
    except Exception:
        point_balance = 0

    return render(request, 'passenger/bookings.html', {
        'bus_bookings': bus_bookings,
        'train_bookings': train_bookings,
        'flight_bookings': flight_bookings,
        'loyalty_points': f"{point_balance:,}",
    })
