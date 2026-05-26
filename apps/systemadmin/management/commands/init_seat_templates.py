"""
Management command to initialize seat layout templates
Run: python manage.py init_seat_templates
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.systemadmin.models import (
    SeatClass, VehicleLayout, Seat, Company
)
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialize seat layout templates for buses, trains, and flights'

    def handle(self, *args, **options):
        self.stdout.write('Initializing seat templates...\n')

        # Create seat classes
        self.create_seat_classes()
        
        # Create bus templates
        self.create_bus_templates()
        
        # Create train templates
        self.create_train_templates()
        
        # Create flight templates
        self.create_flight_templates()

        self.stdout.write(self.style.SUCCESS('✓ Seat templates initialized successfully!'))

    def create_seat_classes(self):
        """Create standard seat classes"""
        self.stdout.write('Creating seat classes...')

        # Bus seat classes
        bus_classes = [
            {
                'name': 'normal',
                'display_name': 'Standard Seat',
                'color_code': '#2ecc71',
                'base_price': Decimal('1200'),
                'icon': '🚐',
            },
            {
                'name': 'vip',
                'display_name': 'VIP Seat',
                'color_code': '#9b59b6',
                'base_price': Decimal('1800'),
                'icon': '👑',
            },
            {
                'name': 'executive',
                'display_name': 'Executive Seat',
                'color_code': '#3498db',
                'base_price': Decimal('2500'),
                'icon': '💼',
            },
        ]

        for cls_data in bus_classes:
            SeatClass.objects.get_or_create(
                name=cls_data['name'],
                transport_type='bus',
                defaults={
                    'display_name': cls_data['display_name'],
                    'color_code': cls_data['color_code'],
                    'base_price': cls_data['base_price'],
                    'icon': cls_data['icon'],
                }
            )

        # Train seat classes
        train_classes = [
            {
                'name': 'economy',
                'display_name': 'Economy',
                'color_code': '#2ecc71',
                'base_price': Decimal('3000'),
                'icon': '🪑',
            },
            {
                'name': 'business',
                'display_name': 'Business',
                'color_code': '#3498db',
                'base_price': Decimal('6000'),
                'icon': '💼',
            },
            {
                'name': 'first_class',
                'display_name': 'First Class',
                'color_code': '#f39c12',
                'base_price': Decimal('9000'),
                'icon': '👑',
            },
        ]

        for cls_data in train_classes:
            SeatClass.objects.get_or_create(
                name=cls_data['name'],
                transport_type='train',
                defaults={
                    'display_name': cls_data['display_name'],
                    'color_code': cls_data['color_code'],
                    'base_price': cls_data['base_price'],
                    'icon': cls_data['icon'],
                }
            )

        # Flight seat classes
        flight_classes = [
            {
                'name': 'economy',
                'display_name': 'Economy',
                'color_code': '#2ecc71',
                'base_price': Decimal('8000'),
                'icon': '🛫',
            },
            {
                'name': 'business',
                'display_name': 'Business',
                'color_code': '#3498db',
                'base_price': Decimal('15000'),
                'icon': '💼',
            },
            {
                'name': 'first_class',
                'display_name': 'First Class',
                'color_code': '#f39c12',
                'base_price': Decimal('25000'),
                'icon': '👑',
            },
        ]

        for cls_data in flight_classes:
            SeatClass.objects.get_or_create(
                name=cls_data['name'],
                transport_type='flight',
                defaults={
                    'display_name': cls_data['display_name'],
                    'color_code': cls_data['color_code'],
                    'base_price': cls_data['base_price'],
                    'icon': cls_data['icon'],
                }
            )

        self.stdout.write(self.style.SUCCESS('✓ Seat classes created'))

    def create_bus_templates(self):
        """Create bus layout templates"""
        self.stdout.write('Creating bus templates...')

        # Get or create a default company
        company, _ = Company.objects.get_or_create(
            name='Default Company',
            defaults={
                'transport_type': 'bus',
                'is_active': True,
            }
        )

        templates = [
            {
                'template_name': '14-Seater Shuttle',
                'description': 'Compact shuttle bus with 2×2 layout',
                'total_seats': 14,
                'rows': 7,
                'columns': 2,
                'aisle_position': 2,
                'aisle_arrangement': '2x1_vip',
            },
            {
                'template_name': '25-Seater Mini Coach',
                'description': 'Standard mini coach with mixed seating',
                'total_seats': 25,
                'rows': 7,
                'columns': 4,
                'aisle_position': 2,
                'aisle_arrangement': '2x2',
            },
            {
                'template_name': '33-Seater Standard Coach',
                'description': 'Standard coach layout',
                'total_seats': 33,
                'rows': 7,
                'columns': 5,
                'aisle_position': 3,
                'aisle_arrangement': '3x2',
            },
            {
                'template_name': '49-Seater Dreamline Style',
                'description': 'Large luxury coach inspired by Dreamline',
                'total_seats': 49,
                'rows': 7,
                'columns': 7,
                'aisle_position': 4,
                'aisle_arrangement': '3x3',
            },
        ]

        for template_data in templates:
            layout, created = VehicleLayout.objects.get_or_create(
                company=company,
                template_name=template_data['template_name'],
                vehicle_type='bus',
                defaults={
                    'description': template_data['description'],
                    'total_seats': template_data['total_seats'],
                    'rows': template_data['rows'],
                    'columns': template_data['columns'],
                    'aisle_position': template_data['aisle_position'],
                    'aisle_arrangement': template_data['aisle_arrangement'],
                    'has_driver_cockpit': True,
                    'driver_location': 'front',
                    'has_doors': 2,
                    'is_template': True,
                }
            )
            if created:
                self.stdout.write(f'  ✓ Created: {template_data["template_name"]}')

    def create_train_templates(self):
        """Create train layout templates"""
        self.stdout.write('Creating train templates...')

        company, _ = Company.objects.get_or_create(
            name='Default Company',
            defaults={'transport_type': 'train', 'is_active': True}
        )

        templates = [
            {
                'template_name': 'Standard Train (3 Cabins)',
                'description': 'Standard train with First, Business, and Economy cabins',
                'total_seats': 200,
                'cabins': [
                    {'name': 'Cabin A', 'seats': 60, 'class': 'first_class'},
                    {'name': 'Cabin B', 'seats': 70, 'class': 'business'},
                    {'name': 'Cabin C', 'seats': 70, 'class': 'economy'},
                ],
            },
            {
                'template_name': 'Madaraka Express Style',
                'description': 'Luxury train similar to Madaraka Express',
                'total_seats': 150,
                'cabins': [
                    {'name': 'Suite Cabin', 'seats': 30, 'class': 'first_class'},
                    {'name': 'Standard Cabin', 'seats': 120, 'class': 'business'},
                ],
            },
        ]

        for template_data in templates:
            layout, created = VehicleLayout.objects.get_or_create(
                company=company,
                template_name=template_data['template_name'],
                vehicle_type='train',
                defaults={
                    'description': template_data['description'],
                    'total_seats': template_data['total_seats'],
                    'rows': 10,
                    'columns': 2,
                    'cabins': template_data.get('cabins', []),
                    'is_template': True,
                }
            )
            if created:
                self.stdout.write(f'  ✓ Created: {template_data["template_name"]}')

    def create_flight_templates(self):
        """Create flight layout templates"""
        self.stdout.write('Creating flight templates...')

        company, _ = Company.objects.get_or_create(
            name='Default Company',
            defaults={'transport_type': 'flight', 'is_active': True}
        )

        templates = [
            {
                'template_name': 'Narrow Body Aircraft (A320 style)',
                'description': '3-3 layout, typical for Airbus A320',
                'total_seats': 180,
                'rows': 30,
                'columns': 6,
                'aisle_position': 3,
                'emergency_exits': 4,
                'lavatory_locations': ['front', 'rear'],
            },
            {
                'template_name': 'Regional Aircraft (2-2 layout)',
                'description': 'Small regional aircraft',
                'total_seats': 90,
                'rows': 30,
                'columns': 4,
                'aisle_position': 2,
                'emergency_exits': 2,
                'lavatory_locations': ['rear'],
            },
            {
                'template_name': 'Wide Body Aircraft (2-4-2 layout)',
                'description': 'Large international aircraft',
                'total_seats': 300,
                'rows': 35,
                'columns': 10,
                'aisle_position': 5,
                'emergency_exits': 6,
                'lavatory_locations': ['front', 'mid', 'rear'],
            },
        ]

        for template_data in templates:
            layout, created = VehicleLayout.objects.get_or_create(
                company=company,
                template_name=template_data['template_name'],
                vehicle_type='flight',
                defaults={
                    'description': template_data['description'],
                    'total_seats': template_data['total_seats'],
                    'rows': template_data['rows'],
                    'columns': template_data['columns'],
                    'aisle_position': template_data['aisle_position'],
                    'emergency_exits': template_data.get('emergency_exits', 0),
                    'lavatory_locations': template_data.get('lavatory_locations', []),
                    'is_template': True,
                }
            )
            if created:
                self.stdout.write(f'  ✓ Created: {template_data["template_name"]}')
