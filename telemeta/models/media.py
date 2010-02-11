# -*- coding: utf-8 -*-
# Copyright (C) 2007-2010 Samalyse SARL

# This software is a computer program whose purpose is to backup, analyse,
# transcode and stream any audio content with its metadata over a web frontend.

# This software is governed by the CeCILL  license under French law and
# abiding by the rules of distribution of free software.  You can  use,
# modify and/ or redistribute the software under the terms of the CeCILL
# license as circulated by CEA, CNRS and INRIA at the following URL
# "http://www.cecill.info".

# As a counterpart to the access to the source code and  rights to copy,
# modify and redistribute granted by the license, users are provided only
# with a limited warranty  and the software's author,  the holder of the
# economic rights,  and the successive licensors  have only  limited
# liability.

# In this respect, the user's attention is drawn to the risks associated
# with loading,  using,  modifying and/or developing or reproducing the
# software by the user in light of its specific status of free software,
# that may mean  that it is complicated to manipulate,  and  that  also
# therefore means  that it is reserved for developers  and  experienced
# professionals having in-depth computer knowledge. Users are therefore
# encouraged to load and test the software's suitability as regards their
# requirements in conditions enabling the security of their systems and/or
# data to be ensured and,  more generally, to use and operate it in the
# same conditions as regards security.

# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL license and that you accept its terms.
#
# Authors: Olivier Guilyardi <olivier@samalyse.com>
#          David LIPSZYC <davidlipszyc@gmail.com>

from django.utils.translation import ugettext_lazy as _
from telemeta.models.core import *
from telemeta.models.enum import ContextKeyword
from telemeta.util.unaccent import unaccent_icmp
import re
from telemeta.models.location import LocationRelation, Location
from telemeta.models.system import Revision
from telemeta.models import query

class MediaResource(ModelCore):
    "Base class of all media objects"

    def public_access_label(self):
        if self.public_access == 'metadata':
            return _('Metadata only')
        elif self.public_access == 'full':
            return _('Sound and metadata')

        return _('Private data')
    public_access_label.verbose_name = _('public access')

    def save_with_revision(self, user, force_insert=False, force_update=False):
        "Save a media object and add a revision"
        self.save(force_insert, force_update)
        Revision.touch(self, user)    

    def get_revision(self):
        return Revision.objects.filter(element_type=self.element_type, element_id=self.id).order_by('-time')[0]

    class Meta:
        abstract = True

