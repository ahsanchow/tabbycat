# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-07 07:45
from __future__ import unicode_literals

from django.db import migrations
from django.db import models


NAMES = {"novice": "Novice", "esl": "ESL", "efl": "EFL"}
LIMIT_PREFERENCES = {"pro": "pros_tab_limit", "novice": "novices_tab_limit", "esl": "esl_tab_limit", "efl": "efl_tab_limit"}
RELEASED_PREFERENCES = {"pro": "pros_tab_released", "novice": "novices_tab_released", "esl": "esl_tab_released", "efl": "efl_tab_released"}
TRUE_CONSTANTS = ("True", "true", "TRUE", "1", "YES", "Yes", "yes")


def create_speaker_categories(apps, schema_editor):
    """Creates the speaker categories, migrating preferences etc."""

    Speaker = apps.get_model("participants", "Speaker")
    SpeakerCategory = apps.get_model("participants", "SpeakerCategory")
    TournamentPreferenceModel = apps.get_model("options", "TournamentPreferenceModel")
    Tournament = apps.get_model("tournaments", "Tournament")

    def get_limit(tournament, field):
        try:
            limit_pref = TournamentPreferenceModel.objects.get(section="tab_release",
                    name=LIMIT_PREFERENCES[field], instance_id=tournament.id)
        except TournamentPreferenceModel.DoesNotExist:
            return 0
        try:
            return int(limit_pref.raw_value)
        except ValueError:
            return 0


    for tournament in Tournament.objects.all():

        last_seq = SpeakerCategory.objects.filter(tournament=tournament).aggregate(models.Max('seq'))['seq__max']
        if last_seq is None:
            last_seq = 0

        # Collect whether tabs were released
        released = {}
        for field, pref_name in RELEASED_PREFERENCES.items():
            try:
                released_pref = TournamentPreferenceModel.objects.get(section="tab_release",
                        name=pref_name, instance_id=tournament.id)
            except TournamentPreferenceModel.DoesNotExist:
                released[field] = False
            else:
                released[field] = released_pref.raw_value in TRUE_CONSTANTS
        any_released = any(released.values())

        # If any one of the category tabs was released, set the new preference to be True
        # (and let the `public` option on the SpeakerCategory model hide the unreleased ones).
        # If all were unreleased, set it to be False.
        TournamentPreferenceModel.objects.get_or_create(section="tab_release",
                name="speaker_category_tabs_released", instance_id=tournament.id,
                defaults={'raw_value': "True" if any_released else "False"})

        # Now, create the categories if there was at least one speaker with the flag on
        for seq, field in enumerate(["esl", "efl", "novice"], start=last_seq+1):
            if SpeakerCategory.objects.filter(tournament=tournament, slug=field).exists():
                continue
            if not Speaker.objects.filter(team__tournament=tournament, **{field: True}).exists():
                continue

            name = NAMES[field]
            limit = get_limit(tournament, field)

            # Make public if either no tab is released, or this specific one is
            public = (not any_released) or released.get(RELEASED_PREFERENCES[field], False)

            SpeakerCategory.objects.create(tournament=tournament, name=name, slug=field, seq=seq,
                    limit=limit, public=public)

        # Finally, create the pro category (for everyone; can be deleted manually if not used)
        # but only make it public if the tab is already released (i.e. assume it's not wanted)
        if not SpeakerCategory.objects.filter(tournament=tournament, slug="pro").exists():
            SpeakerCategory.objects.create(tournament=tournament, name="Pro", slug="pro", seq=last_seq+3,
                limit=get_limit(tournament, "pro"), public=released.get("pros_tab_released", False))


def convert_speaker_categories(apps, schema_editor):
    Speaker = apps.get_model("participants", "Speaker")
    SpeakerCategory = apps.get_model("participants", "SpeakerCategory")

    categories_lookup = {} # (tournament, category): SpeakerCategory object

    def get_category(speaker, slug):
        key = (speaker.team.tournament.id, slug)
        if key not in categories_lookup:
            try:
                categories_lookup[key] = SpeakerCategory.objects.get(
                    tournament_id=speaker.team.tournament.id, slug=slug)
            except SpeakerCategory.DoesNotExist:
                categories_lookup[key] = None
        return categories_lookup[key]

    for speaker in Speaker.objects.all():
        categories = []

        for field in ['novice', 'esl', 'efl']:
            if getattr(speaker, field, False):
                category = get_category(speaker, field)
                if category is not None:
                    categories.append(category)

        # Anyone who isn't a novice is a pro, if that category exists
        if not speaker.novice:
            category = get_category(speaker, "pro")
            if category is not None:
                categories.append(category)

        speaker.categories.set(categories)


class Migration(migrations.Migration):

    dependencies = [
        ('participants', '0030_auto_20170807_0726'),
        ('options', '0008_rename_position_names_to_side_names'),
    ]

    operations = [
        migrations.RunPython(create_speaker_categories, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(convert_speaker_categories, reverse_code=migrations.RunPython.noop),
    ]
