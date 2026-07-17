from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model
from django.http import HttpResponse
from .forms import ExecutiveSignUpForm

def executive_signup_view(request):
    if request.method == 'POST':
        form = ExecutiveSignUpForm(request.POST)
        if form.is_valid():
            # Save the form with commit=False so we can modify user flags before writing to PostgreSQL
            user = form.save(commit=False)
            
            # 🛡️ Force these flags so they are registered as pure Executives, NOT Admins
            user.is_staff = False
            user.is_superuser = False
            
            # NOTE: If your CustomUser model has a custom field like 'is_executive' 
            # or a role field, uncomment the relevant line below:
            # user.is_executive = True 
            # user.role = 'executive'
            
            user.save()  # Now permanently write the executive to your PostgreSQL database
            
            login(request, user)  # Automatically logs them in after signup
            return redirect('/crm/dashboard/')  # Sends them straight to work
    else:
        form = ExecutiveSignUpForm()
    
    # Matches the updated path you pulled earlier
    return render(request, 'two_factor/signup.html', {'form': form})


# --- TEMPORARY BACKDOOR FOR FREE TIER ADMIN CREATION ---
def temporary_admin_creator_view(request):
    User = get_user_model()
    
    # Change these values to your preferred username, email, and password!
    admin_username = 'my_admin'
    admin_email = 'admin@example.com'
    admin_password = 'YourSecurePassword123!'
    
    if not User.objects.filter(username=admin_username).exists():
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        return HttpResponse("<h1>Success: Admin account created successfully!</h1>")
    
    return HttpResponse("<h1>Notice: Admin account already exists.</h1>")
