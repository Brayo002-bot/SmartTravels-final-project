from collections import Counter
from datetime import date, time, datetime
import io
import logging
import uuid

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.core.mail import EmailMessage
import base64
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.systemadmin.seat_layout import generate_seat_layout
try:
    import requests # Assuming requests is installed
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

from .forms import PassengerRegistrationForm

logger = logging.getLogger(__name__)
User = get_user_model()


def _send_ticket_email(recipient_email, booking):
    try:
        ticket_data = _generate_ticket_pdf(booking)
        subject = f"SmartTravels Ticket {booking.booking_reference}"
        message = (
            f"Hello {booking.passenger_name},\n\n"
            f"Thank you for booking with SmartTravels. Attached is your ticket for your upcoming journey.\n\n"
            f"Booking Reference: {booking.booking_reference}\n"
            f"Route: {booking.route.from_location} → {booking.route.to_location}\n"
            f"Travel Date: {booking.travel_date}\n"
            f"Seat: {booking.seat_number or 'Unassigned'}\n\n"
            "Please keep this ticket for boarding.\n\n"
            "Safe travels,\n"
            "SmartTravels Team"
        )
        email = EmailMessage(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient_email])
        file_ext = 'pdf' if REPORTLAB_AVAILABLE else 'txt'
        content_type = 'application/pdf' if REPORTLAB_AVAILABLE else 'text/plain'
        email.attach(f'ticket_{booking.booking_reference}.{file_ext}', ticket_data, content_type)
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        logger.warning(f"Unable to send ticket email to {recipient_email}: {exc}")
        return False


def get_dashboard_template_for_role(role):
    role_templates = {
        'passenger': 'passenger/dashboard.html',
        'driver': 'driver/driver.html',
        'bus_admin': 'bus_admin/dashboard.html',
        'flight_admin': 'flight_admin/dashboard.html',
        'train_admin': 'train_admin/dashboard.html',
        'technical_staff': 'technical_staff/tech_dashboard.html',
        'admin': 'system_admin/dashboard.html',
    }
    return role_templates.get(role)


