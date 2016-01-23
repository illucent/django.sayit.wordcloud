# -*- coding: utf-8 -*-

import hashlib
import urlparse
import re
import calendar
import json
import requests
import datetime

from string import maketrans
from collections import defaultdict
from heapq import nlargest
from operator import itemgetter

from django import template
from django.core.urlresolvers import reverse, reverse_lazy
from django.utils.http import int_to_base36
from django.utils.html import strip_tags
from django.views.generic.edit import CreateView, FormView
from django.views.generic import ListView, DetailView
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.template import Context, loader
from django.db.models import Count
from json import dumps
from django.http.response import HttpResponse

from allauth.account.adapter import get_adapter
from allauth.account.views import PasswordResetFromKeyView
from allauth.account.signals import password_reset

from speeches.models import Speech, Section, Speaker
from speeches.search import SpeakerForm

from instances.models import Instance
from instances.views import InstanceFormMixin

from haystack.forms import SearchForm
from haystack.query import RelatedSearchQuerySet
from haystack.views import SearchView
from popolo.models import Organization

from forms import ShareForm

def wordcloud(request):
    
    STOPWORDS = frozenset([
        # nltk.corpus.stopwords.words('english')
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
        'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her',
        'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs',
        'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
        'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
        'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with',
        'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after',
        'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
        'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
        'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
        'very', 's', 't', 'can', 'will', 'just', 'don', 'should', 'now',
        # @see https://github.com/rhymeswithcycle/openparliament/blob/master/parliament/text_analysis/frequencymodel.py
        "it's", "we're", "we'll", "they're", "can't", "won't", "isn't", "don't", "he's",
        "she's", "i'm", "aren't", "government", "house", "committee", "would", "speaker",
        "motion", "mr", "mrs", "ms", "member", "minister", "canada", "members", "time",
        "prime", "one", "parliament", "us", "bill", "act", "like", "canadians", "people",
        "said", "want", "could", "issue", "today", "hon", "order", "party", "canadian",
        "think", "also", "new", "get", "many", "say", "look", "country", "legislation",
        "law", "department", "two", "day", "days", "madam", "must", "that's", "okay",
        "thank", "really", "much", "there's", "yes", "no",
        # HTML tags
        'sup',
        # Nova Scotia
        "nova", "scotia", "scotians", "province", "honourable", "premier",
        # artifacts
        "\ufffd", "n't",
        # spanish
        '00', '0', 'esas', 'quiero', 'haciendo', 'otro', 'otra', 'otras', 'toda', 'toditos',
        'aquí', 'sus', 'hace', 'con', 'creo', '0000', 'dos', 'estos', 'fue', 'ahí', 'contra',
        'de', 'durante', 'en', 'hacia', 'hasta', 'mediante', 'según', 'so', 'tras', 'decir',
        'parte', 'años', 'esos', 'les', 'unos', 'este', 'ser', 'sino', 'entonces', 'hecho',
        'ustedes', 'van', 'sea', 'cada', 'debe', 'manera', 'nos', 'ellos', 'sin', 'las',
        'esto', 'pero', 'eso', 'una', 'porque', 'hay', 'esta', 'están', 'donde', 'más', 'son',
        'todos', 'ese', 'estamos', 'hoy', 'como', 'han', 'tenemos', 'hemos', 'momento', 'puede',
        'señor', 'señora', 'haciendonos', 'día', 'a', 'ante', 'bajo', 'cabe', 'no', 'No', 'el',
        'Y', 'si', 'o', 'y', 'estas', 'debido', 'ya', 'qué', 'todo', 'esa', 'desde', 'del', 'para',
        'uno', 'por', 'que', 'los', 'solo', 'dentro', 'podemos', 'algunos', 'estar', 'ahora',
        'tema', 'mismo', 'sólo', 'temas', 'tiene', 'muy', 'está', 'cuando', 'nosotros', 'doctor',
        'hacer', 'tienen', 'sobre', 'vamos', 'tres', 'así', 'ver', 'bien', 'cómo', 'entre', 'mucho',
        'otros', 'todas', '000', 'voy', 'sido', 'era', 'vez', 'unas', 'cosas', 'general', 'tanto',
        'frente', 'muchas', 'tener', 'tipo', 'mil', 'estoy', 'gran', 'san', 'tan', 'tengo', 'cual',
        'dice', 'mayor', 'allá', 'solamente', 'bueno', 'primeramente', 'pues', 'consiguiente',
        'debido', 'cuenta', 'menos',
    ])
    
    r_punctuation = re.compile(r"[^\s\w0-9'??-]", re.UNICODE)
    r_whitespace = re.compile(r'[\s?]+')

    hansard = Section.objects.filter(parent=None).order_by('-start_date').first()

    # Get the latest hansard's speeches as in DebateDetailView.
    section_ids = []
    for section in hansard._get_descendants(include_self=True):
        if section.title != 'NOTICES OF MOTION UNDER RULE 32(3)':
            section_ids.append(section.id)
    speeches = Speech.objects.filter(section__in=section_ids)

    # @see https://github.com/rhymeswithcycle/openparliament/blob/master/parliament/text_analysis/analyze.py
    # @see https://github.com/rhymeswithcycle/openparliament/blob/master/parliament/text_analysis/frequencymodel.py

    # get the counts of all non-stopwords.
    word_counts = defaultdict(int)
    total_count = 0

    for speech in speeches:
        for word in r_whitespace.split(r_punctuation.sub(' ', strip_tags(speech.text).lower())):
            if word not in STOPWORDS and len(word) > 2:
                word_counts[word] += 1
                total_count += 1
                
    topN = 29 # top N words
    word_counts = {word: count for word, count in word_counts.items()}
    most_common = nlargest(topN, word_counts.items(), key=itemgetter(1))
    most_common_words = json.dumps(most_common, ensure_ascii=False, encoding='UTF-8') # unicode handling

    return HttpResponse(most_common_words.encode(encoding='latin-1'), content_type='application/json, charset=UTF-8')

    
