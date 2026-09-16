from django.apps import AppConfig

class AiModelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_model'

    def ready(self):
        print("ai_model app loaded successfully!")
