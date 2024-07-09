from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from academy.forms import TrainingForm
from academy.models import Training
from accounts.models import Profile
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.views.generic import DeleteView


# Create your views here.
def academy_index(request):
    trainings = Training.objects.all()

    return render(request, 'academy.html', {'trainings':trainings})

def training(request, training_id):
    training = get_object_or_404(Training, pk=training_id)
    return render(request, 'training.html', {'training': training})

def is_client(user):
    if user.is_authenticated:
        client_profile = Profile.objects.filter(user=user, user_type='client')
        return client_profile.exists()
    return False

@login_required
@user_passes_test(is_client)
def client_academy(request):

    trainings = Training.objects.filter(client=request.user)
    return render(request, 'client_academy.html', {'trainings': trainings})
  
    

@login_required
@user_passes_test(is_client)
def client_trainings(request):
    trainings = Training.objects.filter(client=request.user)
    if request.method == 'POST':
        form = TrainingForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
                # Get the client's Profile instance
                client_profile = request.user.profile

                # Get the User instance from the Profile instance
                client_user = client_profile.user

                # Create or update the Training object with the correct User instance
                training = form.save(commit=False)
                training.client = client_user
                training.save()

                # Add any additional logic or success message
                return redirect('academy:client_academy')
    else:
        form = TrainingForm(user=request.user)
    context = {
        'form': form,        
        }    
    return render(request, 'client_trainings.html', context)


@login_required
@user_passes_test(is_client)
def edit_training(request, training_id):
    training = get_object_or_404(Training, id=training_id, client=request.user)

    if request.method == 'POST':
        form = TrainingForm(request.POST, request.FILES, instance=training, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('academy:client_academy')
    else:
        form = TrainingForm(instance=training, user=request.user)

    return render(request, 'edit_training.html', {'form': form, 'training': training})


class DeleteTrainingView(DeleteView):
    model = Training
    success_url = reverse_lazy('academy:client_academy')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return redirect(self.success_url)
