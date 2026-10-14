import json

from django import forms

MAX_BACKUP_BYTES = 5 * 1024 * 1024


class BackupImportForm(forms.Form):
    file = forms.FileField(label='Backup file (.json)')

    def clean(self):
        cleaned = super().clean()
        upload = cleaned.get('file')
        if upload is None:
            return cleaned
        if upload.size > MAX_BACKUP_BYTES:
            self.add_error('file', 'The file is too large.')
            return cleaned
        try:
            cleaned['data'] = json.loads(upload.read().decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            self.add_error('file', 'The file is not valid JSON.')
        return cleaned
