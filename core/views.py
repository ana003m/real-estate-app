from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse

from core.forms import ContactForm
from core.models import ContactMessage, BlogPost
from properties.models import Property


def about(request):
    return render(request, "core/about.html")

def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return HttpResponse("OK")
            messages.success(request, "Your message has been sent! We'll get back to you shortly.")
            return redirect("contact")
    else:
        form = ContactForm()

    return render(request, "core/contact.html", {"form": form})


def home(request):
    approved = list(
        Property.objects.filter(status="approved")
        .prefetch_related("images")
        .order_by("-created_at")[:7]
    )
    blog_posts = BlogPost.objects.filter(is_published=True)[:3]

    context = {
        "featured_prop":    approved[0] if len(approved) > 0 else None,
        "side_properties":  approved[1:4],
        "bottom_properties": approved[4:7],
        "blog_posts":       blog_posts,
    }
    return render(request, "core/home.html", context)


def blog_list(request):
    posts = BlogPost.objects.filter(is_published=True)
    return render(request, "blog/list.html", {"posts": posts})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, is_published=True)
    return render(request, "blog/detail.html", {"post": post})