from django.db import models

class FoodQA(models.Model):
    question = models.TextField()
    response = models.TextField()
