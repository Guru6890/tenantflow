# tenancy/forms.py
from django import forms
from .models import Workspace

BUSINESS_TYPE_CHOICES = [
    ('', 'Select Business Type'),
    ('gym', 'Gym / Fitness Studio'),
    ('pharmacy', 'Medical Shop / Pharmacy'),
    ('manufacturing', 'Manufacturing / Production Unit'),
    ('food', 'Food Products Manufacturing'),
    ('retail', 'Supermarket / Retail Store'),
    ('service', 'Service Based Business'),
    ('other', 'Other Business'),
]


class WorkspaceCreationForm(forms.ModelForm):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'placeholder': 'My Fitness Studio',
            'class': 'form-control'
        }),
        label="Workspace Name"
    )

    business_type = forms.ChoiceField(
        choices=BUSINESS_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="What best describes your business?"
    )

    class Meta:
        model = Workspace
        fields = ['name', 'business_type']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if len(name.strip()) < 3:
            raise forms.ValidationError("Workspace name must be at least 3 characters long.")
        return name.strip()