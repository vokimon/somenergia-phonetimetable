#!/usr/bin/env python

import requests
import datetime
from pathlib import Path
from consolemsg import step, out, warn, fail, u
from yamlns import namespace as ns
from .persons import persons
from .config import secrets

# Dirty Hack: Behave like python3 open regarding unicode
def open(*args, **kwd):
    import io
    return io.open(encoding='utf8', *args, **kwd)

def transliterate(word):
    word=u(word).lower().strip()
    for old, new in zip(
        u'àèìòùáéíóúçñ',
        u'aeiouaeioucn',
    ) :
        word = word.replace(old,new)
    return word

def addDays(date, ndays):
    return date + datetime.timedelta(days=ndays)


def downloadVacations(config):
    step("Baixant vacances de l'odoo...")

    import erppeek
    erp = erppeek.Client(**secrets('tomatic.holidaysodoo'))
    firstDay = addDays(config.monday, 0)
    lastDay = addDays(config.monday, 4)
    absences = erp.model('hr.leave').get_leaves(
        firstDay.strftime("%Y-%m-%d"), lastDay.strftime("%Y-%m-%d")
    )

    def dateFromIso(isoString):
        return datetime.datetime.strptime(
            isoString,
            '%Y-%m-%d %H:%M:%S'
        ).date()
    email2tomatic = {
        email: id
        for id, email in persons().emails.items()
    }

    step("  Guardant indisponibilitats per vacances a 'indisponibilitats-vacances.conf'...")
    weekdays = ['dl', 'dm', 'dx', 'dj', 'dv']
    days = [addDays(config.monday, i) for i in range(5)]
    ignored = set()
    with open('indisponibilitats-vacances.conf', 'w') as holidaysfile:
        for absence in absences:
            worker = absence['worker']
            name = email2tomatic.get(worker)
            if name is None:
                if worker in ignored:
                    continue
                ignored.add(worker)
                warn(
                    "Ignorant les vacances de {} que no està al Tomàtic",
                    worker,
                )
                continue

            start = dateFromIso(absence['start_time'])
            end = dateFromIso(absence['end_time'])
            for weekday, day in zip(weekdays, days):
                if start <= day <= end:
                    if config.get('verbose'):
                        out("+{} {} # absencia odoo (vacances, baixa...)", name, weekday)
                    holidaysfile.write("+{} {} # absencia odoo (vacances, baixa...)\n".format(name, weekday))


def downloadFestivities(config):
    step("Baixant festivitats de l'odoo...")
    intervals=dict(
        workweek=4, # This is what is needed just for schedulings
        year=366, # This is useful for many other uses, not yet slower
    )
    import erppeek
    erp = erppeek.Client(**secrets('tomatic.holidaysodoo'))
    firstDay = addDays(config.monday, 0)
    lastDay = addDays(config.monday, intervals['year'])
    festivities = erp.model('hr.holidays.public.line').get_festivities(
        firstDay.strftime("%Y-%m-%d"), lastDay.strftime("%Y-%m-%d")
    )
    holidaysfile = Path('holidays.conf')
    with holidaysfile.open('w', encoding='utf8') as output:
        for festivity in festivities:
            output.write('{date}\t{name}\n'.format(
                date=festivity['date'],
                name=festivity['name']
            ))
        no_service_file = Path('data')/'noservice.conf'
        if no_service_file.exists():
            no_service_days = no_service_file.read_text()
            output.write(no_service_days)

def downloadPersons(config):
    step("Baixant informació de les persones del tomatic...")
    url = config.baseUrl + '/api/persons'
    r = requests.get(url)
    r.raise_for_status()
    from yamlns import namespace as ns
    persons = ns.loads(r.content)
    persons.persons.dump(config.personsfile)


def downloadBusy(config):
    step("Baixant indisponibilitats del tomatic...")

    baseUrl = config.baseUrl + '/api/busy/download/'
    for name, filename in [
            ('weekly', 'indisponibilitats.conf'),
            ('oneshot', 'oneshot.conf'),
        ]:
        url = baseUrl + name
        step("  Baixant {} from {}", filename, url)
        r = requests.get(url)
        r.raise_for_status()
        Path(filename).write_bytes(r.content)

def downloadShiftCredit(config):
    step("Baixant crèdit de torns del tomatic...")
    pastMonday = addDays(config.monday,-7)
    url = config.baseUrl + '/api/shifts/download/credit/{}'.format(pastMonday)
    filename='shiftcredit.yaml'
    step("  Baixant {} from {}", filename, url)
    r = requests.get(url)
    r.raise_for_status()
    Path(filename).write_bytes(r.content)

def downloadCallCategories(config):
    from .call_registry.dummy import CallRegistry as DummyRegistry
    from .call_registry.odoo import CallRegistry as OdooRegistry
    categories = OdooRegistry().categories()
    DummyRegistry().save_categories(categories)




# vim: et ts=4 sw=4
