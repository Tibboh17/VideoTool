from django.shortcuts import render

# Create your views here.
def dashboard(request):
    context = 'dashboard'
    return render(request, 'dashboard/dashboard.html', dashboard)