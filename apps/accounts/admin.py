# apps/accounts/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import (
    UserChangeForm,
    UserCreationForm
)
from django import forms

from .models import User


class CustomUserCreationForm(UserCreationForm):

    email = forms.EmailField(required=True)

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True
    )

    phone_number = forms.CharField(
        max_length=20,
        required=False
    )

    company = forms.ModelChoiceField(
        queryset=None,
        required=False
    )

    class Meta:
        model = User

        fields = (
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'company',
        )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        from apps.systemadmin.models import Company

        self.fields['company'].queryset = Company.objects.all()

    def clean(self):

        cleaned_data = super().clean()

        role = cleaned_data.get('role')
        company = cleaned_data.get('company')

        company_required_roles = [
            'bus_admin',
            'train_admin',
            'flight_admin',
            'driver'
        ]

        # Require company for specific roles
        if role in company_required_roles and not company:
            raise forms.ValidationError(
                "Company is required for this role."
            )

        # Remove company for admin/passenger
        if role in ['admin', 'passenger']:
            cleaned_data['company'] = None

        return cleaned_data

    def save(self, commit=True):

        user = super().save(commit=False)

        user.email = self.cleaned_data['email']

        # Username mirrors email
        user.username = self.cleaned_data['email']

        user.first_name = self.cleaned_data.get('first_name')

        user.last_name = self.cleaned_data.get('last_name')

        user.role = self.cleaned_data['role']

        user.phone_number = self.cleaned_data.get('phone_number')

        user.company = self.cleaned_data.get('company')

        if commit:
            user.save()

        return user


class CustomUserChangeForm(UserChangeForm):

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True
    )

    phone_number = forms.CharField(
        max_length=20,
        required=False
    )

    company = forms.ModelChoiceField(
        queryset=None,
        required=False
    )

    class Meta:
        model = User

        fields = (
            'email',
            'first_name',
            'last_name',
            'role',
            'phone_number',
            'company',
            'is_active',
            'is_staff',
            'is_superuser',
        )

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        from apps.systemadmin.models import Company

        self.fields['company'].queryset = Company.objects.all()

    def clean(self):

        cleaned_data = super().clean()

        role = cleaned_data.get('role')
        company = cleaned_data.get('company')

        company_required_roles = [
            'bus_admin',
            'train_admin',
            'flight_admin',
            'driver'
        ]

        # Require company for specific roles
        if role in company_required_roles and not company:
            raise forms.ValidationError(
                "Company is required for this role."
            )

        # Remove company for admin/passenger
        if role in ['admin', 'passenger']:
            cleaned_data['company'] = None

        return cleaned_data

    def save(self, commit=True):

        user = super().save(commit=False)

        # Username mirrors email
        user.username = user.email

        user.role = self.cleaned_data['role']

        user.phone_number = self.cleaned_data.get('phone_number')

        user.company = self.cleaned_data.get('company')

        if commit:
            user.save()

        return user


@admin.register(User)
class UserAdmin(DjangoUserAdmin):

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    model = User

    ordering = ('email',)

    list_display = (
        'email',
        'first_name',
        'last_name',
        'role',
        'is_staff',
        'is_active',
    )

    list_filter = (
        'role',
        'is_staff',
        'is_superuser',
        'is_active',
    )

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'email',
                    'password',
                )
            },
        ),

        (
            'Personal Info',
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'phone_number',
                )
            },
        ),

        (
            'Role & Company',
            {
                'fields': (
                    'role',
                    'company',
                )
            },
        ),

        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),

        (
            'Important Dates',
            {
                'fields': (
                    'last_login',
                    'date_joined',
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),

                'fields': (
                    'email',
                    'first_name',
                    'last_name',
                    'password1',
                    'password2',
                    'role',
                    'phone_number',
                    'company',
                ),
            },
        ),
    )

    search_fields = (
        'email',
        'first_name',
        'last_name',
    )

    filter_horizontal = (
        'groups',
        'user_permissions',
    )

    def save_model(self, request, obj, form, change):

        # Ensure username matches email
        obj.username = obj.email

        # Remove company for admin/passenger roles
        if obj.role in ['admin', 'passenger']:
            obj.company = None

        # Use super() so Django's UserAdmin handles password hashing
        # and the two-step add_view save process correctly.
        super().save_model(request, obj, form, change)

        if obj.pk is None:
            # Ensure object is saved before related filters are used
            obj.save()

        # Create SystemAdminRole for admin users
        if obj.role == 'admin':
            from apps.systemadmin.models import SystemAdminRole

            SystemAdminRole.objects.get_or_create(
                user_id=obj.id,
                defaults={
                    'role': 'super_admin'
                }
            )

        # Clean up SystemAdminRole if role changed away from admin
        elif change and obj.role != 'admin':
            from apps.systemadmin.models import SystemAdminRole

            SystemAdminRole.objects.filter(user_id=obj.id).delete()