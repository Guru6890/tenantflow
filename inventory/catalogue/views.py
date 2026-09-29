#iventory/catalogue/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from core.views import ServiceListView, ServiceCreateView, ServiceUpdateView, ServiceDeleteView
from .services import CategoryService
from catalogue.forms import CategoryForm

# Create your views here.

class CategoryListView(LoginRequiredMixin, ServiceListView):
    service = CategoryService
    template_name = 'category_list.html'
    context_object_name = 'categories'

class CategoryCreateView(LoginRequiredMixin, ServiceCreateView):
    service = CategoryService
    form_class = CategoryForm
    template_name = 'category_create.html'

class CategoryUpdateView(LoginRequiredMixin, ServiceUpdateView):
    service = CategoryService
    form_class = CategoryForm
    template_name = 'category_create.html'

class CategoryDeleteView(LoginRequiredMixin,ServiceDeleteView):
    service = CategoryService
    template_name = 'invenotory/confirm_delete_generic.html'