"""
Seat Management API Views
Handles seat availability, reservations, and booking operations
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
import json
import uuid

from .models import (
    Seat, SeatClass, VehicleLayout, SeatReservation, 
    SeatBooking, SeatLayoutHistory
)


@require_http_methods(["GET"])
def get_vehicle_seats(request, vehicle_type, vehicle_id, travel_date):
    """
    Get all seats for a vehicle on a specific date with their statuses
    
    GET /api/seats/vehicle/<type>/<id>/<date>/
    Returns: {
        'vehicle_id': int,
        'vehicle_type': str,
        'travel_date': str,
        'layout': VehicleLayout data,
        'seats': [Seat data with status],
        'summary': { available, booked, reserved, blocked }
    }
    """
    try:
        travel_dt = datetime.strptime(travel_date, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)
    
    # Fetch all seats for this vehicle
    seats = Seat.objects.filter(
        content_type=vehicle_type,
        vehicle_id=vehicle_id
    ).select_related('seat_class').order_by('seat_row', 'seat_column')
    
    if not seats.exists():
        return JsonResponse({'error': 'Vehicle not found or has no seats'}, status=404)
    
    # Get layout info
    try:
        layout = VehicleLayout.objects.filter(
            vehicle_type=vehicle_type
        ).first()
    except:
        layout = None
    
    # Build seat data with real-time status checks
    seats_data = []
    status_summary = {'available': 0, 'booked': 0, 'reserved': 0, 'blocked': 0}
    
    for seat in seats:
        # Check if reservation is still active
        if seat.status == 'reserved' and seat.held_until:
            if timezone.now() > seat.held_until:
                # Hold expired, revert to available
                seat.status = 'available'
                seat.save()
        
        status_summary[seat.status] += 1
        
        seat_dict = {
            'id': seat.id,
            'seat_number': seat.seat_number,
            'row': seat.seat_row,
            'column': seat.seat_column,
            'class': seat.seat_class.name,
            'class_display': seat.seat_class.display_name,
            'status': seat.status,
            'price': float(seat.price),
            'color': seat.seat_class.color_code,
            'position': {'x': seat.position_x, 'y': seat.position_y},
            'features': {
                'extra_legroom': seat.is_extra_legroom,
                'window': seat.is_window,
                'aisle': seat.is_aisle,
                'emergency_exit_row': seat.is_emergency_exit_row,
            }
        }
        
        # Add cabin info for trains
        if seat.cabin_name:
            seat_dict['cabin'] = {
                'id': seat.cabin_id,
                'name': seat.cabin_name
            }
        
        seats_data.append(seat_dict)
    
    response = {
        'vehicle_id': vehicle_id,
        'vehicle_type': vehicle_type,
        'travel_date': travel_date,
        'total_seats': len(seats_data),
        'layout': {
            'rows': layout.rows if layout else None,
            'columns': layout.columns if layout else None,
            'aisle_position': layout.aisle_position if layout else None,
            'template_name': layout.template_name if layout else None,
        } if layout else None,
        'seats': seats_data,
        'summary': status_summary,
    }
    
    return JsonResponse(response)


@require_http_methods(["GET"])
def get_seat_details(request, seat_id):
    """Get detailed information about a specific seat"""
    try:
        seat = Seat.objects.select_related('seat_class').get(id=seat_id)
    except Seat.DoesNotExist:
        return JsonResponse({'error': 'Seat not found'}, status=404)
    
    bookings = seat.bookings.filter(status='confirmed')
    reservations = seat.reservations.filter(status='active')
    
    response = {
        'id': seat.id,
        'seat_number': seat.seat_number,
        'status': seat.status,
        'class': seat.seat_class.display_name,
        'price': float(seat.price),
        'features': {
            'extra_legroom': seat.is_extra_legroom,
            'window': seat.is_window,
            'aisle': seat.is_aisle,
            'emergency_exit_row': seat.is_emergency_exit_row,
        },
        'booking_history': [
            {
                'booking_ref': b.booking_reference,
                'passenger': b.passenger_name,
                'status': b.status,
                'booked_at': b.created_at.isoformat(),
            }
            for b in bookings[:5]
        ],
        'current_holds': len(reservations),
    }
    
    if seat.cabin_name:
        response['cabin'] = seat.cabin_name
    
    return JsonResponse(response)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def reserve_seat(request, seat_id):
    """
    Reserve a seat temporarily (seat hold during checkout)
    
    POST /api/seats/<id>/reserve/
    Body: {
        'hold_duration_minutes': 10,
        'travel_date': '2025-06-15',
        'travel_time': '14:30'
    }
    Returns: {
        'reservation_token': str,
        'expires_at': datetime,
        'seat': Seat data
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    try:
        seat = Seat.objects.get(id=seat_id)
    except Seat.DoesNotExist:
        return JsonResponse({'error': 'Seat not found'}, status=404)
    
    # Check if seat is available
    if not seat.is_available_for_booking():
        return JsonResponse({
            'error': 'Seat is not available',
            'status': seat.status
        }, status=400)
    
    # Check for existing holds by this user
    existing_holds = SeatReservation.objects.filter(
        user=request.user,
        status='active'
    ).count()
    
    if existing_holds >= 8:  # Max 8 seats per booking
        return JsonResponse({
            'error': 'Maximum seat holds per booking exceeded'
        }, status=400)
    
    # Create reservation
    hold_duration = data.get('hold_duration_minutes', 10)
    expires_at = timezone.now() + timedelta(minutes=hold_duration)
    reservation_token = str(uuid.uuid4())
    
    try:
        travel_date = datetime.strptime(data.get('travel_date', ''), '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Invalid travel_date format'}, status=400)
    
    travel_time = None
    if data.get('travel_time'):
        try:
            travel_time = datetime.strptime(data.get('travel_time'), '%H:%M').time()
        except ValueError:
            pass
    
    reservation = SeatReservation.objects.create(
        user=request.user,
        seat=seat,
        reservation_token=reservation_token,
        status='active',
        hold_duration_minutes=hold_duration,
        expires_at=expires_at,
        travel_date=travel_date,
        travel_time=travel_time,
    )
    
    # Update seat status
    seat.status = 'reserved'
    seat.held_until = expires_at
    seat.held_by = request.user
    seat.save()
    
    return JsonResponse({
        'success': True,
        'reservation_token': reservation_token,
        'expires_at': expires_at.isoformat(),
        'seat': {
            'id': seat.id,
            'seat_number': seat.seat_number,
            'price': float(seat.price),
        }
    }, status=201)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def release_seat(request, seat_id):
    """Release a seat hold"""
    try:
        seat = Seat.objects.get(id=seat_id)
    except Seat.DoesNotExist:
        return JsonResponse({'error': 'Seat not found'}, status=404)
    
    reservation = SeatReservation.objects.filter(
        seat=seat,
        user=request.user,
        status='active'
    ).first()
    
    if not reservation:
        return JsonResponse({
            'error': 'No active reservation found'
        }, status=404)
    
    # Release reservation
    reservation.status = 'released'
    reservation.released_at = timezone.now()
    reservation.save()
    
    # Reset seat status
    seat.status = 'available'
    seat.held_until = None
    seat.held_by = None
    seat.save()
    
    return JsonResponse({
        'success': True,
        'seat_id': seat.id,
        'message': 'Seat released successfully'
    })


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def confirm_seat_booking(request):
    """
    Confirm seat booking after payment
    
    POST /api/seats/confirm-booking/
    Body: {
        'reservation_token': str,
        'booking_id': int,
        'booking_reference': str,
        'content_type': 'bus|train|flight',
        'passenger_name': str,
        'passenger_phone': str,
        'passenger_id': str,
        'price_paid': float
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    reservation_token = data.get('reservation_token')
    if not reservation_token:
        return JsonResponse({'error': 'Missing reservation_token'}, status=400)
    
    try:
        reservation = SeatReservation.objects.get(
            reservation_token=reservation_token,
            user=request.user
        )
    except SeatReservation.DoesNotExist:
        return JsonResponse({'error': 'Reservation not found'}, status=404)
    
    if reservation.is_expired():
        # Clean up
        reservation.status = 'expired'
        reservation.save()
        reservation.seat.status = 'available'
        reservation.seat.save()
        return JsonResponse({'error': 'Reservation has expired'}, status=400)
    
    # Create SeatBooking
    seat_booking = SeatBooking.objects.create(
        content_type=data.get('content_type', 'bus'),
        booking_id=data.get('booking_id', 0),
        seat=reservation.seat,
        user=request.user,
        booking_reference=data.get('booking_reference', ''),
        status='pending',
        price_paid=data.get('price_paid', 0),
        passenger_name=data.get('passenger_name', ''),
        passenger_phone=data.get('passenger_phone', ''),
        passenger_id=data.get('passenger_id', ''),
    )
    
    # Update reservation
    reservation.status = 'confirmed'
    reservation.save()
    
    # Update seat
    seat = reservation.seat
    seat.status = 'booked'
    seat.held_until = None
    seat.held_by = None
    seat.save()
    
    return JsonResponse({
        'success': True,
        'seat_booking_id': seat_booking.id,
        'seat_number': seat.seat_number,
        'booking_reference': seat_booking.booking_reference,
        'message': 'Seat booking confirmed'
    }, status=201)


@require_http_methods(["GET"])
def get_seat_layout_template(request, layout_id):
    """Get a seat layout template"""
    try:
        layout = VehicleLayout.objects.get(id=layout_id)
    except VehicleLayout.DoesNotExist:
        return JsonResponse({'error': 'Layout not found'}, status=404)
    
    response = {
        'id': layout.id,
        'template_name': layout.template_name,
        'vehicle_type': layout.vehicle_type,
        'total_seats': layout.total_seats,
        'rows': layout.rows,
        'columns': layout.columns,
        'aisle_position': layout.aisle_position,
        'aisle_arrangement': layout.aisle_arrangement,
        'has_driver_cockpit': layout.has_driver_cockpit,
        'driver_location': layout.driver_location,
        'layout_data': layout.layout_data,
    }
    
    # Add train-specific info
    if layout.cabins:
        response['cabins'] = layout.cabins
    
    # Add flight-specific info
    if layout.emergency_exits:
        response['emergency_exits'] = layout.emergency_exits
        response['lavatory_locations'] = layout.lavatory_locations
    
    return JsonResponse(response)


@require_http_methods(["GET"])
def list_available_templates(request, vehicle_type):
    """List all available seat layout templates for a vehicle type"""
    company_id = request.GET.get('company_id')
    
    query = VehicleLayout.objects.filter(
        vehicle_type=vehicle_type,
        is_template=True,
        is_active=True
    )
    
    if company_id:
        query = query.filter(company_id=company_id)
    
    templates = [
        {
            'id': t.id,
            'name': t.template_name,
            'description': t.description,
            'total_seats': t.total_seats,
            'rows': t.rows,
            'columns': t.columns,
            'created_at': t.created_at.isoformat(),
        }
        for t in query
    ]
    
    return JsonResponse({
        'vehicle_type': vehicle_type,
        'templates': templates,
        'count': len(templates)
    })


@login_required
@require_http_methods(["GET"])
def get_user_reservations(request):
    """Get all active seat reservations for logged-in user"""
    reservations = SeatReservation.objects.filter(
        user=request.user,
        status='active'
    ).select_related('seat')
    
    data = [
        {
            'reservation_token': r.reservation_token,
            'seat': {
                'id': r.seat.id,
                'number': r.seat.seat_number,
                'class': r.seat.seat_class.display_name,
                'price': float(r.seat.price),
            },
            'travel_date': r.travel_date.isoformat(),
            'expires_at': r.expires_at.isoformat(),
            'time_remaining_minutes': int((r.expires_at - timezone.now()).total_seconds() / 60),
        }
        for r in reservations
    ]
    
    return JsonResponse({
        'reservations': data,
        'count': len(data)
    })


# ===== ADMIN FUNCTIONS =====

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def generate_vehicle_seats(request):
    """
    Generate seats from a layout template
    
    POST /api/seats/generate/
    Body: {
        'layout_id': int,
        'vehicle_type': 'bus|train|flight',
        'vehicle_id': int,
        'cabin_mappings': { 'Cabin A': {'class': 'first_class', 'rows': 5} }
    }
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    try:
        layout = VehicleLayout.objects.get(id=data.get('layout_id'))
    except VehicleLayout.DoesNotExist:
        return JsonResponse({'error': 'Layout not found'}, status=404)
    
    vehicle_type = data.get('vehicle_type', layout.vehicle_type)
    vehicle_id = data.get('vehicle_id')
    
    if not vehicle_id:
        return JsonResponse({'error': 'vehicle_id required'}, status=400)
    
    # Delete existing seats
    Seat.objects.filter(
        content_type=vehicle_type,
        vehicle_id=vehicle_id
    ).delete()
    
    # Generate seats from layout
    created_seats = []
    
    if vehicle_type in ['bus', 'flight']:
        # Standard row/column layout
        seat_classes = SeatClass.objects.filter(transport_type=vehicle_type)
        class_distribution = {
            'bus': {'vip': range(1, 6), 'normal': range(6, layout.total_seats + 1)},
            'flight': {'first_class': range(1, 11), 'business': range(11, 41), 'economy': range(41, layout.total_seats + 1)}
        }
        
        dist = class_distribution.get(vehicle_type, {})
        seat_num = 1
        
        for row in range(1, layout.rows + 1):
            for col_idx in range(1, layout.columns + 1):
                col_letter = chr(64 + col_idx)  # A, B, C, etc.
                seat_number = f"{row}{col_letter}"
                
                # Determine seat class
                seat_class = None
                for class_name, seats_range in dist.items():
                    if seat_num in seats_range:
                        seat_class = SeatClass.objects.filter(
                            name=class_name,
                            transport_type=vehicle_type
                        ).first()
                        break
                
                if not seat_class:
                    seat_class = seat_classes.first()
                
                # Skip aisle columns
                if col_idx != layout.aisle_position:
                    seat = Seat.objects.create(
                        content_type=vehicle_type,
                        vehicle_id=vehicle_id,
                        seat_number=seat_number,
                        seat_row=row,
                        seat_column=col_letter,
                        seat_class=seat_class,
                        position_x=col_idx * 50,
                        position_y=row * 60,
                        price=seat_class.base_price,
                        is_window=(col_idx == 1 or col_idx == layout.columns),
                        status='available',
                    )
                    created_seats.append(seat)
                    seat_num += 1
    
    elif vehicle_type == 'train':
        # Train with cabins
        cabin_mappings = data.get('cabin_mappings', {})
        seat_num = 1
        
        for cabin_name, cabin_config in cabin_mappings.items():
            seat_class = SeatClass.objects.filter(
                name=cabin_config.get('class', 'economy'),
                transport_type='train'
            ).first()
            
            if not seat_class:
                seat_class = SeatClass.objects.filter(transport_type='train').first()
            
            cabin_rows = cabin_config.get('rows', 10)
            
            for row in range(1, cabin_rows + 1):
                for col_idx in range(1, 3):  # 2 columns for trains
                    col_letter = chr(64 + col_idx)
                    seat_number = f"{cabin_name}-{row}{col_letter}"
                    
                    seat = Seat.objects.create(
                        content_type='train',
                        vehicle_id=vehicle_id,
                        seat_number=seat_number,
                        seat_row=row,
                        seat_column=col_letter,
                        cabin_id=cabin_name.lower().replace(' ', '_'),
                        cabin_name=cabin_name,
                        seat_class=seat_class,
                        position_x=col_idx * 100,
                        position_y=row * 50,
                        price=seat_class.base_price,
                        is_window=(col_idx == 1),
                        status='available',
                    )
                    created_seats.append(seat)
                    seat_num += 1
    
    return JsonResponse({
        'success': True,
        'seats_created': len(created_seats),
        'vehicle_type': vehicle_type,
        'vehicle_id': vehicle_id,
        'message': f'Successfully created {len(created_seats)} seats'
    }, status=201)
