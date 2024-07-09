from django import forms
from django.forms import inlineformset_factory
from .models import Invoice, InvoiceLineItem
from django.utils import timezone
from django.contrib.auth.models import User

class InvoiceLineItemForm(forms.ModelForm):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = InvoiceLineItem
        fields = ['id', 'description', 'quantity', 'rate']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs.update({'class': 'form-control'})
        self.fields['quantity'].widget.attrs.update({'class': 'form-control'})
        self.fields['rate'].widget.attrs.update({'class': 'form-control'})

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.amount = instance.quantity * instance.rate
        if commit:
            instance.save()
        return instance

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['client', 'due_date', 'notes', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = User.objects.filter(profile__user_type='client')
        self.fields['client'].widget.attrs.update({'class': 'form-control'})
        self.fields['due_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['notes'].widget.attrs.update({'class': 'form-control small-textarea'})
        self.fields['status'].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        cleaned_data = super().clean()
        due_date = cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise forms.ValidationError("Due date cannot be in the past.")
        return cleaned_data

InvoiceLineItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceLineItem,
    form=InvoiceLineItemForm,
    extra=1,
    can_delete=True
)

