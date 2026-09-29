#inventory/catalalogue/forms.py
from django import forms
from django.core.exceptions import ValidationError

from .models import Category

class CategoryForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter category name (e.g. Electronics, Medicines, Groceries)',
        }),
        label='Category Name'
    )
    class Meta:
        model = Category
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError('Category name is required.')
        name = name.strip()
        if len(name) < 2:
            raise ValidationError('Category name must be at least 2 characters long.')
        return name
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # You can add extra logic here later (slug generation, etc.)
        if commit:
            instance.save()
        return instance