# tickets/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count,F,Q, Case, When, IntegerField, Q, Sum, Avg, ExpressionWrapper, fields # Added Sum, Avg, ExpressionWrapper, fields
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth # Added Trunc functions
from django.utils import timezone
from datetime import timedelta

from .models import *
from .decorators import role_required

from dotenv import load_dotenv
import os
load_dotenv()

# For AI API call
import json
import asyncio
import aiohttp

# --- Authentication Views ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = auth.authenticate(username=username, password=password)
        
        if user is not None:
            auth.login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'tickets/login.html', {'error_message': 'Invalid credentials'})
    return render(request, 'login.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role", "customer")

        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return redirect('register_view')

        if CustomUser.objects.filter(username=username).exists():
            messages.warning(request, "Username already exists. Please choose a different one.")
            return redirect('register_view')
        
        if CustomUser.objects.filter(email=email).exists():
            messages.warning(request, "Email already registered. Please use a different email or login.")
            return redirect('register_view')

        try:
            user = CustomUser.objects.create_user(username=username, email=email, password=password)
            user.role = role
            user.save()
            messages.success(request, "Registration successful! Please log in.")
            return redirect('login_view')
        except Exception as e:
            messages.error(f"An error occurred during registration: {e}")
            return redirect('register_view')
    
    return render(request, 'register.html')

@login_required(login_url='login_view')
def logout_view(request):
    auth.logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login_view')

# --- Ticket Management Views ---
@login_required(login_url='login_view')
def dashboard(request):
    STATUS_ORDER = Case(
        When(status='open', then=0),
        When(status='assigned', then=1),
        When(status='in_progress', then=2),
        When(status='reopened', then=3),
        When(status='awaiting_customer_response', then=4),
        When(status='resolved', then=5),
        When(status='closed', then=6),
        default=7,
        output_field=IntegerField()
    )

    if request.user.role == 'customer':
        tickets = Ticket.objects.filter(create_by=request.user).order_by(
            Case(
                When(priority='high', then=0),
                When(priority='medium', then=1),
                When(priority='low', then=2),
                default=3,
                output_field=IntegerField(),
            ),
            STATUS_ORDER,
            '-created_at'
        )
    elif request.user.role == 'agent':
        tickets = Ticket.objects.filter(assigned_to=request.user).exclude(status='closed').order_by(
            Case(
                When(priority='high', then=0),
                When(priority='medium', then=1),
                When(priority='low', then=2),
                default=3,
                output_field=IntegerField(),
            ),
            STATUS_ORDER,
            '-created_at'
        )
    else:
        tickets = Ticket.objects.all().order_by(
            Case(
                When(priority='high', then=0),
                When(priority='medium', then=1),
                When(priority='low', then=2),
                default=3,
                output_field=IntegerField(),
            ),
            STATUS_ORDER,
            '-created_at'
        )
    
    return render(request, 'dashboard.html', {'tickets': tickets})


# Function to predict priority using Gemini API
async def predict_priority_ai(title, description, user_role):
    api_key = os.environ.get('GEMINI_API_KEY')
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    prompt = f"""
    Analyze the following support ticket details and determine its priority (high, medium, or low).
    Consider the title, description, and the role of the user creating the ticket.
    
    Use these guidelines for priority:
    - High: Critical system down, security breach, major disruption affecting many users, production issue.
    - Medium: Service degradation, minor bugs, issues affecting some users, non-critical errors.
    - Low: General questions, feature requests, cosmetic issues, minor non-critical problems.

    User Role: {user_role}
    Ticket Title: {title}
    Ticket Description: {description}

    Provide the output as a JSON object with a single key "priority" and its value.
    Example: {{"priority": "high"}}
    """

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "priority": {
                        "type": "STRING",
                        "enum": ["low", "medium", "high"]
                    }
                },
                "required": ["priority"]
            }
        }
    }

    headers = {
        'Content-Type': 'application/json'
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(api_url, headers=headers, data=json.dumps(payload)) as response:
                response.raise_for_status()
                result = await response.json()
                
                if result and result.get("candidates") and len(result["candidates"]) > 0 and \
                   result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts") and \
                   len(result["candidates"][0]["content"]["parts"]) > 0:
                    
                    json_string = result["candidates"][0]["content"]["parts"][0]["text"]
                    parsed_json = json.loads(json_string)
                    
                    predicted_priority = parsed_json.get("priority", "low")
                    
                    if predicted_priority not in ['low', 'medium', 'high']:
                        print(f"Gemini returned an invalid priority: {predicted_priority}. Defaulting to low.")
                        return "low"
                    
                    return predicted_priority
                else:
                    print("Gemini response structure unexpected or missing content.")
                    return "low"
        except aiohttp.ClientError as e:
            print(f"HTTP error during Gemini API call: {e}")
            return "low"
        except json.JSONDecodeError as e:
            print(f"JSON decode error from Gemini response: {e}")
            return "low"
        except Exception as e:
            print(f"An unexpected error occurred during Gemini API call: {e}")
            return "low"


@login_required(login_url='login_view')
@role_required(allowed_roles=['customer'])
def create_ticket(request):
    if request.method == "POST":
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if not title or not description:
            messages.error(request, "Title and description are required.")
            return render(request, 'create_ticket.html', {'title': title, 'description': description})

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            predicted_priority = loop.run_until_complete(predict_priority_ai(title, description, request.user.role))
            loop.close()

            ticket = Ticket.objects.create(
                title=title,
                description=description,
                priority=predicted_priority,
                create_by=request.user
            )
            messages.success(request, f"Ticket created successfully with AI-determined priority: {predicted_priority.upper()}! It will be assigned to an agent shortly.")
            return redirect('ticket_detail', pk=ticket.pk)
        except Exception as e:
            messages.error(f"An error occurred while creating the ticket: {e}")
            return render(request, 'create_ticket.html', {'title': title, 'description': description})
        
    return render(request, 'create_ticket.html')

@login_required(login_url='login_view')
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket, id=pk)

    reopenable_statuses = ['resolved', 'closed']

    if request.user.role == 'customer' and ticket.create_by != request.user:
        messages.error(request, "You do not have permission to view this ticket.")
        return redirect('dashboard')

    if request.method == "POST":
        if 'comment_text' in request.POST:
            comment_text = request.POST.get('comment_text')
            if not comment_text:
                messages.error(request, "Comment cannot be empty.")
            else:
                try:
                    Comment.objects.create(
                        text=comment_text,
                        ticket=ticket,
                        user=request.user
                    )
                    messages.success(request, "Comment added successfully!")
                    if request.user.role == 'customer' and ticket.status in reopenable_statuses:
                        ticket.status = 'reopened'
                        ticket.save()
                        messages.info(request, "Ticket has been automatically reopened due to your new comment.")
                    return redirect('ticket_detail', pk=ticket.pk)
                except Exception as e:
                    messages.error(f"Error adding comment: {e}")
        
        elif 'reopen_ticket' in request.POST and request.user.role == 'customer' and ticket.status in reopenable_statuses:
            ticket.status = 'reopened'
            ticket.save()
            messages.success(request, "Ticket has been reopened!")
            return redirect('ticket_detail', pk=ticket.pk)
    
    comments = ticket.comments.all().order_by('created_at')
    return render(request, 'ticket_detail.html', {
        'ticket': ticket,
        'comments': comments,
        'reopenable_statuses': reopenable_statuses,
    })

