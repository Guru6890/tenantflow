from django.shortcuts import render
from django.contrib.auth import login

from .forms import TenantUserCreationForm

# Create your views here.

def register_view(request):
    if request.method == 'POST':
        form = TenantUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

    else:
        form = TenantUserCreationForm()

    return render(request, 'registration/register.html', {'form': form})