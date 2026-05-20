from django.urls import path
from . import views

urlpatterns = [
    path('checkout/<str:booking_reference>/',                  views.checkout,        name='payment_checkout'),
    path('checkout/<str:booking_reference>/<str:booking_type>/', views.checkout,      name='payment_checkout_typed'),
    path('pending/<int:payment_id>/',                          views.payment_pending, name='payment_pending'),
    path('success/<int:payment_id>/',                          views.payment_success, name='payment_success'),
    path('mpesa/callback/',                                    views.mpesa_callback,  name='mpesa_callback'),
    path('status/<int:payment_id>/',                           views.check_status,    name='payment_status'),
]
