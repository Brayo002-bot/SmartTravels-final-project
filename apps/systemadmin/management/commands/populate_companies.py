from django.core.management.base import BaseCommand
from apps.systemadmin.models import Company

class Command(BaseCommand):
    help = 'Populate initial transportation companies'

    def handle(self, *args, **options):
        companies_data = [
            {
                'name': 'Easy Coach',
                'transport_type': 'bus',
                'description': 'Leading bus transportation company in Kenya',
                'contact_email': 'info@easycoach.co.ke',
                'contact_phone': '+254 700 123 456',
                'address': 'Nairobi, Kenya'
            },
            {
                'name': 'Guardian Angel',
                'transport_type': 'bus',
                'description': 'Reliable bus services across Kenya',
                'contact_email': 'contact@guardianangel.co.ke',
                'contact_phone': '+254 711 234 567',
                'address': 'Mombasa, Kenya'
            },
            {
                'name': 'Kenya Railways (SGR)',
                'transport_type': 'train',
                'description': 'Standard Gauge Railway services',
                'contact_email': 'info@krc.co.ke',
                'contact_phone': '+254 722 345 678',
                'address': 'Nairobi, Kenya'
            },
            {
                'name': 'Jambo Jet',
                'transport_type': 'flight',
                'description': 'Domestic and regional flight services',
                'contact_email': 'reservations@jambojet.com',
                'contact_phone': '+254 733 456 789',
                'address': 'Nairobi, Kenya'
            },
            {
                'name': 'Kenyan Airways',
                'transport_type': 'flight',
                'description': 'National carrier of Kenya',
                'contact_email': 'info@kenya-airways.com',
                'contact_phone': '+254 711 001 000',
                'address': 'Nairobi, Kenya'
            }
        ]

        created_count = 0
        for company_data in companies_data:
            company, created = Company.objects.get_or_create(
                name=company_data['name'],
                defaults=company_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created company: {company.name}')
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(f'Company already exists: {company.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} companies')
        )