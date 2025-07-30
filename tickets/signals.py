from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Count, Q, Case, When, IntegerField, Sum
from datetime import datetime, timedelta
from django.utils import timezone
from .models import Ticket, CustomUser

@receiver(post_save, sender=Ticket)
def assign_new_ticket_and_set_sla(sender, instance, created, **kwargs):
    if created:
        if not instance.assigned_to:
            try:
                PRIORITY_WEIGHTS = {
                    'high': 3,
                    'medium': 2,
                    'low': 1,
                }

                MAX_AGENT_WEIGHT_CAP = 10

                agents_with_load = CustomUser.objects.filter(
                    role='agent',
                    is_active=True,
                ).annotate(
                    weighted_ticket_load = Sum(
                        Case(
                            When(assigned_tickets__status__in=['open', 'assigned', 'in_progress', 'reopened', 'awaiting_customer_response'],
                                 assigned_tickets__priority='high', then=PRIORITY_WEIGHTS['high']),
                            When(assigned_tickets__status__in=['open', 'assigned', 'in_progress', 'reopened', 'awaiting_customer_response'],
                                 assigned_tickets__priority='medium', then=PRIORITY_WEIGHTS['medium']),
                            When(assigned_tickets__status__in=['open', 'assigned', 'in_progress', 'reopened', 'awaiting_customer_response'],
                                 assigned_tickets__priority='low', then=PRIORITY_WEIGHTS['low']),
                            default=0,
                            output_field=IntegerField()
                        )
                    )
                )

                available_agents_below_cap = agents_with_load.filter(
                    weighted_ticket_load__lt=MAX_AGENT_WEIGHT_CAP
                ).order_by('weighted_ticket_load') 

                available_agent = available_agents_below_cap.first()

                if available_agent:
                    instance.assigned_to = available_agent
                    instance.status = 'assigned'
                    print(f"Ticket '{instance.title}' automatically assigned to {available_agent.username} (Load: {available_agent.weighted_ticket_load or 0})")
                else:
                    instance.status = 'open'
                    print(f"No active agents available below cap ({MAX_AGENT_WEIGHT_CAP} weight). Ticket '{instance.title}' remains open and unassigned.")
            except Exception as e:
                print(f"Error during weighted auto-assignment for ticket '{instance.title}': {e}")
        
        SLA_TARGETS = {
            'high': {'response': timedelta(hours=1), 'resolution': timedelta(hours=4)},
            'medium': {'response': timedelta(hours=4), 'resolution': timedelta(hours=24)},
            'low': {'response': timedelta(hours=24), 'resolution': timedelta(minutes=2)},
        }

        # Get the current time in the timezone defined in settings.py (USE_TZ = True)
        now = timezone.now()

        # Calculate due dates based on the ticket's priority
        priority_sla = SLA_TARGETS.get(instance.priority, SLA_TARGETS['low']) # Default to low if priority not found

        instance.response_due_at = now + priority_sla['response']
        instance.resolution_due_at = now + priority_sla['resolution']
        print(f"SLA set for Ticket '{instance.title}': Response Due: {instance.response_due_at}, Resolution Due: {instance.resolution_due_at}")

        # Save the instance again with assigned_to and SLA dates
        # Disconnect/reconnect to prevent recursion if this save triggers post_save again
        post_save.disconnect(assign_new_ticket_and_set_sla, sender=Ticket)
        instance.save()
        post_save.connect(assign_new_ticket_and_set_sla, sender=Ticket)
        