@login_required(login_url='login_view')
@role_required(allowed_roles=['agent', 'admin'])
def update_ticket(request, pk):
    ticket = get_object_or_404(Ticket, id=pk)
    
    if request.method == "POST":
        priority = request.POST.get('priority')
        status = request.POST.get('status')
        
        ticket.priority = priority
        ticket.status = status

        if request.user.role == 'admin':
            assigned_to_id = request.POST.get('assigned_to')
            assigned_to_user = None
            if assigned_to_id:
                try:
                    assigned_to_user = CustomUser.objects.get(id=assigned_to_id)
                except CustomUser.DoesNotExist:
                    messages.error(request, "Invalid agent selected for assignment.")
                    agents = CustomUser.objects.filter(role='agent')
                    return render(request, 'update_ticket.html', {'ticket': ticket, 'agents': agents})
            
            ticket.assigned_to = assigned_to_user
        
        try:
            ticket.save()
            messages.success(request, "Ticket updated successfully!")
            return redirect('ticket_detail', pk=ticket.pk)
        except Exception as e:
            messages.error(f"Error updating ticket: {e}")
            agents = CustomUser.objects.filter(role='agent')
            return render(request, 'update_ticket.html', {'ticket': ticket, 'agents': agents})
    
    agents = CustomUser.objects.filter(role='agent') if request.user.role == 'admin' else None
    
    return render(request, 'update_ticket.html', {'ticket': ticket, 'agents': agents})

@login_required(login_url='login_view')
@role_required(allowed_roles=['admin'])
def delete_ticket(request, pk):
    ticket = get_object_or_404(Ticket, id=pk)
    if request.method == "POST":
        try:
            ticket.delete()
            messages.success(request, f"Ticket '{ticket.title}' deleted successfully!")
            return redirect('dashboard')
        except Exception as e:
            messages.error(f"Error deleting ticket: {e}")
            return redirect('ticket_detail', pk=ticket.pk)
    
    return render(request, 'confirm_delete.html', {'ticket': ticket})