class MediaCollection(MediaResource):
    "Describe a collection of items"
    element_type = 'collection'
    PUBLIC_ACCESS_CHOICES = (('none', 'none'), ('metadata', 'metadata'), ('full', 'full'))

    published_code_regex   = 'CNRSMH_E_[0-9]{4}(?:_[0-9]{3}){2}'
    unpublished_code_regex = 'CNRSMH_I_[0-9]{4}_[0-9]{3}'
    code_regex             = '(?:%s|%s)' % (published_code_regex, unpublished_code_regex)

    reference             = CharField(_('reference'), unique=True, null=True)
    physical_format       = WeakForeignKey('PhysicalFormat', related_name="collections", 
                                           verbose_name=_('archive format'))
    old_code              = CharField(_('old code'), unique=True, null=True)
    code                  = CharField(_('code'), unique=True, required=True)
    title                 = CharField(_('title'), required=True)
    alt_title             = CharField(_('original title / translation'))
    physical_items_num    = IntegerField(_('number of components (medium / piece)'))
    publishing_status     = WeakForeignKey('PublishingStatus', related_name="collections", 
                                           verbose_name=_('secondary edition'))
    creator               = CharField(_('depositor / contributor'))
    booklet_author        = CharField(_('author of published notice'))
    booklet_description   = TextField(_('related documentation'))
    collector             = CharField(_('recordist'))
    collector_is_creator  = BooleanField(_('recordist identical to depositor'))
    publisher             = WeakForeignKey('Publisher', related_name="collections", 
                                           verbose_name=_('publisher / status'))     
    is_published          = BooleanField(_('published'))
    year_published        = IntegerField(_('year published'))
    publisher_collection  = WeakForeignKey('PublisherCollection', related_name="collections", 
                                            verbose_name=_('publisher collection'))
    publisher_serial      = CharField(_('publisher serial number'))
    external_references   = TextField(_('bibliographic references'))
    acquisition_mode      = WeakForeignKey('AcquisitionMode', related_name="collections", 
                                            verbose_name=_('mode of acquisition'))
    comment               = TextField(_('comment'))
    metadata_author       = WeakForeignKey('MetadataAuthor', related_name="collections", 
                                           verbose_name=_('record author'))
    metadata_writer       = WeakForeignKey('MetadataWriter', related_name="collections", 
                                           verbose_name=_('record writer'))
    legal_rights          = WeakForeignKey('LegalRight', related_name="collections", 
                                           verbose_name=_('legal rights'))
    alt_ids               = CharField(_('copies'))
    recorded_from_year    = IntegerField(_('recording year (from)'))
    recorded_to_year      = IntegerField(_('recording year (until)'))
    recording_context     = WeakForeignKey('RecordingContext', related_name="collections", 
                                           verbose_name=_('recording context'))
    approx_duration       = DurationField(_('approximative duration'))
    doctype_code          = IntegerField(_('document type'))
    travail               = CharField(_('archiver notes'))
    state                 = TextField(_('status'))
    cnrs_contributor      = CharField(_('CNRS depositor'))
    items_done            = CharField(_('items finished'))
    a_informer_07_03      = CharField(_('a_informer_07_03'))
    ad_conversion         = WeakForeignKey('AdConversion', related_name='collections', 
                                           verbose_name=_('A/D conversion'))
    public_access         = CharField(_('public access'), choices=PUBLIC_ACCESS_CHOICES, 
                                      max_length=16, default="metadata")

    objects               = query.MediaCollectionManager()

    def __unicode__(self):
        if self.title:
            return self.title

        return self.code

    @property
    def public_id(self):
        return self.code

    def has_mediafile(self):
        "Tell wether this collection has any media files attached to its items"
        items = self.items.all()
        for item in items:
            if item.file:
                return True
        return False

    def __name_cmp(self, obj1, obj2):
        return unaccent_icmp(obj1.name, obj2.name)

    def countries(self):
        "Return the countries of the items"
        countries = []
        for item in self.items.filter(location__isnull=False):
            for country in item.location.countries():
                if not country in countries:
                    countries.append(country)
            
        countries.sort(self.__name_cmp)                

        return countries
    countries.verbose_name = _("states / nations")

    def ethnic_groups(self):
        "Return the ethnic groups of the items"
        groups = []
        items = self.items.all()
        for item in items:
            if item.ethnic_group and not item.ethnic_group in groups:
                groups.append(item.ethnic_group)

        groups.sort(self.__name_cmp)                

        return groups
    ethnic_groups.verbose_name = _('populations / social groups')

    def computed_duration(self):
        duration = Duration()
        for item in self.items.all():
            duration += item.computed_duration()

        return duration
    computed_duration.verbose_name = _('computed duration')        

    def is_valid_code(self, code):
        "Check if the collection code is well formed"
        if self.is_published:
            regex = '^' + self.published_code_regex + '$'
        else:
            regex = '^' + self.unpublished_code_regex + '$'
           
        if re.match(regex, code):
            return True

        return False

    def save(self, force_insert=False, force_update=False):
        if not self.code:
            raise RequiredFieldError(self, self._meta.get_field('code'))
        if not self.is_valid_code(self.code):
            raise MediaInvalidCodeError("%s is not a valid code for this collection" % self.code)
        super(MediaCollection, self).save(force_insert, force_update)

    class Meta(MetaCore):
        db_table = 'media_collections'

