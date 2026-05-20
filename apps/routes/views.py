from django.shortcuts import render
from apps.buses.models import Route as BusRoute
from apps.trains.models import Route as TrainRoute
from apps.flights.models import Route as FlightRoute

def all_routes(request):
    return render(request, 'routes/all.html', {
        'bus_routes': BusRoute.objects.all(),
        'train_routes': TrainRoute.objects.all(),
        'flight_routes': FlightRoute.objects.all(),
    })
