from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('agent', 'Agent'),
        ('customer', 'Customer')
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

class Ticket(models.Model):
    PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    STATUS_CHOICES = [('open', "Open"), ('assigned', 'Assigned'), ('in_progress', 'In Progress'),('awaiting_customer_response', 'Awaiting Customer Response'),('resolved', 'Resolved'), ('reopened', 'Reopened'), ('closed', 'Closed')]

    title = models.CharField(max_length=255)
    description = models.TextField()
    create_by = models.ForeignKey(CustomUser, related_name='created_tickets', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(CustomUser, related_name='assigned_tickets', null=True, blank=True, on_delete=models.SET_NULL)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='low')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class Comment(models.Model):
    ticket = models.ForeignKey(Ticket, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, related_name='comments', on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Comment by {self.user.username} on {self.ticket.title}'