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


# --- TEMPORARY BACKDOOR FOR FREE TIER ADMIN CREATION (NEW ID CREATION) ---
def temporary_admin_creator_view(request):
    User = get_user_model()
    
    # 🌟 NEW UNIQUE CREDENTIALS
    admin_username = 'crm_superadmin'
    admin_email = 'superadmin@example.com'
    admin_password = 'NewSecurePassword2026!' 
    
    user_query = User.objects.filter(username=admin_username)
    
    if user_query.exists():
        user = user_query.first()
        user.set_password(admin_password)
        user.is_superuser = True
        user.is_staff = True
        user.save()
        return HttpResponse("<h1>Success: Password for superadmin updated!</h1>")
    else:
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        return HttpResponse("<h1>Success: Brand new Unique Admin account created!</h1>")
