from django.forms import inlineformset_factory
from django.forms import formset_factory
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from .forms import InvoiceForm, InvoiceLineItemForm
from .models import Invoice, InvoiceLineItem
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from .invoice_pdf import generate_invoice_pdf
from django.contrib.auth.decorators import user_passes_test

@user_passes_test(lambda u: u.is_staff)
def invoice_index(request):
    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST)
        line_item_formset = InvoiceLineItemFormSet(request.POST, instance=None, prefix='line_items')

        if invoice_form.is_valid() and line_item_formset.is_valid():
            with transaction.atomic():
                invoice = invoice_form.save()

                line_items = line_item_formset.save(commit=False)
                for line_item in line_items:
                    line_item.invoice = invoice
                    line_item.save()

                # Calculate the total amount
                total_amount = sum(item.amount for item in invoice.line_items.all())
                invoice.total_amount = total_amount
                invoice.save()

                return redirect('invoicemgmt:invoice_list')
    else:
        invoice_form = InvoiceForm()
        line_item_formset = InvoiceLineItemFormSet(instance=None, prefix='line_items')

    context = {
        'invoice_form': invoice_form,
        'line_item_formset': line_item_formset
    }
    return render(request, 'invoice.html', context)

@user_passes_test(lambda u: u.is_staff)
def invoice_list(request):
    search_query = request.GET.get('search', '')
    if search_query:
        invoices = Invoice.objects.filter(
            invoice_number__icontains=search_query
        ) | Invoice.objects.filter(
            client__username__icontains=search_query
        )
    else:
        invoices = Invoice.objects.all()

     # Get the 6 most recent invoices
    recent_invoices = Invoice.objects.order_by('-created_at')[:6]

    context = {
        'invoices': invoices,
        'search_query': search_query,
        'recent_invoices': recent_invoices,
    }
    return render(request, 'list.html', context)

InvoiceLineItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceLineItem,
    form=InvoiceLineItemForm,
    extra=1,
    fields=['id', 'description', 'quantity', 'rate']
)

@user_passes_test(lambda u: u.is_staff)
def edit_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)

    if request.method == 'POST':
        invoice_form = InvoiceForm(request.POST, instance=invoice)
        line_item_formset = InvoiceLineItemFormSet(request.POST, instance=invoice, prefix='line_items')

        if invoice_form.is_valid() and line_item_formset.is_valid():
            with transaction.atomic():
                invoice_form.save()

                # Save line items
                line_items = line_item_formset.save(commit=False)
                for line_item in line_items:
                    line_item.invoice = invoice
                    line_item.save()

            # Update the total amount
            invoice.total_amount = invoice.get_total_amount()
            invoice.save()

            # Return success response as JSON
            return JsonResponse({'success': True})

        else:
            # Combine form and formset errors
            errors = {}
            errors.update(invoice_form.errors)
            formset_errors = line_item_formset.errors
            formset_error_dict = {f'line_items-{idx}-{key}': val for idx, form_errors in enumerate(formset_errors) for key, val in form_errors.items()}
            errors.update(formset_error_dict)
            return JsonResponse({'success': False, 'errors': errors})

    else:
        invoice_form = InvoiceForm(instance=invoice)
        line_item_formset = InvoiceLineItemFormSet(instance=invoice, prefix='line_items')

    context = {
        'invoice': invoice,
        'invoice_form': invoice_form,
        'line_item_formset': line_item_formset
    }
    return render(request, 'edit_invoice.html', context)

@user_passes_test(lambda u: u.is_staff)
def delete_invoice(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)

    if request.method == 'POST':
        invoice.delete()
        messages.success(request, f'Invoice #{invoice.invoice_number} has been deleted.')
        return redirect('invoicemgmt:invoice_list')

    return render(request, 'delete_invoice.html', {'invoice': invoice})

@user_passes_test(lambda u: u.is_staff)
def generate_invoice_pdf_view(request, invoice_id):
    invoice = get_object_or_404(Invoice, pk=invoice_id)
    pdf = generate_invoice_pdf(invoice)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    response.write(pdf)

    return response