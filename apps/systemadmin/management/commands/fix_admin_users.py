from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.systemadmin.models import SystemAdminRole

class Command(BaseCommand):
    help = 'Fix system admin users created in Django admin'

    def handle(self, *args, **options):
        # Find users with role='admin' but no SystemAdminRole
        admin_users = User.objects.filter(role='admin')
        fixed_count = 0

        for user in admin_users:
            if not hasattr(user, 'system_admin_role') or user.system_admin_role is None:
                # Create SystemAdminRole for this user
                SystemAdminRole.objects.get_or_create(
                    user=user,
                    defaults={'role': 'super_admin'}
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Created SystemAdminRole for user: {user.username}')
                )
                fixed_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'User {user.username} already has SystemAdminRole')
                )

        # Find users with empty role that should be admin
        empty_role_users = User.objects.filter(role='')
        for user in empty_role_users:
            # Check if they should be admin based on username or other criteria
            # For now, let's assume users with 'admin' in username should be admin
            if 'admin' in user.username.lower() or user.is_superuser:
                user.role = 'admin'
                user.save()
                # Create SystemAdminRole
                SystemAdminRole.objects.get_or_create(
                    user=user,
                    defaults={'role': 'super_admin'}
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Fixed user {user.username}: set role to admin and created SystemAdminRole')
                )
                fixed_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'Successfully fixed {fixed_count} users')
        )