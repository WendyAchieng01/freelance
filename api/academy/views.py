from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from academy.models import Training
from .serializers import TrainingSerializer


class TrainingViewSet(viewsets.ModelViewSet):
    serializer_class = TrainingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Training.objects.filter(client=self.request.user)

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)
