from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class AuthTests(TestCase):
    def setUp(self):
        User.objects.create_user('admin', password='pw')

    def test_login_redirects_to_home(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'admin', 'password': 'pw'})
        self.assertRedirects(response, reverse('wireguard:home'))

    def test_login_honours_next(self):
        target = reverse('wireguard:peer-list')
        response = self.client.post(reverse('accounts:login') + '?next=' + target,
                                    {'username': 'admin', 'password': 'pw', 'next': target})
        self.assertRedirects(response, target)

    def test_bad_password_shows_error(self):
        response = self.client.post(reverse('accounts:login'), {'username': 'admin', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Please enter a correct username and password')

    def test_logout_requires_post(self):
        self.client.login(username='admin', password='pw')
        self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('accounts:login'))

    def test_root_redirects_to_home(self):
        self.assertRedirects(self.client.get('/'), reverse('wireguard:home'), target_status_code=302)
