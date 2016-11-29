from django import forms


class BaseForm(forms.Form):
    """
    Base class for forms which adds custom 'required' attribute to HTML form fields.
    """
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
        for bound_field in self:
            # https://www.w3.org/WAI/tutorials/forms/validation/#validating-required-input
            if hasattr(bound_field, 'field') and bound_field.field.required:
                bound_field.label = '{label} (required)'.format(label=bound_field.label)
                bound_field.field.widget.attrs['required'] = 'required'
                bound_field.field.widget.attrs['aria-required'] = 'true'