class InstanceCreate(CreateView):
    model = Instance
    fields = ['label', 'title', 'description']

    def is_stashed(self):
        return self.request.GET.get('post') and self.request.session.get('instance')

    def get(self, request, *args, **kwargs):
        if self.is_stashed():
            return self.post(request, *args, **kwargs)
        return super(InstanceCreate, self).get(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(InstanceCreate, self).get_form_kwargs()
        if self.is_stashed():
            kwargs['data'] = self.request.session['instance']
            del self.request.session['instance']
        return kwargs

    def form_valid(self, form):
        if self.request.user.is_authenticated():
            form.instance.created_by = self.request.user
            redirect = super(InstanceCreate, self).form_valid(form)
            self.object.users.add(self.request.user)
            return redirect
        else:
            self.request.session['instance'] = form.cleaned_data
            return redirect_to_login(
                self.request.path + '?post=1',
                login_url=reverse("account_signup"),
            )


class ShareWithCollaborators(InstanceFormMixin, FormView):
    template_name = 'share_instance_with_collaborators.html'

    form_class = ShareForm
    success_url = reverse_lazy('share_instance')

    # substantially cargo-culted from allauth.account.forms.ResetPasswordForm
    def form_valid(self, form):
        email = form.cleaned_data["email"]

        users = form.users
        if users:
            context = {
                "instance": self.request.instance,
                "inviter": self.request.user,
                "invitee": users[0],
                }
            get_adapter().send_mail('instance_invite_existing',
                                    email,
                                    context)
            user_ids = [x.id for x in users]

        else:
            # Create a new user with email address as username
            # or a bit of a hash of the email address if it's longer
            # than Django's 30 character username limit.
            if len(email) > 30:
                username = hashlib.md5(email).hexdigest()[:10]
            else:
                username = email

            # Let's try creating a new user and sending an email to them
            # with a link to the password reset page.
            # FIXME - should probably try/catch the very unlikely situation
            # where we have a duplicate username, I guess.
            user = User.objects.create_user(username, email=email)
            user_ids = (user.id,)

            temp_key = default_token_generator.make_token(user)

            instance_url = self.request.instance.get_absolute_url()

            # send the password reset email
            path = reverse("instance_accept_invite",
                           kwargs=dict(uidb36=int_to_base36(user.id),
                                       key=temp_key))
            url = urlparse.urljoin(instance_url, path)
            context = {
                "instance": self.request.instance,
                "inviter": self.request.user,
                "invitee": user,
                "password_reset_url": url,
                }
            get_adapter().send_mail('accept_invite',
                                    email,
                                    context)

        self.request.instance.users.add(*user_ids)

        messages.add_message(
            self.request,
            messages.SUCCESS,
            'Your invitation has been sent.',
            )
        return super(ShareWithCollaborators, self).form_valid(form)


class AcceptInvite(PasswordResetFromKeyView):
    template_name = 'accept_invitation.html'
    success_message_template = 'messages/accept_invite_success.txt'

    def get_success_url(self):
        return reverse('speeches:home')

    def form_valid(self, form):
        form.save()
        get_adapter().add_message(self.request,
                                  messages.SUCCESS,
                                  self.success_message_template)
        password_reset.send(sender=self.reset_user.__class__,
                            request=self.request,
                            user=self.reset_user)
        get_adapter().login(self.request, self.reset_user)

        return super(PasswordResetFromKeyView, self).form_valid(form)
