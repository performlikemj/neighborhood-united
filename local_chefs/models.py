from django.db import models

class PostalCode(models.Model):
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.code


class ChefPostalCode(models.Model):
    chef = models.ForeignKey('chefs.Chef', on_delete=models.CASCADE)
    postal_code = models.ForeignKey(PostalCode, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('chef', 'postal_code')


    def __str__(self):
        return f"{self.chef.user.username} - {self.postal_code.code}"