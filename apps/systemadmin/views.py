"""
SmartTravels – System Admin Views
Full analytics, user management, company assignment, audit logs
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import json

from apps.accounts.models import User
from apps.buses.models   import Bus, Route as BusRoute, Booking as BusBooking, Schedule as BusSchedule
from apps.trains.models  import Train, Route as TrainRoute, Booking as TrainBooking, Schedule as TrainSchedule
from apps.flights.models import Flight, Route as FlightRoute, Booking as FlightBooking, Schedule as FlightSchedule
from apps.payments.models import Payment
from apps.parcels.models  import Parcel
from apps.systemadmin.models import AuditLog, Company, SystemAdminRole, SystemSetting
from apps.systemadmin.models import Subscriber
from django.core.mail import send_mail, EmailMessage
from django.conf import settings


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def record_audit(request, action, model_name, object_id=None, details=''):
    AuditLog.objects.create(
        user=request.user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details,
        ip_address=get_client_ip(request)
    )


def sysadmin_required(fn):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'admin':
            messages.error(request, 'Access denied.')
            return redirect('login')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


# ── DASHBOARD ────────────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def system_admin_dashboard(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Totals
    total_users     = User.objects.count()
    total_buses     = Bus.objects.count()
    total_trains    = Train.objects.count()
    total_flights   = Flight.objects.count()
    total_bookings  = BusBooking.objects.count() + TrainBooking.objects.count() + FlightBooking.objects.count()
    total_revenue   = (
        BusBooking.objects.aggregate(s=Sum('price'))['s'] or 0
    ) + (
        TrainBooking.objects.aggregate(s=Sum('price'))['s'] or 0
    ) + (
        FlightBooking.objects.aggregate(s=Sum('price'))['s'] or 0
    )
    total_parcels   = Parcel.objects.count()

    # Recent users
    recent_users = User.objects.order_by('-date_joined')[:10]

    # Revenue by day (last 7 days)
    revenue_trend = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        bus_rev   = BusBooking.objects.filter(created_at__date=day).aggregate(s=Sum('price'))['s'] or 0
        train_rev = TrainBooking.objects.filter(created_at__date=day).aggregate(s=Sum('price'))['s'] or 0
        flight_rev= FlightBooking.objects.filter(created_at__date=day).aggregate(s=Sum('price'))['s'] or 0
        revenue_trend.append({
            'date': day.strftime('%d %b'),
            'bus': float(bus_rev),
            'train': float(train_rev),
            'flight': float(flight_rev),
            'total': float(bus_rev + train_rev + flight_rev),
        })

    # Booking breakdown
    booking_breakdown = {
        'bus': BusBooking.objects.count(),
        'train': TrainBooking.objects.count(),
        'flight': FlightBooking.objects.count(),
    }

    # Role distribution
    role_counts = {r: User.objects.filter(role=r).count() for r in ['admin','bus_admin','train_admin','flight_admin','driver','passenger']}

    # Recent bookings (all modes)
    recent_bookings = []
    for b in BusBooking.objects.select_related('route').order_by('-created_at')[:5]:
        recent_bookings.append({'ref': b.booking_reference, 'route': str(b.route), 'mode': 'bus', 'price': b.price, 'status': b.status, 'date': b.created_at})
    for b in TrainBooking.objects.select_related('route').order_by('-created_at')[:5]:
        recent_bookings.append({'ref': b.booking_reference, 'route': str(b.route), 'mode': 'train', 'price': b.price, 'status': b.status, 'date': b.created_at})
    recent_bookings.sort(key=lambda x: x['date'], reverse=True)
    recent_bookings = recent_bookings[:10]
    recent_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:5]
    total_admins = User.objects.filter(role__in=['admin', 'bus_admin', 'train_admin', 'flight_admin']).count()
    system_health = 'Good'

    return render(request, 'system_admin/dashboard.html', {
        'total_users': total_users,
        'total_vehicles': total_buses + total_trains + total_flights,
        'total_bookings': total_bookings,
        'total_revenue': total_revenue,
        'total_parcels': total_parcels,
        'recent_users': recent_users,
        'revenue_trend': json.dumps(revenue_trend),
        'booking_breakdown': json.dumps(booking_breakdown),
        'role_counts': json.dumps(role_counts),
        'recent_bookings': recent_bookings,
        'recent_logs': recent_logs,
        'total_admins': total_admins,
        'system_health': system_health,
    })


# ── USER MANAGEMENT ──────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def manage_users(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        target_user = User.objects.filter(id=user_id).first()

        if not target_user:
            messages.error(request, 'User not found.')
            return redirect('manage_users')

        if action == 'activate':
            target_user.is_active = True
            target_user.save(update_fields=['is_active'])
            messages.success(request, f'User "{target_user.email}" has been activated.')
            record_audit(
                request,
                'update',
                'User',
                object_id=target_user.id,
                details=f'Activated user {target_user.email} ({target_user.role}).'
            )
        elif action == 'deactivate':
            if target_user == request.user:
                messages.error(request, 'You cannot deactivate your own account.')
            else:
                target_user.is_active = False
                target_user.save(update_fields=['is_active'])
                messages.success(request, f'User "{target_user.email}" has been deactivated.')
                record_audit(
                    request,
                    'update',
                    'User',
                    object_id=target_user.id,
                    details=f'Deactivated user {target_user.email} ({target_user.role}).'
                )
        elif action == 'delete':
            if target_user == request.user:
                messages.error(request, 'You cannot delete your own account.')
            else:
                target_user_id = target_user.id
                target_user_email = target_user.email
                target_user_role = target_user.role
                target_user.delete()
                messages.success(request, f'User "{target_user_email}" has been deleted.')
                record_audit(
                    request,
                    'delete',
                    'User',
                    object_id=target_user_id,
                    details=f'Deleted user {target_user_email} ({target_user_role}).'
                )
        else:
            messages.error(request, 'Unknown user action.')

        return redirect('manage_users')

    role_filter = request.GET.get('role', '')
    search = request.GET.get('q', '')
    users = User.objects.all().order_by('-date_joined')
    if role_filter:
        users = users.filter(role=role_filter)
    if search:
        users = users.filter(Q(username__icontains=search) | Q(first_name__icontains=search)
                             | Q(last_name__icontains=search) | Q(email__icontains=search))
    return render(request, 'system_admin/manage_users.html', {
        'users': users,
        'role_filter': role_filter,
        'search': search,
        'roles': User.ROLE_CHOICES if hasattr(User, 'ROLE_CHOICES') else [],
    })


@login_required
@sysadmin_required
def toggle_user_status(request, user_id):
    u = get_object_or_404(User, id=user_id)
    u.is_active = not u.is_active
    u.save(update_fields=['is_active'])
    return JsonResponse({'active': u.is_active, 'name': u.get_full_name() or u.username})


@login_required
@sysadmin_required
def subscribers(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'send_email':
            subject = request.POST.get('subject', '').strip()
            body = request.POST.get('body', '').strip()
            emails = Subscriber.objects.values_list('email', flat=True)
            if subject and body and emails:
                try:
                    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, list(emails))
                    email.send(fail_silently=False)
                    messages.success(request, 'Email sent to subscribers.')
                except Exception as exc:
                    messages.error(request, f'Failed to send emails: {exc}')
            return redirect('subscribers')

    subs = Subscriber.objects.all()
    return render(request, 'system_admin/subscribers.html', {
        'subscribers': subs,
    })


@csrf_exempt
def subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        if email:
            s, created = Subscriber.objects.get_or_create(email=email)
            if created:
                try:
                    send_mail('Thanks for subscribing', 'You have been subscribed to SmartTravels updates.', settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                except Exception:
                    pass
            messages.success(request, 'Thank you for subscribing.')
            return redirect('homepage')
    return JsonResponse({'error': 'Invalid request'}, status=400)


# ── ADMIN MANAGEMENT ─────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def manage_admins(request):
    if request.method == 'POST':
        if 'create_company' in request.POST:
            name = request.POST.get('company_name', '').strip()
            transport_type = request.POST.get('transport_type', '').strip()
            contact_email = request.POST.get('contact_email', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            description = request.POST.get('description', '').strip()
            address = request.POST.get('address', '').strip()

            if not name or not transport_type:
                messages.error(request, 'Company name and transport type are required.')
            elif Company.objects.filter(name__iexact=name).exists():
                messages.error(request, f'Company "{name}" already exists.')
            else:
                company = Company.objects.create(
                    name=name,
                    transport_type=transport_type,
                    contact_email=contact_email,
                    contact_phone=contact_phone,
                    description=description,
                    address=address,
                )
                messages.success(request, f'Company "{name}" created successfully.')
                record_audit(
                    request,
                    'create',
                    'Company',
                    object_id=company.id,
                    details=f'Created company {company.name} ({company.get_transport_type_display()}).'
                )
            return redirect('manage_admins')

        if 'create_transport_admin' in request.POST:
            username = request.POST.get('admin_username', '').strip()
            email = request.POST.get('admin_email', '').strip()
            password = request.POST.get('admin_password', '').strip()
            role = request.POST.get('admin_type', '').strip()
            company_id = request.POST.get('company_id', '').strip()

            if not username or not email or not password or not role or not company_id:
                messages.error(request, 'All transport admin fields are required.')
                return redirect('manage_admins')

            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists.')
                return redirect('manage_admins')
            if User.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" already exists.')
                return redirect('manage_admins')

            company = Company.objects.filter(id=company_id).first()
            if not company:
                messages.error(request, 'Selected company does not exist.')
                return redirect('manage_admins')

            new_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=request.POST.get('first_name', '').strip(),
                last_name=request.POST.get('last_name', '').strip(),
                role=role,
                company=company,
                is_active=True,
                is_staff=True,
            )
            if hasattr(new_user, 'phone_number') and request.POST.get('phone', '').strip():
                new_user.phone_number = request.POST.get('phone', '').strip()
                new_user.save(update_fields=['phone_number'])
            messages.success(request, f'{role.replace("_", " ").title()} "{username}" created successfully.')
            record_audit(
                request,
                'create',
                'User',
                object_id=new_user.id,
                details=f'Created transport admin {new_user.email} ({role}).'
            )
            return redirect('manage_admins')

        if 'create_admin' in request.POST:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            system_role = request.POST.get('role', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()

            if not username or not email or not password or not system_role:
                messages.error(request, 'All system admin fields are required.')
                return redirect('manage_admins')

            if User.objects.filter(username=username).exists():
                messages.error(request, f'Username "{username}" already exists.')
                return redirect('manage_admins')
            if User.objects.filter(email=email).exists():
                messages.error(request, f'Email "{email}" already exists.')
                return redirect('manage_admins')

            new_user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='admin',
                is_active=True,
                is_staff=True,
            )
            SystemAdminRole.objects.create(user=new_user, role=system_role)
            messages.success(request, f'System admin "{username}" created successfully.')
            record_audit(
                request,
                'create',
                'User',
                object_id=new_user.id,
                details=f'Created system admin {new_user.email} with role {system_role}.'
            )
            return redirect('manage_admins')

        if 'update_system_role' in request.POST:
            admin_id = request.POST.get('admin_id')
            new_role = request.POST.get('new_role')
            admin_role = SystemAdminRole.objects.filter(id=admin_id).first()
            if admin_role and new_role:
                old_role = admin_role.role
                admin_role.role = new_role
                admin_role.save(update_fields=['role'])
                messages.success(request, 'System admin role updated.')
                record_audit(
                    request,
                    'update',
                    'SystemAdminRole',
                    object_id=admin_role.id,
                    details=f'Updated system admin {admin_role.user.email} role from {old_role} to {new_role}.'
                )
            else:
                messages.error(request, 'Unable to update system role.')
            return redirect('manage_admins')

        if 'action' in request.POST:
            transport_admin_id = request.POST.get('transport_admin_id')
            action = request.POST.get('action')
            transport_admin = User.objects.filter(id=transport_admin_id, role__in=['bus_admin', 'train_admin', 'flight_admin']).first()
            if transport_admin:
                if action == 'activate':
                    transport_admin.is_active = True
                    transport_admin.save(update_fields=['is_active'])
                    messages.success(request, 'Transport admin activated.')
                    record_audit(
                        request,
                        'update',
                        'User',
                        object_id=transport_admin.id,
                        details=f'Activated transport admin {transport_admin.email} ({transport_admin.role}).'
                    )
                elif action == 'deactivate':
                    transport_admin.is_active = False
                    transport_admin.save(update_fields=['is_active'])
                    messages.success(request, 'Transport admin deactivated.')
                    record_audit(
                        request,
                        'update',
                        'User',
                        object_id=transport_admin.id,
                        details=f'Deactivated transport admin {transport_admin.email} ({transport_admin.role}).'
                    )
                elif action == 'delete':
                    transport_admin_id = transport_admin.id
                    transport_admin_email = transport_admin.email
                    transport_admin_role = transport_admin.role
                    transport_admin.delete()
                    messages.success(request, 'Transport admin deleted.')
                    record_audit(
                        request,
                        'delete',
                        'User',
                        object_id=transport_admin_id,
                        details=f'Deleted transport admin {transport_admin_email} ({transport_admin_role}).'
                    )
                else:
                    messages.error(request, 'Unknown action.')
            else:
                messages.error(request, 'Transport admin not found.')
            return redirect('manage_admins')

    companies = Company.objects.all().order_by('name')
    admin_roles = SystemAdminRole.objects.select_related('user').all().order_by('-id')
    transport_admins = User.objects.filter(role__in=['bus_admin', 'train_admin', 'flight_admin']).order_by('-date_joined')
    return render(request, 'system_admin/manage_admins.html', {
        'companies': companies,
        'admin_roles': admin_roles,
        'transport_admins': transport_admins,
    })


# ── ANALYTICS ────────────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def analytics(request):
    today = timezone.now().date()
    # Monthly revenue trend (12 months)
    monthly = []
    for i in range(11, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=30 * i))
        m_end   = (m_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        rev = (
            (BusBooking.objects.filter(created_at__date__gte=m_start, created_at__date__lte=m_end).aggregate(s=Sum('price'))['s'] or 0)
            + (TrainBooking.objects.filter(created_at__date__gte=m_start, created_at__date__lte=m_end).aggregate(s=Sum('price'))['s'] or 0)
            + (FlightBooking.objects.filter(created_at__date__gte=m_start, created_at__date__lte=m_end).aggregate(s=Sum('price'))['s'] or 0)
        )
        monthly.append({'month': m_start.strftime('%b %Y'), 'revenue': float(rev)})

    return render(request, 'system_admin/analytics.html', {
        'monthly_revenue': json.dumps(monthly),
        'total_bus_bookings':    BusBooking.objects.count(),
        'total_train_bookings':  TrainBooking.objects.count(),
        'total_flight_bookings': FlightBooking.objects.count(),
        'total_parcels':         Parcel.objects.count(),
        'total_payments':        Payment.objects.filter(status='completed').count(),
    })


# ── AUDIT LOGS ───────────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def audit_logs(request):
    action_filter = request.GET.get('action', '')
    user_query = request.GET.get('user', '').strip()

    logs = AuditLog.objects.select_related('user').order_by('-timestamp')
    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_query:
        logs = logs.filter(Q(user__username__icontains=user_query) | Q(user__email__icontains=user_query))

    return render(request, 'system_admin/audit_logs.html', {
        'logs': logs,
        'action_choices': AuditLog.ACTION_CHOICES,
    })


# ── SYSTEM SETTINGS ───────────────────────────────────────────────────────────
@login_required
@sysadmin_required
def system_settings(request):
    settings = SystemSetting.objects.order_by('key')

    if request.method == 'POST':
        key = request.POST.get('key', '').strip()
        value = request.POST.get('value', '').strip()
        description = request.POST.get('description', '').strip()
        is_public = request.POST.get('is_public') == 'on'

        if not key or not value:
            messages.error(request, 'Key and value are required for settings.')
        else:
            setting, created = SystemSetting.objects.update_or_create(
                key=key,
                defaults={
                    'value': value,
                    'description': description,
                    'is_public': is_public,
                }
            )
            action_label = 'created' if created else 'updated'
            record_audit(
                request,
                'create' if created else 'update',
                'SystemSetting',
                object_id=setting.id,
                details=(f'Created setting {setting.key}.' if created else f'Updated setting {setting.key}.')
            )
            messages.success(request, f'System setting "{setting.key}" {action_label} successfully.')
            return redirect('system_settings')

    return render(request, 'system_admin/system_settings.html', {
        'settings': settings,
    })
