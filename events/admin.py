from django.contrib import admin
from .models import Category, Event, TicketType, Booking, SavedEvent, EventInteraction
# Register your models here.

class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'category', 'date', 'status', 'views')
    list_filter = ('status', 'category', 'city')
    search_fields = ('title', 'venue', 'city')
    inlines = [TicketTypeInline]

from .models import Category, Event, TicketType, Booking, SavedEvent, EventInteraction

admin.site.register(Category)
admin.site.register(Booking)
admin.site.register(SavedEvent)
admin.site.register(EventInteraction)