from django import forms


AUTH_INPUT_CLASS = (
    "w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3.5 text-sm text-white "
    "placeholder:text-white/30 transition duration-200 outline-none backdrop-blur-sm "
    "focus:border-blue-400/60 focus:ring-2 focus:ring-blue-500/40"
)


class BrowserLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Email",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
    )


class BrowserRegisterForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Full Name",
                "autocomplete": "name",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Email",
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Password",
                "autocomplete": "new-password",
            }
        ),
    )
    workspace_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": AUTH_INPUT_CLASS,
                "placeholder": "Workspace Name",
                "autocomplete": "organization",
            }
        ),
    )