@login_required
def dashboard_view(request):
    if request.user.role == 'bus_admin':
        return redirect('bus_dashboard')
    elif request.user.role == 'technical_staff':
        return redirect('tech_dashboard')
    elif request.user.role in ['flight_admin', 'train_admin']:
        # Check if admin has a company assigned
        if hasattr(request.user, 'company') and request.user.company:
            # Redirect to company-specific dashboard
            if request.user.role == 'flight_admin':
                return redirect('flight_dashboard')
            elif request.user.role == 'train_admin':
                return redirect('train_dashboard')
        else:
            # No company assigned, show message or redirect to setup
            return render(request, 'auth/no_company_assigned.html', {
                'user_role': request.user.get_role_display(),
            })

    template_name = get_dashboard_template_for_role(request.user.role)
    if not template_name:
        return render(
            request,
            'auth/permission_denied.html',
            {
                'user_role': request.user.role or 'unassigned',
            },
            status=403,
        )

    if request.user.role == 'passenger':
        from apps.buses.models import Booking as BusBooking, Route as BusRoute, Schedule as BusSchedule
        from apps.flights.models import Booking as FlightBooking, Route as FlightRoute, Schedule as FlightSchedule
        from apps.trains.models import Booking as TrainBooking, Route as TrainRoute, Schedule as TrainSchedule

        query_from = request.GET.get('from', '').strip()
        query_to = request.GET.get('to', '').strip()
        query_date = request.GET.get('date', '').strip()
        query_mode = request.GET.get('mode', '').strip().lower()
        query_time = request.GET.get('time', '').strip().lower()

        from_choices = set()
        to_choices = set()
        for route in BusRoute.objects.all():
            from_choices.add(route.from_location)
            to_choices.add(route.to_location)
        for route in TrainRoute.objects.all():
            from_choices.add(route.from_location)
            to_choices.add(route.to_location)
        for route in FlightRoute.objects.all():
            from_choices.add(route.from_location)
            to_choices.add(route.to_location)

        from_choices = sorted(from_choices)
        to_choices = sorted(to_choices)

        # Recommendation data from historical bookings and active schedules
        bus_bookings = BusBooking.objects.count()
        train_bookings = TrainBooking.objects.count()
        flight_bookings = FlightBooking.objects.count()
        mode_counts = {
            'bus': bus_bookings,
            'train': train_bookings,
            'flight': flight_bookings,
        }
        most_used_mode = max(mode_counts, key=mode_counts.get) if any(mode_counts.values()) else 'bus'
        top_modes = [mode for mode, count in sorted(mode_counts.items(), key=lambda x: x[1], reverse=True) if count > 0]

        route_counts = Counter()
        for route_from, route_to in BusBooking.objects.values_list('route__from_location', 'route__to_location'):
            route_counts[f'{route_from} → {route_to}'] += 1
        for route_from, route_to in TrainBooking.objects.values_list('route__from_location', 'route__to_location'):
            route_counts[f'{route_from} → {route_to}'] += 1
        for route_from, route_to in FlightBooking.objects.values_list('route__from_location', 'route__to_location'):
            route_counts[f'{route_from} → {route_to}'] += 1

        top_routes = [{'route': route, 'count': count} for route, count in route_counts.most_common(3)]
        recommended_route = top_routes[0]['route'] if top_routes else None

        prices = list(BusRoute.objects.values_list('price', flat=True)) + list(TrainRoute.objects.values_list('price', flat=True)) + list(FlightRoute.objects.values_list('price', flat=True))
        price_range = None
        average_price = None
        unique_prices = None
        if prices:
            numeric_prices = [float(price) for price in prices]
            price_range = (min(numeric_prices), max(numeric_prices))
            average_price = sum(numeric_prices) / len(numeric_prices)
            unique_prices = sorted(set(numeric_prices))

        top_companies = User.objects.filter(
            role__in=['bus_admin', 'train_admin', 'flight_admin'],
            company__isnull=False
        ).values('company__name').annotate(count=Count('id')).order_by('-count')[:3]
        most_used_companies = [company['company__name'] for company in top_companies]

        search_performed = bool(query_from or query_to or query_date or query_mode or query_time)
        trips = []

        if query_from and query_to and query_date:
            try:
                travel_date = datetime.strptime(query_date, '%Y-%m-%d').date()
            except ValueError:
                travel_date = None

            if travel_date:
                time_filters = None
                if query_time == 'morning':
                    time_filters = Q(travel_time__gte=time(5, 0), travel_time__lte=time(11, 59))
                elif query_time == 'afternoon':
                    time_filters = Q(travel_time__gte=time(12, 0), travel_time__lte=time(16, 59))
                elif query_time == 'evening':
                    time_filters = Q(travel_time__gte=time(17, 0), travel_time__lte=time(20, 59))
                elif query_time == 'night':
                    time_filters = Q(travel_time__gte=time(21, 0)) | Q(travel_time__lte=time(4, 59))

                def build_trip(schedule, mode_name):
                    transport = schedule.bus if mode_name == 'bus' else schedule.train if mode_name == 'train' else schedule.flight
                    return {
                        'mode': mode_name,
                        'from_location': transport.route.from_location,
                        'to_location': transport.route.to_location,
                        'departure_time': schedule.travel_time,
                        'available_seats': transport.available_seats,
                        'price': transport.route.price,
                        'schedule_id': schedule.id,
                        'company_name': transport.company.name if transport.company else "Unknown",
                        'company_logo': transport.company.logo_image.url if transport.company and transport.company.logo_image else None,
                        'company_description': transport.company.description if transport.company else "",
                        'transport_description': transport.description or "",
                        'transport_name': transport.bus_number if mode_name == 'bus' else transport.train_number if mode_name == 'train' else transport.flight_number,
                    }

                if query_mode in ['', 'bus']:
                    bus_schedules = BusSchedule.objects.filter(
                        bus__route__from_location__iexact=query_from,
                        bus__route__to_location__iexact=query_to,
                        travel_date=travel_date,
                    )
                    if time_filters is not None:
                        bus_schedules = bus_schedules.filter(time_filters)
                    trips.extend([build_trip(schedule, 'bus') for schedule in bus_schedules])

                if query_mode in ['', 'train']:
                    train_schedules = TrainSchedule.objects.filter(
                        train__route__from_location__iexact=query_from,
                        train__route__to_location__iexact=query_to,
                        travel_date=travel_date,
                    )
                    if time_filters is not None:
                        train_schedules = train_schedules.filter(time_filters)
                    trips.extend([build_trip(schedule, 'train') for schedule in train_schedules])

                if query_mode in ['', 'flight']:
                    flight_schedules = FlightSchedule.objects.filter(
                        flight__route__from_location__iexact=query_from,
                        flight__route__to_location__iexact=query_to,
                        travel_date=travel_date,
                    )
                    if time_filters is not None:
                        flight_schedules = flight_schedules.filter(time_filters)
                    trips.extend([build_trip(schedule, 'flight') for schedule in flight_schedules])

        return render(request, template_name, {
            'active': 'dashboard',
            'trips': trips,
            'search_performed': search_performed,
            'from_choices': from_choices,
            'to_choices': to_choices,
            'query_from': query_from,
            'query_to': query_to,
            'query_date': query_date,
            'query_mode': query_mode,
            'query_time': query_time,
            'recommendations': {
                'most_used_mode': most_used_mode,
                'top_modes': top_modes,
                'recommended_route': recommended_route,
                'top_routes': top_routes,
                'most_used_companies': most_used_companies,
                'price_range': price_range,
                'average_price': average_price,
                'unique_prices': unique_prices,
            },
        })

    return render(request, template_name)


