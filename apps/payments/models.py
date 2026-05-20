import base64, requests
from datetime import datetime
from django.db import models
from django.conf import settings as django_settings

class Payment(models.Model):
    METHOD = [('mpesa','M-Pesa'),('card','Card'),('cash','Cash'),('loyalty','Loyalty Points')]
    STATUS = [('pending','Pending'),('completed','Completed'),('failed','Failed'),('refunded','Refunded')]

    booking_reference = models.CharField(max_length=30)
    booking_type      = models.CharField(max_length=10, default='bus')  # bus/train/flight
    passenger         = models.ForeignKey(django_settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    amount            = models.DecimalField(max_digits=10, decimal_places=2)
    method            = models.CharField(max_length=10, choices=METHOD, default='mpesa')
    status            = models.CharField(max_length=10, choices=STATUS, default='pending')
    phone_number      = models.CharField(max_length=20, blank=True)
    mpesa_ref         = models.CharField(max_length=50, blank=True)
    mpesa_code        = models.CharField(max_length=30, blank=True)
    merchant_ref      = models.CharField(max_length=100, blank=True)
    notes             = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    completed_at      = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.booking_reference} | {self.method} | KES {self.amount} | {self.status}"

    def mark_completed(self, code=''):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        if code:
            self.mpesa_code = code
        self.save()


class MPesaService:
    SANDBOX = 'https://sandbox.safaricom.co.ke'
    PROD    = 'https://api.safaricom.co.ke'

    def __init__(self):
        self.env      = getattr(django_settings, 'MPESA_ENVIRONMENT', 'sandbox')
        self.base     = self.PROD if self.env == 'production' else self.SANDBOX
        self.key      = getattr(django_settings, 'MPESA_CONSUMER_KEY', '')
        self.secret   = getattr(django_settings, 'MPESA_CONSUMER_SECRET', '')
        self.shortcode= getattr(django_settings, 'MPESA_SHORTCODE', '174379')
        self.passkey  = getattr(django_settings, 'MPESA_PASSKEY', '')
        self.callback = getattr(django_settings, 'MPESA_CALLBACK_URL', '')

    def get_token(self):
        creds = base64.b64encode(f'{self.key}:{self.secret}'.encode()).decode()
        r = requests.get(f'{self.base}/oauth/v1/generate?grant_type=client_credentials',
                         headers={'Authorization': f'Basic {creds}'}, timeout=20)
        return r.json().get('access_token', '')

    def _password_ts(self):
        ts = datetime.now().strftime('%Y%m%d%H%M%S')
        pw = base64.b64encode(f'{self.shortcode}{self.passkey}{ts}'.encode()).decode()
        return pw, ts

    def stk_push(self, phone, amount, reference):
        token = self.get_token()
        pw, ts = self._password_ts()
        phone = self._norm(phone)
        r = requests.post(f'{self.base}/mpesa/stkpush/v1/processrequest',
            json={
                'BusinessShortCode': self.shortcode, 'Password': pw, 'Timestamp': ts,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount), 'PartyA': phone, 'PartyB': self.shortcode,
                'PhoneNumber': phone, 'CallBackURL': self.callback,
                'AccountReference': reference, 'TransactionDesc': f'SmartTravels {reference}',
            },
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            timeout=30)
        return r.json()

    @staticmethod
    def _norm(ph):
        ph = ph.replace(' ','').replace('-','').replace('+','')
        if ph.startswith('0'): ph = '254' + ph[1:]
        return ph
