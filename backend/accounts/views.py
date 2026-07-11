from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import ExecutiveSignUpForm

def executive_signup_view(request):
    if request.method == 'POST':
        form = ExecutiveSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  # This saves their custom username and password
            login(request, user)  # Automatically logs them in after signup
            return redirect('/crm/dashboard/')  # Sends them straight to work
    else:
        form = ExecutiveSignUpForm()
    
    return render(request, 'registration/signup.html', {'form': form})