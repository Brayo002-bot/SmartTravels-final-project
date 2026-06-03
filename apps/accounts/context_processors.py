from django.db.models import Sum


def loyalty_context(request):
    loyalty_points = None
    loyalty_tier = None
    wallet_amount = 0
    if request.user.is_authenticated and getattr(request.user, 'role', None) == 'passenger':
        try:
            from apps.payments.models import Payment
            payments = Payment.objects.filter(passenger=request.user).exclude(method='loyalty')
            payment_total = payments.aggregate(total=Sum('amount'))['total'] or 0
            earned_points = int(payment_total / 100)  # 1 point per 100 KSH spent
            redeemed_points = getattr(request.user, 'redeemed_points', 0) or 0
            available_points = max(earned_points - redeemed_points, 0)
            if available_points >= 3000:
                loyalty_tier = 'Platinum'
            elif available_points >= 1500:
                loyalty_tier = 'Gold'
            else:
                loyalty_tier = 'Silver'
            loyalty_points = f"{available_points:,}"
            wallet_amount = getattr(request.user, 'wallet_balance', 0) or 0
        except Exception:
            loyalty_points = None
            loyalty_tier = 'Passenger'
            wallet_amount = 0
    return {
        'loyalty_points': loyalty_points,
        'loyalty_tier': loyalty_tier,
        'wallet_balance': f"KES {wallet_amount:,.2f}",
        'wallet_balance_raw': float(wallet_amount),
    }
