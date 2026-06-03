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
        payments = Payment.objects.filter(passenger=request.user).exclude(method='loyalty')
        payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
        earned_points = int(payment_total / 100)  # 1 point per 100 KSH spent
        redeemed_points = getattr(request.user, 'redeemed_points', 0) or 0
        available_points = max(earned_points - redeemed_points, 0)
    except Exception:
        available_points = 0

    return render(request, 'passenger/bookings.html', {
        'bus_bookings': bus_bookings,
        'train_bookings': train_bookings,
        'flight_bookings': flight_bookings,
        'loyalty_points': f"{available_points:,}",
    })
