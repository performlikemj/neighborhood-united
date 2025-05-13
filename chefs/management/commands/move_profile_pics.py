from django.core.management.base import BaseCommand
import os
import shutil
from django.conf import settings
from chefs.models import Chef

class Command(BaseCommand):
    help = "Move chef profile pictures to the new media directory"

    def handle(self, *args, **kwargs):
        for chef in Chef.objects.all():
            if chef.profile_pic:
                old_image_path = chef.profile_pic.path
                new_image_path = os.path.join(settings.MEDIA_ROOT, chef.profile_pic.name)

                if not os.path.exists(os.path.dirname(new_image_path)):
                    os.makedirs(os.path.dirname(new_image_path))

                shutil.move(old_image_path, new_image_path)
                chef.profile_pic.name = os.path.join('chefs/profile_pics', os.path.basename(new_image_path))
                chef.save()

                self.stdout.write(self.style.SUCCESS(f'Moved {old_image_path} to {new_image_path}'))
