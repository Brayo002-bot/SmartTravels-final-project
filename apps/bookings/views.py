from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from apps.buses.models import Booking as BusBooking
from apps.trains.models import Booking as TrainBooking
from apps.flights.models import Booking as FlightBooking

@login_required
def my_bookings(request):
    name = request.user.get_full_name() or request.user.username
    bus_bookings    = BusBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]
    train_bookings  = TrainBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]
    flight_bookings = FlightBooking.objects.filter(passenger_name__icontains=name).order_by('-created_at')[:20]
    return render(request, 'passenger/bookings.html', {
        'bus_bookings': bus_bookings,
        'train_bookings': train_bookings,
        'flight_bookings': flight_bookings,
    })
