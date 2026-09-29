# tenancy/forms.py
from django import forms
from .models import Workspace

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
        choices=Workspace.BusinessTypes.choices,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="What best describes your business?"
    )

    class Meta:
        model = Workspace
        fields = ['name', 'business_type']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 3:
            raise forms.ValidationError("Workspace name must be at least 3 characters long.")
        return name