class MediaItem(MediaResource):
    "Describe an item"
    element_type = 'item'
    PUBLIC_ACCESS_CHOICES = (('none', 'none'), ('metadata', 'metadata'), ('full', 'full'))

    published_code_regex    = MediaCollection.published_code_regex + '(?:_[0-9]{2}){1,2}'
    unpublished_code_regex  = MediaCollection.unpublished_code_regex + '_[0-9]{2,3}(?:_[0-9]{2}){0,2}'
    code_regex              = '(?:%s|%s)' % (published_code_regex, unpublished_code_regex)

    collection            = ForeignKey('MediaCollection', related_name="items", 
                                       verbose_name=_('collection'))
    track                 = CharField(_('item number'))
    old_code              = CharField(_('old code'), unique=True, null=True)
    code                  = CharField(_('code'), unique=True, null=True)
    approx_duration       = DurationField(_('approximative duration'))
    recorded_from_date    = DateField(_('recording date (from)'))
    recorded_to_date      = DateField(_('recording date (until)'))
    location              = WeakForeignKey('Location', verbose_name=_('location'))
    location_comment      = CharField(_('location details'))
    ethnic_group          = WeakForeignKey('EthnicGroup', related_name="items", 
                                           verbose_name=_('population / social group'))
    title                 = CharField(_('title'))
    alt_title             = CharField(_('original title / translation'))
    author                = CharField(_('author'))
    vernacular_style      = WeakForeignKey('VernacularStyle', related_name="items", 
                                           verbose_name=_('vernacular name'))
    context_comment       = TextField(_('comments'))
    external_references   = TextField(_('published reference'))
    moda_execut           = CharField(_('moda_execut'))
    copied_from_item      = WeakForeignKey('self', related_name="copies", verbose_name=_('copy of'))
    collector             = CharField(_('recordist'))
    collector_from_collection = BooleanField(_('recordist as in collection'))
    cultural_area         = CharField(_('cultural area'))
    generic_style         = WeakForeignKey('GenericStyle', related_name="items", 
                                           verbose_name=_('generic name'))
    collector_selection   = CharField(_('recordist selection'))
    creator_reference     = CharField(_('reference'))
    comment               = TextField(_('comment'))
    file                  = FileField(_('file'), upload_to='items/%Y/%m/%d', db_column="filename")
    public_access         = CharField(_('public access'), choices=PUBLIC_ACCESS_CHOICES, max_length=16, default="metadata")

    objects               = query.MediaItemManager()

    def keywords(self):
        return ContextKeyword.objects.filter(item_relations__item = self)
    keywords.verbose_name = _('keywords')

    @property
    def public_id(self):
        if self.code:
            return self.code
        return self.id

    class Meta(MetaCore):
        db_table = 'media_items'

    def is_valid_code(self, code):
        "Check if the item code is well formed"
        if not re.match('^' + self.collection.code, self.code):
            return False

        if self.collection.is_published:
            regex = '^' + self.published_code_regex + '$'
        else:
            regex = '^' + self.unpublished_code_regex + '$'

        if re.match(regex, code):
            return True

        return False

    def save(self, force_insert=False, force_update=False):
        if self.code and not self.is_valid_code(self.code):
            raise MediaInvalidCodeError("%s is not a valid item code for collection %s" 
                                        % (self.code, self.collection.code))
        super(MediaItem, self).save(force_insert, force_update)

    def computed_duration(self):
        "Tell the length in seconds of this item media data"
        # FIXME: use TimeSide?
        seconds = 0
        if self.file:
            import wave
            media = wave.open(self.file.path, "rb")
            seconds = media.getnframes() / media.getframerate()
            media.close()

        return Duration(seconds=seconds)

    computed_duration.verbose_name = _('computed duration')        

    def __unicode__(self):
        if self.title and not re.match('^ *N *$', self.title):
            title = self.title
        else:
            title = unicode(self.collection)

        if self.track:
            title += ' ' + self.track

        return title

class MediaItemKeyword(ModelCore):
    "Item keyword"
    item    = ForeignKey('MediaItem', verbose_name=_('item'), related_name="keyword_relations")
    keyword = ForeignKey('ContextKeyword', verbose_name=_('keyword'), related_name="item_relations")

    class Meta(MetaCore):
        db_table = 'media_item_keywords'
        unique_together = (('item', 'keyword'),)

class MediaItemPerformance(ModelCore):
    "Item performance"
    media_item      = ForeignKey('MediaItem', related_name="performances", 
                                 verbose_name=_('item'))
    instrument      = WeakForeignKey('Instrument', related_name="performances", 
                                     verbose_name=_('scientific instrument'))
    alias           = WeakForeignKey('InstrumentAlias', related_name="performances", 
                                     verbose_name=_('vernacular instrument'))
    instruments_num = CharField(_('number'))
    musicians       = CharField(_('interprets'))

    class Meta(MetaCore):
        db_table = 'media_item_performances'

class MediaPart(MediaResource):
    "Describe an item part"
    element_type = 'part'
    item  = ForeignKey('MediaItem', related_name="parts", verbose_name=_('item'))
    title = CharField(_('title'), required=True)
    start = FloatField(_('start'), required=True)
    end   = FloatField(_('end'), required=True)
    
    class Meta(MetaCore):
        db_table = 'media_parts'

    def __unicode__(self):
        return self.title

class Playlist(ModelCore):
    "Item or collection playlist"
    owner_username = ForeignKey('User', related_name="playlists", db_column="owner_username") 
    name           = CharField(_('name'), required=True)

    class Meta(MetaCore):
        db_table = 'playlists'

    def __unicode__(self):
        return self.name

class PlaylistResource(ModelCore):
    "Playlist components"
    RESOURCE_TYPE_CHOICES = (('item', 'item'), ('collection', 'collection'))

    playlist              = ForeignKey('Playlist', related_name="resources", verbose_name=_('playlist'))
    resource_type         = CharField(_('resource type'), choices=RESOURCE_TYPE_CHOICES, required=True)
    resource              = IntegerField(_('resource'), required=True)

    class Meta(MetaCore):
        db_table = 'playlist_resources'

class MediaInvalidCodeError(Exception):
    pass
