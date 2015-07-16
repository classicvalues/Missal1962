"""
Missal 1962
"""
import re
import sys
import logging
from collections import OrderedDict
from calendar import isleap
from datetime import date, timedelta
from dateutil.easter import easter

from missal1962 import blocks
from missal1962.constants import *
from missal1962.models import LiturgicalDay

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


class Missal(OrderedDict):
    """ Class representing a Missal.

    It's an ordered dict of lists where each key is a `date` object and value
    is a list containing `LiturgicalDay` objects. Example:

    {
      ...
      datetime.date(2008, 5, 3): [<var:sab_post_ascension:4>,
                                  <fix:05-03.mariae_reginae_poloniae:1>],
      datetime.date(2008, 5, 4): [<var:dom_post_ascension:4>, <fix:05-04>],
      datetime.date(2008, 5, 5): [<var:f2_hebd_post_ascension:4>, <fix:05-05>],
      datetime.date(2008, 5, 6): [<var:f3_hebd_post_ascension:4>],
      ...
    }
    """
    def __init__(self, year):
        """ Build an empty missal and fill it in with liturgical days' objects
        """
        super(Missal, self).__init__()
        self._build_empty_missal(year)
        self._fill_in_variable_days(year)
        self._fill_in_fixed_days()
        self._fill_in_semi_fixed_days(year)
        self._resolve_concurrency()

    def get_day_by_id(self, day_id):
        """ Return a day representation by liturgical day ID

        :param dayid: liturgical days'identifier, for example
                      'var:f2_septuagesima:4'
        :type dayid: string
        :return: day representation
        :rtype: list(datetime, list)
        """
        for day in self.iteritems():
            if day_id in [ii.id for ii in day[1]]:
                return day

    def _build_empty_missal(self, year):
        day = date(year, 1, 1)
        while day.year == year:
            self[day] = []
            day += timedelta(days=1)

    def _fill_in_variable_days(self, year):
        """
        Days depending on variable date, such as Easter or Advent
        """
        # main blocks
        self._insert_block(
            self._calc_varday__dom_sanctae_familiae(year),
            blocks.VARDAYS__POST_EPIPHANIA)
        self._insert_block(
            self._calc_varday__dom_septuagesima(year),
            blocks.VARDAYS__RESSURECTIONIS)
        self._insert_block(
            self._calc_varday__sab_before_dom_post_pentecost_24(year),
            blocks.VARDAYS__POST_EPIPHANIA,
            reverse=True,
            overwrite=False)
        self._insert_block(
            self._calc_varday__dom_post_pentecost_24(year),
            blocks.VARDAYS__HEBD_POST_PENTECOST_24)
        self._insert_block(
            self._calc_varday__dom_adventus(year),
            blocks.VARDAYS__ADVENT,
            stop_date=date(year, 12, 23))
        # additional blocks
        self._insert_block(
            self._calc_varday__sanctissimi_nominis_jesu(year),
            blocks.VARDAYS__SANCTISSIMI_NOMINIS_JESU
        )
        self._insert_block(
            self._calc_varday__quattour_septembris(year),
            blocks.VARDAYS__QUATTOUR_SEPTEMBRIS)
        self._insert_block(
            self._calc_varday__jesu_christi_regis(year),
            blocks.VARDAYS__JESU_CHRISTI_REGIS
        )
        if self._calc_varday__dom_octavam_nativitatis(year):
            self._insert_block(
                self._calc_varday__dom_octavam_nativitatis(year),
                blocks.VARDAYS__DOM_OCTAVAM_NATIVITATIS
            )

    def _fill_in_fixed_days(self):
        """
        Days ascribed to specific date
        """
        for date_, contents in self.iteritems():
            date_id = date_.strftime("%m_%d")
            days = list(set([LiturgicalDay(ii, date_) for ii in blocks.FIXDAYS
                             if ii.startswith("fix:{}".format(date_id))]))
            contents.extend(days)
            contents.sort(reverse=True)

    def _fill_in_semi_fixed_days(self, year):
        """
        Days normally ascribed to specific date, but in
        certain conditions moved to other dates
        """
        day = self._calc_fixday__11_02_omnium_fidelium_defunctorum(year)
        self[day].append(LiturgicalDay(FIX_11_02_OMNIUM_FIDELIUM_DEFUNCTORUM, day))
        self[day].sort(reverse=True)

        day = self._calc_fixday__02_24_matthiae_apostoli(year)
        self[day].append(LiturgicalDay(FIX_02_24_MATTHIAE_APOSTOLI, day))
        self[day].sort(reverse=True)

        day = self._calc_fixday__02_27(year)
        self[day].append(LiturgicalDay(FIX_02_27_1, day))
        self[day].sort(reverse=True)

    def _insert_block(self, start_date, block, stop_date=None, reverse=False,
                      overwrite=True):
        """ Insert a block of related `LiturgicalDay` objects.

        :param start_date: date where first or last (if `reverse`=True)
                           element of the block will be inserted
        :type start_date: date object
        :param block: list of day identifiers in established order
        :type block: list of strings
        :param stop_date: last date to insert block element
        :type stop_date: date object
        :param reverse: if False, identifiers will be put in days
                        following `start_date` otherwise they'll
                        be put in leading up days
        :param overwrite: if True, overwrite existing identifiers,
                          else quit on first non empty day

        Example:
        start_date=2008-01-13, reverse=False
        block = [
            'var:dom_sanctae_familiae:2',
            'var:f2_post_epiphania_1:4',
            'var:f3_post_epiphania_1:4',
        ]
        Result:
        {
        ...
          datetime.date(2008, 1, 13): [<var:dom_sanctae_familiae:2>],
          datetime.date(2008, 1, 14): [<var:f2_post_epiphania_1:4>, <fix:01-14_1:3>],
          datetime.date(2008, 1, 15): [<var:f3_post_epiphania_1:4', <fix:01-15_1:3>],
        ...
        }

        Example:
        start_date=2008-11-22, reverse=True
        block = [
            'var:f5_post_epiphania_6:4',
            'var:f6_post_epiphania_6:4',
            'var:sab_post_epiphania_6:4'
        ]
        Result:
        {
        ...
          datetime.date(2008, 11, 20): [<var:f5_post_epiphania_6:4>],
          datetime.date(2008, 11, 21): [<var:f6_post_epiphania_6:4>],
          datetime.date(2008, 11, 22): [<var:sab_post_epiphania_6:4>],
        ...
        }
        """
        if reverse:
            block = reversed(block)
        for ii, day_ids in enumerate(block):
            index = start_date + timedelta(days=ii if not reverse else -ii)
            # skip on empty day in a block
            if not day_ids:
                continue
            # break on first non-empty day
            if self[index] and not overwrite:
                break
            # break on stop date
            if stop_date == self[index - timedelta(days=1)]:
                break
            self[index] = [LiturgicalDay(day_id, index) for day_id in day_ids]

    def _resolve_concurrency(self):
        patterm__var_dom_adventus = re.compile('var:dom_adventus')

        for day, lit_days in self.iteritems():
            lit_days_ids = [ld.id for ld in lit_days]

            if FIX_12_08_CONCEPTIONE_IMMACULATA_BMV in lit_days_ids and day.weekday() == 6:
                new_days = []
                for pattern in (FIX_12_08_CONCEPTIONE_IMMACULATA_BMV, patterm__var_dom_adventus):
                    for lit_day in lit_days:
                        if re.match(pattern, lit_day.id):
                            new_days.append(lit_day)
                self[day] = new_days

    def _calc_varday__dom_ressurectionis(self, year):
        """ Dominica Ressurectionis - Easter Sunday """
        return easter(year)

    def _calc_varday__dom_sanctae_familiae(self, year):
        """ Dominica Sanctae Familiae Jesu Mariae Joseph

        First Sunday after Epiphany (06 January)
        """
        d = date(year, 1, 6)
        wd = d.weekday()
        delta = 6 - wd if wd < 6 else 7
        return d + timedelta(days=delta)

    def _calc_varday__dom_septuagesima(self, year):
        """ Dominica in Septuagesima

        Beginning of the pre-Lenten season
        First day of the Ressurection Sunday - related block.
        It's 63 days before Ressurection.
        """
        return self._calc_varday__dom_ressurectionis(year) - timedelta(days=63)

    def _calc_varday__dom_adventus(self, year):
        """ Dominica I Adventus

        First Sunday of Advent - November 27 if it's Sunday
        or closest Sunday
        """
        d = date(year, 11, 27)
        wd = d.weekday()
        if wd != 6:
            d += timedelta(days=6 - wd)
        return d

    def _calc_varday__dom_post_pentecost_24(self, year):
        """ Dominica XXIV Post Pentecosten

        Last Sunday before Dominica I Adventus
        This will be always dom_post_pentecost_24, which will be
        placed either
        * instead of dom_post_pentecost_23 - if number of
          dom_post_pentecost_* == 23)
        * directly after week of dom_post_pentecost_23 - if number of
          dom_post_pentecost_* == 24)
        * directly after week of dom_post_epiphania_6 (moved from post
          epiphania period) - if number of dom_post_pentecost_* > 24)
        """
        return self._calc_varday__dom_adventus(year) - timedelta(days=7)

    def _calc_varday__sab_before_dom_post_pentecost_24(self, year):
        """ Last Saturday before Dominica XXIV Post Pentecosten

        This is the end of potentially "empty" period that might appear
        between Dominica XXIII and Dominica XXIV Post Pentecosten if
        Easter is early. In such case Dominica post Epiphania * are
        moved here to "fill the gap"
        """
        return self._calc_varday__dom_post_pentecost_24(year) - timedelta(days=1)

    def _calc_varday__quattour_septembris(self, year):
        """ Feria Quarta Quattuor Temporum Septembris

        Ember Wednesday in September is a Wednesday after third Sunday
        of September according to John XXIII's motu proprio
        Rubricarum instructum of June 25 1960.
        """
        d = date(year, 9, 1)
        while d.month == 9:
            # third Sunday
            if d.weekday() == 6 and 15 <= d.day <= 21:
                break
            d += timedelta(days=1)
        # Wednesday after third Sunday
        return d + timedelta(days=3)

    def _calc_varday__sanctissimi_nominis_jesu(self, year):
        """ Sanctissimi Nominis Jesu

        The Feast of the Holy Name of Jesus. Kept on the First
        Sunday of the year; but if this Sunday falls on
        1st, 6th or 7th January, the feast is kept on 2nd January.
        """
        d = date(year, 1, 1)
        while d.day <= 7:
            wd = d.weekday()
            if d.day in (1, 6, 7) and wd == 6:
                return date(year, 1, 2)
            if wd == 6:
                return d
            d += timedelta(days=1)

    def _calc_varday__jesu_christi_regis(self, year):
        """ Jesu Christi Regis

        The Feast of Christ the King, last Sunday of October
        """
        d = date(year, 10, 31)
        while d.month == 10:
            if d.weekday() == 6:
                return d
            d -= timedelta(days=1)

    def _calc_varday__dom_octavam_nativitatis(self, year):
        """ Dominica infra octavam Nativitatis

        Sunday within the Octave of Christmas, Sunday between
        Dec 26 and Dec 31
        """
        d = date(year, 12, 27)
        while d.year == year:
            if d.weekday() == 6:
                return d
            d += timedelta(days=1)
        return None

    def _calc_fixday__11_02_omnium_fidelium_defunctorum(self, year):
        """ Commemoratione Omnium Fidelium Defunctorum

        All Souls Day; if not Sunday - Nov 2, else Nov 3
        """
        d = date(year, 11, 2)
        if d.weekday() == 6:
            return date(year, 11, 3)
        return d

    def _calc_fixday__02_24_matthiae_apostoli(self, year):
        """ Matthiae Apostoli

        saint Matthew the Apostle, normally on Feb 24
        but in leap year on Feb 25
        """
        return date(year, 2, 24) if not isleap(year) else date(year, 2, 25)

    def _calc_fixday__02_27(self, year):
        """ Feb 27

        Feb 27, normally on Feb 27
        but in leap year on Feb 28
        """
        return date(year, 2, 27) if not isleap(year) else date(year, 2, 28)


if __name__ == '__main__':
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2012
    missal = Missal(year)

    for k, v in missal.iteritems():
        if k.weekday() == 6:
            log.info("---")
        log.info("%s %s %s", k.strftime('%A'), k, v)
