from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from .decorators import organizer_required
from .forms import EventForm, TicketTypeFormSet
from .models import Event
from .models import Category
from django.db.models import F
from django.contrib.auth.decorators import login_required
from .models import SavedEvent, EventInteraction, TicketType, Booking

@organizer_required
def dashboard(request):
    events = Event.objects.filter(organizer=request.user)
    return render(request, 'events/dashboard.html', {'events': events})


@organizer_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        formset = None
        if form.is_valid():
            with transaction.atomic():
                event = form.save(commit=False)
                event.organizer = request.user
                event.save()
                formset = TicketTypeFormSet(request.POST, instance=event)
                if formset.is_valid():
                    formset.save()
                    messages.success(request, 'Event created.')
                    return redirect('events:dashboard')
                transaction.set_rollback(True)
    else:
        form = EventForm()
        formset = TicketTypeFormSet()
    return render(request, 'events/event_form.html',
                  {'form': form, 'formset': formset, 'title': 'Create Event'})


@organizer_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.organizer != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        formset = TicketTypeFormSet(request.POST, instance=event)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Event updated.')
            return redirect('events:dashboard')
    else:
        form = EventForm(instance=event)
        formset = TicketTypeFormSet(instance=event)
    return render(request, 'events/event_form.html',
                  {'form': form, 'formset': formset, 'title': 'Edit Event'})


@organizer_required
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if event.organizer != request.user:
        raise PermissionDenied

    if request.method == 'POST':
        event.delete()
        messages.success(request, 'Event deleted.')
        return redirect('events:dashboard')
    return render(request, 'events/event_confirm_delete.html', {'event': event})

def event_list(request):
    events = Event.objects.filter(status=Event.Status.PUBLISHED)

    query = request.GET.get('q', '').strip()
    if query:
        events = events.filter(
            Q(title__icontains=query) | Q(description__icontains=query) | Q(venue__icontains=query)
        )

    category_slug = request.GET.get('category', '')
    if category_slug:
        events = events.filter(category__slug=category_slug)

    city = request.GET.get('city', '').strip()
    if city:
        events = events.filter(city__icontains=city)

    categories = Category.objects.all()

    return render(request, 'events/event_list.html', {
        'events': events,
        'categories': categories,
        'query': query,
        'selected_category': category_slug,
        'city': city,
    })

def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk, status=Event.Status.PUBLISHED)
    event.views = F('views') + 1
    event.save(update_fields=['views'])
    event.refresh_from_db(fields=['views'])

    if request.user.is_authenticated:
        EventInteraction.objects.create(user=request.user, event=event, interaction_type='view')
        is_saved = SavedEvent.objects.filter(user=request.user, event=event).exists()
    else:
        is_saved = False

    return render(request, 'events/event_detail.html', {'event': event, 'is_saved': is_saved})


@login_required
def event_book(request, pk):
    event = get_object_or_404(Event, pk=pk, status=Event.Status.PUBLISHED)

    if request.method == 'POST':
        ticket_type_id = request.POST.get('ticket_type')
        quantity = int(request.POST.get('quantity', 1))
        ticket_type = get_object_or_404(TicketType, pk=ticket_type_id, event=event)

        if quantity > ticket_type.tickets_available:
            messages.error(request, 'Not enough tickets available.')
            return redirect('events:event_detail', pk=event.pk)

        Booking.objects.create(
            user=request.user, event=event, ticket_type=ticket_type, quantity=quantity
        )
        EventInteraction.objects.create(user=request.user, event=event, interaction_type='book')
        messages.success(request, f'Booked {quantity} x {ticket_type.name}.')
        return redirect('events:event_detail', pk=event.pk)

    return redirect('events:event_detail', pk=event.pk)


@login_required
def event_save_toggle(request, pk):
    event = get_object_or_404(Event, pk=pk, status=Event.Status.PUBLISHED)
    saved, created = SavedEvent.objects.get_or_create(user=request.user, event=event)

    if not created:
        saved.delete()
        messages.info(request, 'Removed from saved events.')
    else:
        EventInteraction.objects.create(user=request.user, event=event, interaction_type='save')
        messages.success(request, 'Event saved.')

    return redirect('events:event_detail', pk=event.pk)


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user, status='confirmed').select_related('event', 'ticket_type')
    return render(request, 'events/my_bookings.html', {'bookings': bookings})