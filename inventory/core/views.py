#inventory/core/views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect

class ServiceListView(ListView):
    """Reusable List View"""
    service = None
    template_name = ''
    context_object_name = 'objects'
    paginate_by = 20

    def get_queryset(self):
        if hasattr(self.service, 'list'):
            return self.service.list()
        return super().get_queryset()


class ServiceCreateView(CreateView):
    """Reusable Create View using Service"""
    service = None
    form_class = None
    template_name = 'generic/form.html'   # You can override per app
    success_url = None

    def form_valid(self, form):
        try:
            obj = self.service.create(**form.cleaned_data)
            messages.success(self.request, f"{obj} created successfully.")
            return redirect(self.get_success_url())
        except Exception as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy(self.success_url_name) if hasattr(self, 'success_url_name') else '/'


class ServiceUpdateView(UpdateView):
    """Reusable Update View using Service"""
    service = None
    form_class = None
    template_name = 'generic/form.html'

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        return self.service.get_by_id(pk)

    def form_valid(self, form):
        try:
            obj = self.service.update(self.object.id, **form.cleaned_data)
            messages.success(self.request, f"{obj} updated successfully.")
            return redirect(self.get_success_url())
        except Exception as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)


class ServiceDeleteView(DeleteView):
    """Reusable Delete View using Service"""
    service = None
    template_name = 'generic/confirm_delete.html'

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        return self.service.get_by_id(pk)

    def delete(self, request, *args, **kwargs):
        try:
            obj = self.get_object()
            self.service.delete(obj.id)
            messages.success(request, f"{obj} deleted successfully.")
        except Exception as e:
            messages.error(request, str(e))
        return redirect(self.get_success_url())