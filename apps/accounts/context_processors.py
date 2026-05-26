from django.db.models import Sum


def loyalty_context(request):
    loyalty_points = None
    loyalty_tier = None
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'passenger':
        try:
            from apps.payments.models import Payment
            payments = Payment.objects.filter(passenger=request.user)
            payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
            point_balance = int(payment_total / 100)  # 1 point per 100 KSH spent
            if point_balance >= 3000:
                loyalty_tier = 'Platinum'
            elif point_balance >= 1500:
                loyalty_tier = 'Gold'
            else:
                loyalty_tier = 'Silver'
            loyalty_points = f"{point_balance:,}"
        except Exception:
            loyalty_points = None
            loyalty_tier = 'Passenger'
    return {
        'loyalty_points': loyalty_points,
        'loyalty_tier': loyalty_tier,
    }
