from django import forms
from django.forms import inlineformset_factory

from apps.operations.models import (
    Customer,
    Product,
    PurchaseOrder,
    PurchaseOrderLine,
    QualityInspection,
    SalesOrder,
    SalesOrderLine,
    Supplier,
)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "email", "phone", "lead_time_days", "payment_terms", "status", "notes"]


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "company", "email", "phone", "billing_address", "shipping_address"]


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "sku",
            "name",
            "category",
            "unit",
            "description",
            "reorder_level",
            "cost_price",
            "unit_price",
            "is_quality_control_required",
        ]


class PurchaseOrderForm(forms.ModelForm):
    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace is not None:
            self.fields["supplier"].queryset = Supplier.objects.filter(workspace=workspace, is_active=True)

    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "expected_on", "notes"]
        widgets = {"expected_on": forms.DateInput(attrs={"type": "date"})}


class PurchaseOrderLineForm(forms.ModelForm):
    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace is not None:
            self.fields["product"].queryset = Product.objects.filter(workspace=workspace, is_active=True)

    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "quantity_ordered", "unit_cost"]


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=2,
    can_delete=False,  # Deletion handled via is_deleted flag, not formset DELETE
    min_num=1,
    validate_min=True,
)


class QualityDecisionForm(forms.Form):
    accepted_quantity = forms.IntegerField(min_value=0)
    rejected_quantity = forms.IntegerField(min_value=0)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, inspection: QualityInspection, **kwargs):
        self.inspection = inspection
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        accepted_quantity = cleaned_data.get("accepted_quantity", 0)
        rejected_quantity = cleaned_data.get("rejected_quantity", 0)
        expected_total = self.inspection.inventory_lot.quantity_received
        if accepted_quantity + rejected_quantity != expected_total:
            raise forms.ValidationError(
                f"The accepted and rejected quantities must add up to {expected_total}."
            )
        return cleaned_data


class SalesOrderForm(forms.ModelForm):
    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace is not None:
            self.fields["customer"].queryset = Customer.objects.filter(workspace=workspace, is_active=True)

    class Meta:
        model = SalesOrder
        fields = ["customer", "promised_on", "notes"]
        widgets = {"promised_on": forms.DateInput(attrs={"type": "date"})}


class SalesOrderLineForm(forms.ModelForm):
    def __init__(self, *args, workspace=None, **kwargs):
        super().__init__(*args, **kwargs)
        if workspace is not None:
            self.fields["product"].queryset = Product.objects.filter(workspace=workspace, is_active=True)

    class Meta:
        model = SalesOrderLine
        fields = ["product", "quantity_ordered", "unit_price"]


SalesOrderLineFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderLine,
    form=SalesOrderLineForm,
    extra=2,
    can_delete=False,  # Deletion handled via is_deleted flag, not formset DELETE
    min_num=1,
    validate_min=True,
)


class DispatchForm(forms.Form):
    carrier = forms.CharField(max_length=120)
    tracking_number = forms.CharField(max_length=120)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
