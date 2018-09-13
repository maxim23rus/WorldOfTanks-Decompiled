# Embedded file name: scripts/client/gui/Scaleform/daapi/view/lobby/fortifications/FortIntelligenceWindow.py
import BigWorld
from gui.shared.event_bus import EVENT_BUS_SCOPE
from gui.shared.events import FortEvent
from helpers import i18n
from constants import FORT_SCOUTING_DATA_FILTER
from gui.Scaleform.Waiting import Waiting
from gui.Scaleform.daapi.view.lobby.fortifications.components import sorties_dps
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils.FortViewHelper import FortViewHelper
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils.fort_formatters import getTextLevel
from gui.Scaleform.framework.entities.View import View
from gui.Scaleform.daapi.view.meta.FortIntelligenceWindowMeta import FortIntelligenceWindowMeta
from gui.Scaleform.framework import AppRef
from gui.Scaleform.framework.entities.abstract.AbstractWindowView import AbstractWindowView
from gui.Scaleform.genConsts.FORTIFICATION_ALIASES import FORTIFICATION_ALIASES
from gui.Scaleform.locale.FORTIFICATIONS import FORTIFICATIONS

class FortIntelligenceWindow(AbstractWindowView, View, FortIntelligenceWindowMeta, FortViewHelper, AppRef):

    def __init__(self):
        super(FortIntelligenceWindow, self).__init__()
        self._searchDP = None
        self.__cooldownCB = None
        return

    def onWindowClose(self):
        self.destroy()

    def requestClanFortInfo(self, index):
        vo = self._searchDP.getVO(index)
        if vo is not None:
            cache = self.fortCtrl.getPublicInfoCache()
            if cache is not None and not cache.isRequestInProcess:
                if not cache.setSelectedID(vo['clanID']):
                    self._searchDP.setSelectedID(None)
                    cache.clearSelectedID()
                else:
                    Waiting.show('fort/card/get')
                    self._searchDP.setSelectedID(vo['clanID'])
        return

    def onFortPublicInfoReceived(self, hasResults):
        cache = self.fortCtrl.getPublicInfoCache()
        if cache is not None:
            self.as_selectByIndexS(-1)
            self._searchDP.setSelectedID(None)
            cache.clearSelectedID()
            self._searchDP.rebuildList(cache)
            self.__setStatus(hasResults)
        return

    def onFortPublicInfoValidationError(self, reason):
        cache = self.fortCtrl.getPublicInfoCache()
        if cache is not None:
            self.as_selectByIndexS(-1)
            self._searchDP.setSelectedID(None)
            cache.clearSelectedID()
            cache.clear()
            self._searchDP.rebuildList(cache)
        self.as_setStatusTextS(i18n.makeString('#menu:validation/%s' % reason))
        return

    def onEnemyClanCardReceived(self, card):
        Waiting.hide('fort/card/get')
        self._searchDP.refresh()

    def onFavoritesChanged(self, clanDBID):
        cache = self.fortCtrl.getPublicInfoCache()
        if cache is not None:
            self._searchDP.rebuildList(cache)
            self.__setStatus(not self._searchDP.isEmpty())
        return

    def getLevelColumnIcons(self):
        minLevelIcon = getTextLevel(FORTIFICATION_ALIASES.CLAN_FILTER_MIN_LEVEL)
        maxLevelIcon = getTextLevel(FORTIFICATION_ALIASES.CLAN_FILTER_MAX_LEVEL)
        return '%s - %s' % (minLevelIcon, maxLevelIcon)

    def getFilters(self):
        return self.components.get(FORTIFICATION_ALIASES.FORT_INTEL_FILTER_ALIAS)

    def _populate(self):
        super(FortIntelligenceWindow, self)._populate()
        self.startFortListening()
        self._searchDP = sorties_dps.IntelligenceDataProvider()
        self._searchDP.setFlashObject(self.as_getSearchDPS())
        cache = self.fortCtrl.getPublicInfoCache()
        if cache is not None:
            rqIsInCooldown, _ = cache.getRequestCacheCooldownInfo()
            if rqIsInCooldown:
                self._searchDP.setSelectedID(None)
                self._searchDP.rebuildList(cache)
        self.__setStatus(not self._searchDP.isEmpty())
        self.addListener(FortEvent.ON_TOGGLE_BOOKMARK, self.__onToggleBookMark, EVENT_BUS_SCOPE.FORT)
        self.addListener(FortEvent.ON_INTEL_FILTER_DO_REQUEST, self.__onDoInfoCacheRequest, EVENT_BUS_SCOPE.FORT)
        return

    def _dispose(self):
        self.removeListener(FortEvent.ON_INTEL_FILTER_DO_REQUEST, self.__onDoInfoCacheRequest, EVENT_BUS_SCOPE.FORT)
        self.removeListener(FortEvent.ON_TOGGLE_BOOKMARK, self.__onToggleBookMark, EVENT_BUS_SCOPE.FORT)
        self.__clearCooldownCB()
        if self._searchDP is not None:
            self._searchDP.fini()
            self._searchDP = None
        self.stopFortListening()
        super(FortIntelligenceWindow, self)._dispose()
        return

    def _onRegisterFlashComponent(self, viewPy, alias):
        super(FortIntelligenceWindow, self)._onRegisterFlashComponent(viewPy, alias)
        if alias == FORTIFICATION_ALIASES.FORT_INTEL_FILTER_ALIAS:
            self.__updateCooldowns()

    def __onToggleBookMark(self, event):
        selectedIdx = self._searchDP.getSelectedIdx()
        self._searchDP.sortedCollection[selectedIdx]['isFavorite'] = event.ctx['isAdd']
        self._searchDP.refresh()

    def __onDoInfoCacheRequest(self, event):
        self.__updateCooldowns()

    def __updateCooldowns(self):
        cache = self.fortCtrl.getPublicInfoCache()
        if cache:
            isInProcess, timeLeft = cache.getRequestCacheCooldownInfo()
            self.__setCooldownComponents(isInProcess)
            self.__loadCooldownUnlockTimer(timeLeft)

    def __cooldownUnlockHandler(self):
        self.__clearCooldownCB()
        self.__setCooldownComponents(False)

    def __loadCooldownUnlockTimer(self, timeLeft):
        self.__clearCooldownCB()
        self.__cooldownCB = BigWorld.callback(max(timeLeft, 0), self.__cooldownUnlockHandler)

    def __clearCooldownCB(self):
        if self.__cooldownCB is not None:
            BigWorld.cancelCallback(self.__cooldownCB)
            self.__cooldownCB = None
        return

    def __setCooldownComponents(self, isInProcess):
        filters = self.getFilters()
        if filters:
            filters.as_setupCooldownS(isInProcess)

    def __setStatus(self, hasResults):
        cache = self.fortCtrl.getPublicInfoCache()
        if cache is not None and not hasResults:
            status = FORTIFICATIONS.FORTINTELLIGENCE_STATUS_EMPTY
            if cache:
                if cache.getFilterType() == FORT_SCOUTING_DATA_FILTER.RECENT:
                    status = FORTIFICATIONS.FORTINTELLIGENCE_STATUS_EMPTYRECENT
                elif cache.getFilterType() == FORT_SCOUTING_DATA_FILTER.ELECT:
                    status = FORTIFICATIONS.FORTINTELLIGENCE_STATUS_EMPTYFAVORITE
                elif cache.getFilterType() == FORT_SCOUTING_DATA_FILTER.FILTER:
                    status = FORTIFICATIONS.FORTINTELLIGENCE_STATUS_EMPTYABBREV
            self.as_setStatusTextS(status)
        return