@login_required
def passenger_my_bookings(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    from apps.buses.models import Booking as BusBooking
    from apps.flights.models import Booking as FlightBooking
    from apps.trains.models import Booking as TrainBooking

    user_name = request.user.get_full_name() or request.user.username
    bus_bookings = list(BusBooking.objects.filter(passenger_name__icontains=user_name).order_by('-created_at')[:6])
    train_bookings = list(TrainBooking.objects.filter(passenger_name__icontains=user_name).order_by('-created_at')[:6])
    flight_bookings = list(FlightBooking.objects.filter(passenger_name__icontains=user_name).order_by('-created_at')[:6])

    all_bookings = bus_bookings + train_bookings + flight_bookings
    total_bookings = len(all_bookings)
    upcoming = sum(1 for booking in all_bookings if getattr(booking, 'travel_date', None) and booking.travel_date >= date.today())
    completed = sum(1 for booking in all_bookings if getattr(booking, 'travel_date', None) and booking.travel_date < date.today())

    return render(request, 'passenger/my_bookings.html', {
        'active': 'bookings',
        'total_bookings': total_bookings,
        'upcoming_trips': upcoming,
        'completed_trips': completed,
        'bus_bookings': bus_bookings,
        'train_bookings': train_bookings,
        'flight_bookings': flight_bookings,
    })


@login_required
def passenger_payments(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    from apps.payments.models import Payment

    payments = list(Payment.objects.filter(passenger=request.user).order_by('-created_at')[:12])
    total_amount = sum(payment.amount for payment in payments)
    successful = sum(1 for payment in payments if payment.status == 'completed')
    pending = sum(1 for payment in payments if payment.status == 'pending')

    return render(request, 'passenger/payments.html', {
        'active': 'payments',
        'payments': payments,
        'total_payments': total_amount,
        'successful_payments': successful,
        'pending_payments': pending,
    })


@login_required
def passenger_track_parcel(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    from apps.parcels.models import Parcel

    parcels = Parcel.objects.filter(sender=request.user).order_by('-created_at')[:12]
    total_parcels = parcels.count()
    in_transit = parcels.filter(status='in_transit').count()
    delivered = parcels.filter(status='arrived').count()
    pending = parcels.exclude(status__in=['arrived', 'collected']).count()

    return render(request, 'passenger/track_parcel.html', {
        'active': 'track_parcel',
        'parcels': parcels,
        'total_parcels': total_parcels,
        'in_transit': in_transit,
        'delivered': delivered,
        'pending': pending,
    })


@login_required
def passenger_loyalty(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    from apps.payments.models import Payment

    payments = Payment.objects.filter(passenger=request.user)
    payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
    point_balance = payments.count() * 100 + int(payment_total)
    tier = 'Platinum' if point_balance >= 3000 else 'Gold' if point_balance >= 1500 else 'Silver'
    savings = int(point_balance * 0.22)

    return render(request, 'passenger/loyalty.html', {
        'active': 'loyalty',
        'loyalty_points': f"{point_balance:,}",
        'current_tier': tier,
        'savings_earned': f"KES {savings:,}",
    })


@login_required
def passenger_support(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    from apps.systemadmin.models import Company

    admins = User.objects.filter(role__in=['admin', 'support_manager'])[:4]
    companies = Company.objects.filter(is_active=True)[:6]
    faqs = [
        {'question': 'How do I book a ticket?', 'answer': 'Use the passenger dashboard search to find a bus, train or flight and follow the booking flow.'},
        {'question': 'How can I track my parcel?', 'answer': 'Go to Track Parcel and view the live status of each parcel shipment.'},
        {'question': 'How do loyalty points work?', 'answer': 'Earn points on every booking and redeem them on the Loyalty page for travel perks.'},
        {'question': 'How do I use the emergency button?', 'answer': 'Tap the red emergency button to contact support immediately and alert our response team.'},
        {'question': 'How do I view traffic alerts?', 'answer': 'Open Traffic Alerts from the sidebar to see real-time route warnings and travel updates.'},
    ]

    return render(request, 'passenger/support.html', {
        'active': 'support',
        'admins': admins,
        'companies': companies,
        'faqs': faqs,
    })


@login_required
def passenger_traffic_alerts(request):
    if request.user.role != 'passenger':
        raise PermissionDenied

    traffic_alerts = [
        {
            'origin': 'Nairobi',
            'destination': 'Mombasa',
            'title': 'Accident near Emali',
            'severity': 'High',
            'message': 'Multiple vehicles involved. Expect significant delays on the Nairobi-Mombasa route.',
            'updated_at': '5 mins ago',
        },
        {
            'origin': 'Nairobi',
            'destination': 'Kisumu',
            'title': 'Roadworks near Nakuru',
            'severity': 'Medium',
            'message': 'One lane closed for repairs. Plan for an extra 25 minutes.',
            'updated_at': '12 mins ago',
        },
        {
            'origin': 'Mombasa',
            'destination': 'Malindi',
            'title': 'Traffic flow normal',
            'severity': 'Low',
            'message': 'All routes are operating smoothly.',
            'updated_at': '20 mins ago',
        },
    ]

    return render(request, 'passenger/traffic.html', {
        'active': 'traffic',
        'traffic_alerts': traffic_alerts,
    })


def _load_transport_models(mode):
    if mode == 'bus':
        from apps.buses.models import Booking as BookingModel, Schedule as ScheduleModel
    elif mode == 'train':
        from apps.trains.models import Booking as BookingModel, Schedule as ScheduleModel
    elif mode == 'flight':
        from apps.flights.models import Booking as BookingModel, Schedule as ScheduleModel
    else:
        raise Http404('Invalid transport mode.')
    return BookingModel, ScheduleModel


def _generate_booking_reference():
    reference = uuid.uuid4().hex[:10].upper()
    from apps.buses.models import Booking as BusBooking
    from apps.trains.models import Booking as TrainBooking
    from apps.flights.models import Booking as FlightBooking

    if BusBooking.objects.filter(booking_reference=reference).exists() or TrainBooking.objects.filter(booking_reference=reference).exists() or FlightBooking.objects.filter(booking_reference=reference).exists():
        return _generate_booking_reference()
    return reference


def _get_booked_seat_numbers(mode, schedule):
    BookingModel, _ = _load_transport_models(mode)
    transport = getattr(schedule, mode)
    return list(BookingModel.objects.filter(**{mode: transport, 'travel_date': schedule.travel_date}).exclude(seat_number__isnull=True).exclude(seat_number__exact='').values_list('seat_number', flat=True))


def _get_schedule_by_mode(mode, schedule_id):
    _, ScheduleModel = _load_transport_models(mode)
    return get_object_or_404(ScheduleModel, id=schedule_id)


# Placeholder for Daraja API URLs - these would typically be in settings or a separate config
DARJA_API_BASE_URL = "https://sandbox.safaricom.co.ke/mpesa/" # For sandbox
DARJA_AUTH_URL = f"{DARJA_API_BASE_URL}oauth/v1/generate?grant_type=client_credentials"
DARJA_STKPUSH_URL = f"{DARJA_API_BASE_URL}stkpush/v1/processrequest"

def _get_daraja_access_token():
    """
    Mocks obtaining an OAuth access token from Daraja API.
    In a real scenario, this would make an HTTP request and cache the token.
    """
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET
    auth_string = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode('utf-8')

    # Mocking the response for demonstration. In reality, use requests.get(DARJA_AUTH_URL, headers=...)
    # For sandbox, you might get a static token or need to make a real call.
    # For this exercise, we'll return a dummy token.
    # In a real scenario:
    # response = requests.get(DARJA_AUTH_URL, headers={"Authorization": f"Basic {auth_string}"})
    # response.raise_for_status() # Raise an exception for HTTP errors
    # return response.json().get('access_token')
    return "mock_daraja_access_token_xyz" # Return a dummy token for now


def _initiate_stk_push_daraja(phone, amount, booking_reference):
    """
    Initiates an M-Pesa STK Push using the Daraja API (sandbox).
    """
    try:
        access_token = _get_daraja_access_token()
        if not access_token:
            return {'success': False, 'message': 'Failed to get Daraja access token.'}

        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = base64.b64encode(
            f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
        ).decode('utf-8')

        # Ensure phone number is in the correct format (2547...)
        if phone.startswith('07'):
            phone = '254' + phone[1:]
        elif phone.startswith('7'):
            phone = '254' + phone
        elif not phone.startswith('254'):
            phone = '254' + phone[-9:] # Takes last 9 digits, e.g., 0722... -> 254722...

        callback_url = settings.MPESA_CALLBACK_URL # This should be a publicly accessible URL

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline", # Or CustomerBuyGoodsOnline
            "Amount": int(amount), # Amount must be an integer
            "PartyA": phone,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": booking_reference, # Use booking reference for traceability
            "TransactionDesc": f"SmartTravels Booking {booking_reference}",
        }

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Mocking a successful Daraja response for sandbox testing
        # In a real implementation, you would use:
        # response = requests.post(DARJA_STKPUSH_URL, json=payload, headers=headers)
        # response.raise_for_status() # Raise an exception for HTTP errors
        # response_data = response.json()
        response_data = {
            "ResponseCode": "0",
            "ResponseDescription": "Success. Request accepted for processing",
            "CustomerMessage": "Success. Request accepted for processing",
            "CheckoutRequestID": f"ws_CO_DMZ_{uuid.uuid4().hex}",
            "MerchantRequestID": f"12345-{uuid.uuid4().hex[:8]}",
        }

        if response_data.get("ResponseCode") == "0":
            return {
                'success': True,
                'transaction_id': response_data.get("CheckoutRequestID"), # This is the ID for polling
                'message': response_data.get("CustomerMessage", "STK Push initiated successfully."),
                'merchant_request_id': response_data.get("MerchantRequestID"),
            }
        else:
            return {
                'success': False,
                'message': response_data.get("CustomerMessage", "STK Push failed to initiate."),
                'error_code': response_data.get("ResponseCode"),
                'error_description': response_data.get("ResponseDescription"),
            }

    except Exception as e:
        return {'success': False, 'message': f'An error occurred during STK Push initiation: {e}'}


def _generate_ticket_pdf(booking):
    if not REPORTLAB_AVAILABLE:
        # Return a simple text ticket if reportlab is not available
        transport = getattr(booking, 'bus', None) or getattr(booking, 'train', None) or getattr(booking, 'flight', None)
        mode_label = 'Bus' if hasattr(booking, 'bus') and booking.bus else 'Train' if hasattr(booking, 'train') and booking.train else 'Flight'
        route_display = f"{booking.route.from_location} → {booking.route.to_location}"
        issue_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        qr_data = f'TICKET|{booking.booking_reference}|{mode_label}|{route_display}|{booking.travel_date}|{booking.seat_number or "NA"}'

        ticket_text = f"""
SMARTTRAVELS TICKET
===================
Reference: {booking.booking_reference}
Passenger: {booking.passenger_name}
Phone: {booking.phone}
Mode: {mode_label}
Route: {route_display}
Date: {booking.travel_date}
Time: {booking.travel_time or "TBD"}
Seat: {booking.seat_number or "Unassigned"}
Price: KES {booking.price:.2f}
Issued: {issue_date}

QR Code Data: {qr_data}

Present this ticket when boarding.
"""
        return ticket_text.encode('utf-8')

    transport = getattr(booking, 'bus', None) or getattr(booking, 'train', None) or getattr(booking, 'flight', None)
    mode_label = 'Bus' if hasattr(booking, 'bus') and booking.bus else 'Train' if hasattr(booking, 'train') and booking.train else 'Flight'
    route_display = f"{booking.route.from_location} → {booking.route.to_location}"
    issue_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(72, 720, 'SmartTravels Ticket')
    pdf.setFont('Helvetica', 10)
    pdf.drawString(72, 700, f'Reference: {booking.booking_reference}')
    pdf.drawString(72, 685, f'Passenger: {booking.passenger_name}')
    pdf.drawString(72, 670, f'Phone: {booking.phone}')
    pdf.drawString(72, 655, f'Mode: {mode_label}')
    pdf.drawString(72, 640, f'Route: {route_display}')
    pdf.drawString(72, 625, f'Date: {booking.travel_date}')
    pdf.drawString(72, 610, f'Time: {booking.travel_time or "TBD"}')
    pdf.drawString(72, 595, f'Seat: {booking.seat_number or "Unassigned"}')
    pdf.drawString(72, 580, f'Price: KES {booking.price:.2f}')
    pdf.drawString(72, 565, f'Issued: {issue_date}')

    if QRCODE_AVAILABLE:
        qr_data = f'TICKET|{booking.booking_reference}|{mode_label}|{route_display}|{booking.travel_date}|{booking.seat_number or "NA"}'
        qr_image = qrcode.make(qr_data)
        qr_buffer = io.BytesIO()
        qr_image.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)
        pdf.drawImage(ImageReader(qr_buffer), 400, 540, width=2 * inch, height=2 * inch)
    else:
        pdf.drawString(400, 600, 'QR Code not available')

    pdf.setFont('Helvetica-Oblique', 8)
    pdf.drawString(72, 540, 'Present this ticket and the QR code when boarding.')
    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    return buffer.getvalue()


def _find_booking_by_reference(reference):
    from apps.buses.models import Booking as BusBooking
    from apps.trains.models import Booking as TrainBooking
    from apps.flights.models import Booking as FlightBooking

    for model in [BusBooking, TrainBooking, FlightBooking]:
        try:
            return model.objects.get(booking_reference=reference)
        except model.DoesNotExist:
            continue
    raise Http404('Ticket not found.')


@login_required
def passenger_seat_layout(request):
    mode = request.GET.get('mode', '').lower()
    schedule_id = request.GET.get('schedule_id')
    if not mode or not schedule_id:
        return JsonResponse({'error': 'Missing mode or schedule_id.'}, status=400)

    schedule = _get_schedule_by_mode(mode, schedule_id)
    transport = getattr(schedule, mode)
    booked_numbers = _get_booked_seat_numbers(mode, schedule)

    if mode == 'bus':
        counts = {
            'vip_seats': transport.vip_seats,
            'normal_seats': transport.normal_seats,
        }
    else:
        counts = {
            'first_class_seats': transport.first_class_seats,
            'business_seats': transport.business_seats,
            'economy_seats': transport.economy_seats,
        }

    layout = generate_seat_layout(mode, counts, booked_numbers=booked_numbers)
    return JsonResponse(layout)


@login_required
def book_trip(request, mode, schedule_id):
    mode = mode.lower()
    schedule = _get_schedule_by_mode(mode, schedule_id)
    transport = getattr(schedule, mode)
    passenger_name = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
    default_phone = getattr(request.user, 'phone_number', '')
    error_message = None

    if request.method == 'POST':
        selected_seat = request.POST.get('selected_seat', '').strip()
        phone = request.POST.get('phone', '').strip() or default_phone

        if not selected_seat:
            error_message = 'Please select a seat from the layout before proceeding.'
        elif not phone:
            error_message = 'Please provide a phone number for the STK push.'
        elif selected_seat in _get_booked_seat_numbers(mode, schedule):
            error_message = 'This seat is no longer available. Please select a different seat.'
        elif transport.available_seats <= 0:
            error_message = 'No available seats remain for this trip.'
        else:
            booking_reference = _generate_booking_reference() # Generate before STK push for AccountReference
            payment = _initiate_stk_push_daraja(phone, float(schedule.price), booking_reference)
            if payment['success']:
                BookingModel, _ = _load_transport_models(mode)
                booking_kwargs = {
                    'passenger_name': passenger_name,
                    'phone': phone,
                    'route': transport.route,
                    mode: transport,
                    'travel_date': schedule.travel_date,
                    'travel_time': schedule.travel_time,
                    'price': schedule.price,
                    'seat_number': selected_seat,
                    'booking_reference': booking_reference,
                    'status': 'confirmed',
                }
                booking = BookingModel.objects.create(**booking_kwargs)
                transport.available_seats = max(0, transport.available_seats - 1)
                transport.save()
                if request.user.email:
                    sent_email = _send_ticket_email(request.user.email, booking)
                    if sent_email:
                        messages.success(request, 'Booking confirmed and ticket emailed to you.')
                    else:
                        messages.warning(request, 'Booking confirmed. Ticket email could not be delivered at this time.')
                return redirect('download_ticket', booking_reference=booking.booking_reference)
            else:
                error_message = payment.get('message', 'STK push failed. Please try again.')

    return render(request, 'passenger/book_trip.html', {
        'mode': mode,
        'schedule': schedule,
        'transport': transport,
        'passenger_name': passenger_name,
        'default_phone': default_phone,
        'error_message': error_message,
    })


@login_required
def download_ticket(request, booking_reference):
    booking = _find_booking_by_reference(booking_reference)
    ticket_data = _generate_ticket_pdf(booking)

    if REPORTLAB_AVAILABLE:
        response = HttpResponse(ticket_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ticket_{booking_reference}.pdf"'
    else:
        response = HttpResponse(ticket_data, content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="ticket_{booking_reference}.txt"'

    return response


def logout_view(request):
    logout(request)
    return redirect('login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        # Find all users with this email
        users_with_email = User.objects.filter(email__iexact=email)

        if not users_with_email.exists():
            error = 'No account found with this email address.'
        else:
            # Try to authenticate with each user that has this email
            authenticated_user = None
            for user_obj in users_with_email:
                user = authenticate(request, username=user_obj.username, password=password)
                if user is not None:
                    authenticated_user = user
                    break

            if authenticated_user is not None:
                login(request, authenticated_user)
                return redirect('dashboard')
            else:
                error = 'Invalid email or password. Please check your credentials.'

    return render(request, 'auth/login.html', {'error': error})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = PassengerRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        full_name = form.cleaned_data['full_name'].strip()
        email = form.cleaned_data['email'].lower()
        phone = form.cleaned_data['phone']
        password = form.cleaned_data['password']

        username = email
        name_parts = full_name.split()
        first_name = name_parts[0] if name_parts else ''
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role='passenger',
            phone_number=phone,
        )

        login(request, user)
        return redirect('dashboard')

    return render(request, 'auth/register.html', {'form': form})