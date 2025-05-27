from rest_framework import serializers
from academy.models import Training
from core.models import Job

class TrainingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Training
        fields = '__all__'  

    def validate_job(self, value):
        user = self.context['request'].user
        if not Job.objects.filter(id=value.id, client=user.profile).exists():
            raise serializers.ValidationError(
                "You can only select jobs that belong to you.")
        return value
