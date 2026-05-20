from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate
from apps.accounts.models import User

class Command(BaseCommand):
    help = 'Test login credentials for debugging'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to test')
        parser.add_argument('password', type=str, help='Password to test')

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']

        self.stdout.write(f'Testing login for email: {email}')

        # Find users with this email
        users_with_email = User.objects.filter(email__iexact=email)
        if not users_with_email.exists():
            self.stdout.write(
                self.style.ERROR(f'No users found with email: {email}')
            )
            return

        self.stdout.write(f'Found {users_with_email.count()} user(s) with this email:')
        for user in users_with_email:
            self.stdout.write(f'  - Username: {user.username}, Role: {user.role}, Is active: {user.is_active}')

        # Try authentication with the first user
        user_obj = users_with_email.first()
        self.stdout.write(f'Attempting authentication with username: {user_obj.username}')

        auth_user = authenticate(username=user_obj.username, password=password)
        if auth_user:
            self.stdout.write(
                self.style.SUCCESS(f'Authentication successful for user: {auth_user.username} (Role: {auth_user.role})')
            )
        else:
            self.stdout.write(
                self.style.ERROR('Authentication failed. Possible issues:')
            )
            self.stdout.write('  - Incorrect password')
            self.stdout.write('  - User account is not active')
            self.stdout.write('  - Password was not set properly in Django admin')

            # Check if user is active
            if not user_obj.is_active:
                self.stdout.write('  - User account is deactivated')