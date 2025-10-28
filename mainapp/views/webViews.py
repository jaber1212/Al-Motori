from django.shortcuts import render

def terms_view(request):
    return render(request, 'terms.html')

def privacy_view(request):
    return render(request, 'privacy.html')
def home_landing(request):
    return render(request, 'landing.html')

# mainapp/simple_exports.py
