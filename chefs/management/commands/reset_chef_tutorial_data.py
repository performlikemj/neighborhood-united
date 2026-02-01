from django.core.management.base import BaseCommand
from django.db import transaction

from custom_auth.models import CustomUser


class Command(BaseCommand):
    help = 'Reset all chef data for a user so tutorial screenshots start from a clean state'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username of the chef to reset')
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Required flag to confirm destructive operation',
        )
        parser.add_argument(
            '--keep-profile',
            action='store_true',
            help='Keep profile fields (experience, bio, photos) intact',
        )

    def handle(self, *args, **options):
        username = options['username']

        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'User "{username}" not found'))
            return

        from chefs.models import Chef
        try:
            chef = Chef.objects.get(user=user)
        except Chef.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'User "{username}" has no Chef profile'))
            return

        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    f'This will DELETE all chef data for "{username}" (id={chef.pk}).\n'
                    f'Pass --confirm to proceed.'
                )
            )
            return

        keep_profile = options['keep_profile']

        with transaction.atomic():
            self._reset_messaging(chef)
            self._reset_sous_chef(chef)
            self._reset_prep_plans(chef)
            self._reset_meal_plans(chef)
            self._reset_meal_events(chef)
            self._reset_meals_dishes_ingredients(chef)
            self._reset_service_orders(chef)
            self._reset_service_offerings(chef)
            self._reset_connections(chef)
            self._reset_payment_links(chef)
            self._reset_photos(chef)

            if not keep_profile:
                self._reset_profile_fields(chef)

        self.stdout.write(self.style.SUCCESS(
            f'Successfully reset tutorial data for "{username}"'
        ))

    def _delete_qs(self, qs, label):
        count, _ = qs.delete()
        if count:
            self.stdout.write(f'  Deleted {count} {label} object(s)')

    def _reset_messaging(self, chef):
        from messaging.models import Conversation
        self._delete_qs(Conversation.objects.filter(chef=chef), 'Conversation')

    def _reset_sous_chef(self, chef):
        from customer_dashboard.models import SousChefThread, FamilyInsight
        self._delete_qs(FamilyInsight.objects.filter(chef=chef), 'FamilyInsight')
        self._delete_qs(SousChefThread.objects.filter(chef=chef), 'SousChefThread')

    def _reset_prep_plans(self, chef):
        from chefs.resource_planning.models import ChefPrepPlan
        self._delete_qs(ChefPrepPlan.objects.filter(chef=chef), 'ChefPrepPlan')

    def _reset_meal_plans(self, chef):
        from meals.models import ChefMealPlan
        self._delete_qs(ChefMealPlan.objects.filter(chef=chef), 'ChefMealPlan')

    def _reset_meal_events(self, chef):
        from meals.models import ChefMealEvent, ChefMealReview
        self._delete_qs(ChefMealReview.objects.filter(chef=chef), 'ChefMealReview')
        self._delete_qs(ChefMealEvent.objects.filter(chef=chef), 'ChefMealEvent')

    def _reset_meals_dishes_ingredients(self, chef):
        from meals.models import Meal, Dish, Ingredient
        self._delete_qs(Meal.objects.filter(chef=chef), 'Meal')
        self._delete_qs(Dish.objects.filter(chef=chef), 'Dish')
        self._delete_qs(Ingredient.objects.filter(chef=chef), 'Ingredient')

    def _reset_service_orders(self, chef):
        from chef_services.models import ChefServiceOrder
        self._delete_qs(ChefServiceOrder.objects.filter(chef=chef), 'ChefServiceOrder')

    def _reset_service_offerings(self, chef):
        from chef_services.models import ChefServiceOffering
        self._delete_qs(ChefServiceOffering.objects.filter(chef=chef), 'ChefServiceOffering')

    def _reset_connections(self, chef):
        from chef_services.models import ChefCustomerConnection
        self._delete_qs(
            ChefCustomerConnection.objects.filter(chef=chef), 'ChefCustomerConnection'
        )

    def _reset_payment_links(self, chef):
        from chefs.models import ChefPaymentLink
        self._delete_qs(ChefPaymentLink.objects.filter(chef=chef), 'ChefPaymentLink')

    def _reset_photos(self, chef):
        from chefs.models import ChefPhoto
        self._delete_qs(ChefPhoto.objects.filter(chef=chef), 'ChefPhoto')

    def _reset_profile_fields(self, chef):
        chef.experience = ''
        chef.bio = ''
        chef.calendly_url = ''
        chef.profile_pic = ''
        chef.banner_image = None
        chef.is_live = False
        chef.is_on_break = False
        chef.sous_chef_emoji = ''
        chef.save()
        self.stdout.write('  Reset profile fields to empty')
