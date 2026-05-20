from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import GPSPoint

@login_required
def live_tracking(request):
    return render(request, 'tracking/live.html')

@csrf_exempt
@login_required
def update_gps(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        GPSPoint.objects.create(
            driver=request.user,
            vehicle_id=data.get('vehicle_id', 0),
            vehicle_type=data.get('vehicle_type', 'bus'),
            latitude=data['lat'],
            longitude=data['lng'],
            speed_kmh=data.get('speed', 0),
        )
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'error': 'POST required'}, status=405)

@login_required
def get_vehicle_location(request, vehicle_type, vehicle_id):
    point = GPSPoint.objects.filter(vehicle_id=vehicle_id, vehicle_type=vehicle_type).first()
    if point:
        return JsonResponse({'lat': float(point.latitude), 'lng': float(point.longitude),
                             'speed': float(point.speed_kmh), 'time': point.recorded_at.isoformat()})
    return JsonResponse({'error': 'No GPS data'}, status=404)
