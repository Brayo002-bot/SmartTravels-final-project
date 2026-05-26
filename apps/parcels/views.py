from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import Parcel, ParcelLog
from apps.payments.models import Payment


@login_required
def parcel_view(request):
    """Combined parcel page: book + track + my parcels."""
    # Handle track query
    track_query   = request.GET.get('track_id', '').strip().upper()
    tracked_parcel = None
    tracked_logs   = []
    if track_query:
        tracked_parcel = Parcel.objects.filter(parcel_id=track_query).first()
        if tracked_parcel:
            tracked_logs = tracked_parcel.logs.all()

    # Handle POST (book parcel)
    if request.method == 'POST':
        p = Parcel(
            sender=request.user,
            sender_name=request.POST.get('sender_name', request.user.get_full_name()),
            sender_phone=request.POST.get('sender_phone', ''),
            recipient_name=request.POST.get('recipient_name', ''),
            recipient_phone=request.POST.get('recipient_phone', ''),
            origin=request.POST.get('origin', ''),
            destination=request.POST.get('destination', ''),
            category=request.POST.get('category', 'other'),
            description=request.POST.get('description', ''),
            weight_kg=request.POST.get('weight_kg', 1),
            declared_value=request.POST.get('declared_value', 0),
            is_fragile=request.POST.get('is_fragile') == 'on',
        )
        p.shipping_cost = p.calc_cost()
        p.save()
        ParcelLog.objects.create(
            parcel=p, status='booked',
            note='Booked online by passenger',
            updated_by=request.user
        )
        # Award loyalty points for parcel (1 point per 100 KSH spent)
        try:
            Payment.objects.create(
                passenger=request.user,
                amount=p.shipping_cost,
                method='parcel',
                reference=f'Parcel-{p.parcel_id}',
                status='completed'
            )
        except Exception as e:
            messages.warning(request, f'Parcel booked but loyalty points could not be awarded: {str(e)}')
        messages.success(request, f'Parcel {p.parcel_id} booked successfully! Cost: KES {p.shipping_cost}')
        return redirect('parcel')

    my_parcels = Parcel.objects.filter(sender=request.user).order_by('-created_at')

    return render(request, 'parcels/parcel.html', {
        'my_parcels': my_parcels,
        'track_query': track_query,
        'tracked_parcel': tracked_parcel,
        'tracked_logs': tracked_logs,
    })


def scan_parcel(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    parcel_id  = request.POST.get('parcel_id', '').upper()
    new_status = request.POST.get('status', 'arrived')
    parcel = Parcel.objects.filter(parcel_id=parcel_id).first()
    if not parcel:
        return JsonResponse({'valid': False, 'message': 'Parcel not found'})
    parcel.status = new_status
    parcel.save(update_fields=['status'])
    ParcelLog.objects.create(
        parcel=parcel, status=new_status,
        location=request.POST.get('location', ''),
        note='Scanned by staff', updated_by=request.user
    )
    return JsonResponse({'valid': True, 'parcel_id': parcel_id, 'status': parcel.get_status_display()})
