from django.contrib.auth.models import AbstractUser
from django.db import models


ROLE_CHOICES = [
    ('EMPLOYEE', 'Employee'),
    ('MANAGER', 'Manager'),
    ('HR', 'HR'),
    ('IT', 'IT'),
    ('FINANCE', 'Finance'),
    ('ADMIN', 'Admin'),
]


class User(AbstractUser):
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='EMPLOYEE')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        db_table = 'accounts_user'

    def __str__(self):
        return f"{self.email} ({self.role})"
