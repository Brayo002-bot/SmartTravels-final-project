import json, logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Payment, MPesaService

logger = logging.getLogger(__name__)


@login_required
def checkout(request, booking_reference, booking_type='bus'):
    amount = request.GET.get('amount', 0)
    if request.method == 'POST':
        method = request.POST.get('method', 'mpesa')
        phone  = request.POST.get('phone', getattr(request.user, 'phone_number', '') or '')
        pay = Payment.objects.create(
            booking_reference=booking_reference,
            booking_type=booking_type,
            passenger=request.user,
            amount=amount,
            method=method,
            phone_number=phone,
        )
        if method == 'mpesa' and phone:
            try:
                svc = MPesaService()
                res = svc.stk_push(phone, amount, booking_reference)
                if res.get('ResponseCode') == '0':
                    pay.merchant_ref = res.get('CheckoutRequestID', '')
                    pay.save(update_fields=['merchant_ref'])
                    messages.success(request, '📱 M-Pesa push sent! Enter your PIN.')
                    return redirect('payment_pending', payment_id=pay.id)
                else:
                    pay.status = 'failed'
                    pay.save(update_fields=['status'])
                    messages.error(request, f"M-Pesa: {res.get('errorMessage','Please try again.')}")
            except Exception as e:
                logger.warning(f'M-Pesa STK failed: {e}')
                pay.status = 'failed'
                pay.save(update_fields=['status'])
                messages.warning(request, 'M-Pesa unavailable — payment saved as failed.')
            return render(request, 'payments/checkout.html', {
                'booking_reference': booking_reference,
                'booking_type': booking_type,
                'amount': amount,
            })
        pay.mark_completed()
        messages.success(request, f'✅ Payment for booking {booking_reference} recorded.')
        return redirect('payment_success', payment_id=pay.id)

    return render(request, 'payments/checkout.html', {
        'booking_reference': booking_reference,
        'booking_type': booking_type,
        'amount': amount,
    })


@login_required
def payment_pending(request, payment_id):
    pay = get_object_or_404(Payment, id=payment_id, passenger=request.user)
    return render(request, 'payments/pending.html', {'payment': pay})


@login_required
def payment_success(request, payment_id):
    pay = get_object_or_404(Payment, id=payment_id, passenger=request.user)
    return render(request, 'payments/success.html', {'payment': pay})


@csrf_exempt
def mpesa_callback(request):
    try:
        data = json.loads(request.body)
        stk  = data.get('Body', {}).get('stkCallback', {})
        cid  = stk.get('CheckoutRequestID', '')
        code = stk.get('ResultCode')
        pay  = Payment.objects.filter(merchant_ref=cid).first()
        if pay:
            if code == 0:
                items = {i['Name']: i.get('Value') for i in stk.get('CallbackMetadata', {}).get('Item', [])}
                pay.mark_completed(str(items.get('MpesaReceiptNumber', '')))
                _confirm_booking(pay.booking_reference, pay.booking_type, pay)
            else:
                pay.status = 'failed'
                pay.save(update_fields=['status'])
    except Exception as e:
        logger.error(f'Callback error: {e}')
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@login_required
def check_status(request, payment_id):
    pay = get_object_or_404(Payment, id=payment_id, passenger=request.user)
    return JsonResponse({'status': pay.status, 'code': pay.mpesa_code})


def _confirm_booking(ref, btype, pay=None):
    try:
        if btype == 'bus':
            from apps.buses.models import Booking
        elif btype == 'train':
            from apps.trains.models import Booking
        elif btype == 'flight':
            from apps.flights.models import Booking
        elif btype == 'parcel':
            from apps.parcels.models import Parcel
            p = Parcel.objects.filter(parcel_id=ref).first()
            if p:
                p.is_paid = True
                p.status = 'booked'
                p.save(update_fields=['is_paid','status'])
                from apps.parcels.models import ParcelLog
                ParcelLog.objects.create(parcel=p, status='paid', note='Payment received via MPesa', updated_by=None)
                # try sending a simple email receipt if settings configured
                try:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    send_mail(
                        f'Parcel Payment Received - {p.parcel_id}',
                        f'Your parcel {p.parcel_id} has been paid. Tracking ID: {p.parcel_id}',
                        settings.DEFAULT_FROM_EMAIL,
                        [p.sender.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
            return
        else:
            return
        b = Booking.objects.filter(booking_reference=ref).first()
        if b:
            b.status = 'confirmed'
            b.save(update_fields=['status'])
            try:
                from django.core.mail import send_mail
                from django.conf import settings as django_settings
                if pay and pay.passenger.email:
                    send_mail(
                        f'SmartTravels Ticket Confirmed - {b.booking_reference}',
                        (
                            f'Hello {b.passenger_name},\n\n'
                            f'Your booking {b.booking_reference} has been confirmed.\n'
                            f'Route: {b.route.from_location} → {b.route.to_location}\n'
                            f'Date: {b.travel_date} {b.travel_time or "TBD"}\n'
                            f'Seat: {b.seat_number or "Unassigned"}\n'
                            f'Price: KES {b.price:.2f}\n\n'
                            'Thank you for using SmartTravels. Please present this ticket at boarding.\n'
                        ),
                        django_settings.DEFAULT_FROM_EMAIL,
                        [pay.passenger.email],
                        fail_silently=True,
                    )
            except Exception:
                pass
    except Exception:
        pass
