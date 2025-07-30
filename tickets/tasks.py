# tickets/tasks.py
from django.utils import timezone
from django.db.models import Q, Case, When, IntegerField, Sum # Import necessary for weighted load
from .models import Ticket, CustomUser, Comment
from datetime import timedelta
from celery import shared_task

@shared_task
def check_overdue_tickets():
    """
    Checks for tickets that have exceeded their resolution_due_at time
    and performs escalation actions.
    """
    now = timezone.now()

    # Find tickets that are not closed and whose resolution_due_at has passed
    # Exclude tickets that are already 'high' priority and overdue to prevent redundant escalation
    overdue_tickets = Ticket.objects.filter(
        status__in=['open', 'assigned', 'in_progress', 'reopened', 'awaiting_customer_response'], # Include new active statuses
        resolution_due_at__lt=now
    ).exclude(
        Q(priority='high') & Q(status__in=['open', 'assigned', 'in_progress', 'reopened', 'awaiting_customer_response'])
    )

    if not overdue_tickets.exists():
        print("No overdue tickets found.")
        return

    print(f"Found {overdue_tickets.count()} overdue tickets. Initiating escalation...")

    # Get or create a system user for automated comments
    system_user, created = CustomUser.objects.get_or_create(
        username='system_bot',
        defaults={'email': 'bot@yourdomain.com', 'role': 'admin', 'is_staff': True, 'is_active': True}
    )
    if created:
        print("Created system_bot user for automated actions.")

    for ticket in overdue_tickets:
        print(f"Escalating Ticket ID: {ticket.id}, Title: '{ticket.title}'")

        # 1. Update Priority (if not already high)
        original_priority = ticket.priority
        if ticket.priority == 'low':
            ticket.priority = 'medium'
        elif ticket.priority == 'medium':
            ticket.priority = 'high'
        # If it's already high, keep it high.

        # 2. Add an internal comment (for audit trail)
        comment_text = f"AUTOMATED ESCALATION: This ticket has exceeded its resolution SLA. Priority escalated from {original_priority.upper()} to {ticket.priority.upper()}."
        Comment.objects.create(
            ticket=ticket,
            user=system_user,
            text=comment_text
        )
        print(f"  - Added automated comment to ticket {ticket.id}")

        # 3. (Optional) Send Notifications (requires email setup)
        # from django.core.mail import send_mail
        # if ticket.assigned_to:
        #     send_mail(
        #         f"URGENT: Ticket #{ticket.id} - {ticket.title} is OVERDUE!",
        #         f"Ticket #{ticket.id} assigned to you is overdue for resolution. Current priority: {ticket.priority.upper()}.\n\nLink: http://127.0.0.1:8000/tickets/{ticket.id}/",
        #         "noreply@yourdomain.com", # From email
        #         [ticket.assigned_to.email], # To email (assigned agent)
        #         fail_silently=False,
        #     )
        #     print(f"  - Sent overdue notification to agent {ticket.assigned_to.username}")

        # 4. (Optional) Re-assign to a different agent/team lead
        # This logic can be complex, e.g., finding the least busy admin or a specialized team.
        # if ticket.assigned_to and ticket.priority == 'high' and ticket.assigned_to.role == 'agent':
        #     try:
        #         admin_user = CustomUser.objects.filter(role='admin').first()
        #         if admin_user and admin_user != ticket.assigned_to:
        #             ticket.assigned_to = admin_user
        #             print(f"  - Re-assigned ticket {ticket.id} to admin {admin_user.username} due to high priority overdue.")
        #     except Exception as e:
        #         print(f"  - Error during re-assignment: {e}")

        # Save the changes to the ticket
        ticket.save()
        print(f"Ticket {ticket.id} escalation complete.")


@shared_task
def assign_unassigned_tickets():
    """
    Periodically checks for unassigned tickets (status 'open', assigned_to is None)
    and attempts to assign them to agents based on weighted load and cap.
    """
    print("Running assign_unassigned_tickets task...")
    
    unassigned_tickets = Ticket.objects.filter(
        status='open',
        assigned_to__isnull=True # Only unassigned tickets
    ).order_by('created_at') # Prioritize older unassigned tickets

    if not unassigned_tickets.exists():
        print("No unassigned tickets found to assign.")
        return

    # Define weights for each priority level (same as in signals.py)
    PRIORITY_WEIGHTS = {
        'high': 3,
        'medium': 2,
        'low': 1,
    }
    # Define the maximum weighted load an agent should take (same as in signals.py)
    MAX_AGENT_WEIGHT_CAP = 10

    # Get or create a system user for automated comments (for assignment comment)
    system_user, created = CustomUser.objects.get_or_create(
        username='system_bot',
        defaults={'email': 'bot@yourdomain.com', 'role': 'admin', 'is_staff': True, 'is_active': True}
    )
    if created:
        print("Created system_bot user for automated actions.")


    for ticket in unassigned_tickets:
        try:
            # Annotate agents with their weighted active ticket count
            agents_with_load = CustomUser.objects.filter(
                role='agent',
                is_active=True
            ).annotate(
                weighted_ticket_load=Sum(
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
            
            # Filter to only consider agents whose current load is below the cap
            available_agents_below_cap = agents_with_load.filter(
                weighted_ticket_load__lt=MAX_AGENT_WEIGHT_CAP
            ).order_by('weighted_ticket_load')

            available_agent = available_agents_below_cap.first()

            if available_agent:
                ticket.assigned_to = available_agent
                ticket.status = 'assigned' # Change status to assigned
                ticket.save() # Save the ticket with new assignment

                # Add a comment about the automated assignment
                Comment.objects.create(
                    ticket=ticket,
                    user=system_user,
                    text=f"AUTOMATED ASSIGNMENT: This ticket was unassigned and has now been assigned to {available_agent.username}."
                )
                print(f"Ticket '{ticket.title}' (ID: {ticket.id}) assigned to {available_agent.username} via background task.")
            else:
                print(f"No agent available below cap for ticket '{ticket.title}' (ID: {ticket.id}). It remains unassigned.")
        
        except Exception as e:
            print(f"Error during background assignment for ticket '{ticket.title}' (ID: {ticket.id}): {e}")