# --- Analytics Dashboards ---
@login_required(login_url='login_view')
@role_required(allowed_roles=['admin']) # Only admins can see agent performance
def agent_performance_dashboard(request):
    # Calculate Average Resolution Time for closed tickets
    agent_stats = CustomUser.objects.filter(role='agent', is_active=True).annotate(
        active_tickets_count=Count('assigned_tickets', filter=~Q(assigned_tickets__status='closed')),
        closed_tickets_count=Count('assigned_tickets', filter=Q(assigned_tickets__status='closed')),
        
        # Average Resolution Time for tickets closed by this agent
        # Using ExpressionWrapper to calculate duration and then Avg
        avg_resolution_duration_seconds=Avg(
            ExpressionWrapper(
                F('assigned_tickets__updated_at') - F('assigned_tickets__created_at'),
                output_field=fields.DurationField()
            ),
            filter=Q(assigned_tickets__status='closed')
        )
    ).order_by('username')

    # Convert timedelta to a more readable format (e.g., minutes or hours) for display
    for agent in agent_stats:
        if agent.avg_resolution_duration_seconds:
            # Convert timedelta object to total seconds, then minutes
            agent.avg_resolution_minutes = round(agent.avg_resolution_duration_seconds.total_seconds() / 60, 2)
        else:
            agent.avg_resolution_minutes = None

    # Calculate System-wide SLA compliance for closed tickets
    total_closed_tickets = Ticket.objects.filter(status='closed').count()
    
    # SLA compliance checks:
    # Need to ensure first_response_at is tracked for accurate response SLA
    # For now, using a simplified check (updated_at vs response_due_at)
    sla_met_response = Ticket.objects.filter(
        status='closed',
        updated_at__lt=F('response_due_at') # Simplified: assumes updated_at is first response
    ).count()
    
    sla_met_resolution = Ticket.objects.filter(
        status='closed',
        updated_at__lt=F('resolution_due_at')
    ).count()

    sla_response_compliance = (sla_met_response / total_closed_tickets * 100) if total_closed_tickets else 0
    sla_resolution_compliance = (sla_met_resolution / total_closed_tickets * 100) if total_closed_tickets else 0


    context = {
        'agent_stats': agent_stats,
        'sla_response_compliance': round(sla_response_compliance, 2),
        'sla_resolution_compliance': round(sla_resolution_compliance, 2),
        'total_closed_tickets': total_closed_tickets,
    }
    return render(request, 'agent_performance_dashboard.html', context)


@login_required(login_url='login_view')
@role_required(allowed_roles=['admin'])
def ticket_trend_dashboard(request):
    # Get period from GET parameter, default to 'month'
    period = request.GET.get('period', 'month')
    
    end_date = timezone.now()
    
    if period == 'week':
        start_date = end_date - timedelta(weeks=1)
        trunc_func = TruncDay
        date_format = "%Y-%m-%d"
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
        trunc_func = TruncDay
        date_format = "%Y-%m-%d"
    elif period == 'quarter':
        start_date = end_date - timedelta(days=90)
        trunc_func = TruncWeek
        date_format = "%Y-W%W" # Week number
    elif period == 'year':
        start_date = end_date - timedelta(days=365)
        trunc_func = TruncMonth
        date_format = "%Y-%m"
    else: # Default to month if invalid period
        period = 'month'
        start_date = end_date - timedelta(days=30)
        trunc_func = TruncDay
        date_format = "%Y-%m-%d"

    # Aggregate tickets created over time
    tickets_created_data = Ticket.objects.filter(
        created_at__range=(start_date, end_date)
    ).annotate(
        period=trunc_func('created_at')
    ).values('period').annotate(
        count=Count('id')
    ).order_by('period')

    # Aggregate tickets closed over time
    tickets_closed_data = Ticket.objects.filter(
        status='closed',
        updated_at__range=(start_date, end_date)
    ).annotate(
        period=trunc_func('updated_at')
    ).values('period').annotate(
        count=Count('id')
    ).order_by('period')

    # Prepare data for Chart.js for trends
    created_labels = []
    created_counts = []
    for entry in tickets_created_data:
        created_labels.append(entry['period'].strftime(date_format))
        created_counts.append(entry['count'])

    closed_labels = []
    closed_counts = []
    for entry in tickets_closed_data:
        closed_labels.append(entry['period'].strftime(date_format))
        closed_counts.append(entry['count'])

    # Current status distribution
    status_distribution_data = Ticket.objects.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    status_labels = [item['status'].replace('_', ' ').capitalize() for item in status_distribution_data]
    status_counts = [item['count'] for item in status_distribution_data]

    # Current priority distribution
    priority_distribution_data = Ticket.objects.values('priority').annotate(
        count=Count('id')
    ).order_by(
        Case(
            When(priority='high', then=0),
            When(priority='medium', then=1),
            When(priority='low', then=2),
            default=3,
            output_field=IntegerField(),
        )
    )
    priority_labels = [item['priority'].capitalize() for item in priority_distribution_data]
    priority_counts = [item['count'] for item in priority_distribution_data]
        
    context = {
        'period': period,
        'created_labels': json.dumps(created_labels), # Pass as JSON string
        'created_counts': json.dumps(created_counts), # Pass as JSON string
        'closed_labels': json.dumps(closed_labels),   # Pass as JSON string
        'closed_counts': json.dumps(closed_counts),   # Pass as JSON string
        'status_labels': json.dumps(status_labels),
        'status_counts': json.dumps(status_counts),
        'priority_labels': json.dumps(priority_labels),
        'priority_counts': json.dumps(priority_counts),
    }
    return render(request, 'ticket_trend_dashboard.html', context)
