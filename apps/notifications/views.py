from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Notification

@login_required
def notification_list(request):
    notifs = Notification.objects.filter(user=request.user)
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/list.html', {'notifications': notifs})

@login_required
def unread_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})
