# Python bytecode 2.7 (decompiled from Python 2.7)
# Embedded file name: scripts/client/gui/game_control/calendar_controller.py
import functools
import logging
from datetime import timedelta
from account_helpers.AccountSettings import AccountSettings, LAST_CALENDAR_SHOW_TIMESTAMP
from adisp import process
from gui import GUI_SETTINGS
from gui.Scaleform import MENU
from gui.Scaleform.daapi.settings.views import VIEW_ALIAS
from gui.Scaleform.framework import ViewTypes
from gui.Scaleform.framework.managers.containers import POP_UP_CRITERIA
from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
from gui.game_control import CalendarInvokeOrigin
from gui.game_control.links import URLMacros
from gui.server_events.modifiers import CalendarSplashModifier
from gui.shared import g_eventBus, events, EVENT_BUS_SCOPE
from gui.shared.event_dispatcher import showHangar
from helpers import dependency, time_utils, i18n
from helpers.time_utils import ONE_HOUR
from skeletons.gui.app_loader import IAppLoader, GuiGlobalSpaceID
from skeletons.gui.game_control import ICalendarController, IBrowserController
from skeletons.gui.game_window_controller import GameWindowController
from skeletons.gui.server_events import IEventsCache
from skeletons.gui.lobby_context import ILobbyContext
from web.web_client_api import w2capi, webApiCollection, w2c, W2CSchema
from web.web_client_api.request import RequestWebApi
from web.web_client_api.shop import ShopWebApi
from web.web_client_api.sound import SoundWebApi
from web.web_client_api.ui import CloseWindowWebApi, NotificationWebApi, ShopWebApiMixin, UtilWebApi, VehiclePreviewWebApiMixin

@w2capi(name='open_tab', key='tab_id')
class _OpenTabWebApi(ShopWebApiMixin, VehiclePreviewWebApiMixin):
    __calendarController = dependency.descriptor(ICalendarController)

    def _getVehiclePreviewReturnAlias(self, cmd):
        return VIEW_ALIAS.ADVENT_CALENDAR

    def _getVehiclePreviewReturnCallback(self, cmd):
        return functools.partial(self.__showCalendar, cmd.back_url)

    def __showCalendar(self, backUrl=None):
        self.__calendarController.showWindow(backUrl, CalendarInvokeOrigin.HANGAR)


@w2capi(name='close_window', key='window_id')
class _CloseWindowWebApi(CloseWindowWebApi):
    __calendarController = dependency.descriptor(ICalendarController)

    @w2c(W2CSchema, 'advent_calendar')
    def adventCalendar(self, *_):
        self.__calendarController.hideWindow()


_BROWSER_SIZE = (1014, 654)
_MIN_BROWSER_ID = 827709
_logger = logging.getLogger(__name__)
_browserIDGen = xrange(_MIN_BROWSER_ID, _MIN_BROWSER_ID + 10000).__iter__()
_START_OF_DAY_OFFSET = {'EU': timedelta(hours=5),
 'ASIA': timedelta(hours=6),
 'NA': timedelta(hours=11),
 'RU': timedelta(hours=6)}

def calendarEnabledActionFilter(act):
    return any((isinstance(mod, CalendarSplashModifier) for mod in act.getModifiers()))


class CalendarController(GameWindowController, ICalendarController):
    browserCtrl = dependency.descriptor(IBrowserController)
    eventsCache = dependency.descriptor(IEventsCache)
    lobbyContext = dependency.descriptor(ILobbyContext)
    appLoader = dependency.descriptor(IAppLoader)

    def __init__(self):
        super(CalendarController, self).__init__()
        self.__browserID = None
        self.__showOnSplash = False
        self.__urlMacros = URLMacros()
        return

    def onLobbyInited(self, event):
        super(CalendarController, self).onLobbyInited(event)
        self.browserCtrl.onBrowserDeleted += self.__onBrowserDeleted
        self._updateActions()
        if self.__showOnSplash and self.mustShow():
            self.showWindow(invokedFrom=CalendarInvokeOrigin.SPLASH)

    def fini(self):
        super(CalendarController, self).fini()
        self.browserCtrl.onBrowserDeleted -= self.__onBrowserDeleted

    def mustShow(self):
        result = False
        lastShowTstamp = self.__getShowTimestamp()
        if not lastShowTstamp or lastShowTstamp < 0:
            return True
        else:
            now = time_utils.getServerRegionalTime()
            if lastShowTstamp > now:
                return True
            actions = self.eventsCache.getActions(calendarEnabledActionFilter).values()
            for action in actions:
                if action.getFinishTime() < now:
                    continue
                stepDuration = None
                for modifier in action.getModifiers():
                    duration = modifier.getDuration() if modifier else None
                    if duration:
                        stepDuration = min(stepDuration, duration) if stepDuration else duration

                stepDuration = (stepDuration or GUI_SETTINGS.adventCalendar['popupIntervalInHours']) * ONE_HOUR
                offerChangedTime = now - int(now - action.getStartTime()) % stepDuration
                wasntVisibleAtAll = not lastShowTstamp or lastShowTstamp > now
                wasntVisibleCurrentOffer = not wasntVisibleAtAll and lastShowTstamp < offerChangedTime
                result = wasntVisibleAtAll or wasntVisibleCurrentOffer

            return result

    def showWindow(self, url=None, invokedFrom=None):
        self._showWindow(url, invokedFrom)

    def hideWindow(self):
        if self.__browserID is None:
            return
        else:
            app = self.appLoader.getApp()
            if app is not None and app.containerManager is not None:
                browserWindow = app.containerManager.getView(ViewTypes.WINDOW, criteria={POP_UP_CRITERIA.UNIQUE_NAME: VIEW_ALIAS.ADVENT_CALENDAR})
                if browserWindow is not None:
                    browserWindow.destroy()
                    self.__browserID = None
                else:
                    self.browserCtrl.delBrowser(self.__browserID)
            return

    def _openWindow(self, url, invokedFrom=None):
        if self.appLoader.getSpaceID() != GuiGlobalSpaceID.LOBBY:
            return
        elif self.__getBrowserView() is not None:
            return
        else:
            try:
                while self.__browserID is None:
                    browserID = next(_browserIDGen)
                    if self.browserCtrl.getBrowser(browserID) is None:
                        self.__browserID = browserID

            except StopIteration:
                _logger.error('Could not allocate a browser ID for calendar')
                return

            self.__openBrowser(self.__browserID, url, _BROWSER_SIZE, invokedFrom)
            self.__setShowTimestamp(time_utils.getServerRegionalTime())
            _logger.debug('Calendar opened in web browser (browserID=%d)', self.__browserID)
            return

    def _onSyncCompleted(self, *_):
        self._updateActions()

    def _updateActions(self):
        self.__showOnSplash = len(self.eventsCache.getActions(calendarEnabledActionFilter)) > 0

    def _getUrl(self):
        return GUI_SETTINGS.adventCalendar['baseURL']

    def __onBrowserDeleted(self, browserID):
        if browserID == self.__browserID:
            _logger.debug('Calendar web browser destroyed (browserID=%d)', browserID)
            self.__browserID = None
        return

    def __getShowTimestamp(self):
        tstampStr = AccountSettings.getSettings(LAST_CALENDAR_SHOW_TIMESTAMP)
        if tstampStr:
            try:
                return float(tstampStr)
            except (TypeError, ValueError):
                _logger.warning('Invalid calendar show timestamp')

        return None

    def __getBrowserView(self):
        app = self.appLoader.getApp()
        if app is not None and app.containerManager is not None:
            browserView = app.containerManager.getView(ViewTypes.WINDOW, criteria={POP_UP_CRITERIA.VIEW_ALIAS: VIEW_ALIAS.ADVENT_CALENDAR})
            return browserView
        else:
            return

    def __setShowTimestamp(self, tstamp):
        AccountSettings.setSettings(LAST_CALENDAR_SHOW_TIMESTAMP, str(tstamp))

    @process
    def __openBrowser(self, browserID, url, browserSize, invokedFrom):
        browserHandlers = webApiCollection(NotificationWebApi, RequestWebApi, ShopWebApi, SoundWebApi, UtilWebApi, _CloseWindowWebApi, _OpenTabWebApi)

        def showBrowserWindow():
            ctx = {'size': browserSize,
             'title': i18n.makeString(MENU.ADVENTCALENDAR_WINDOW_TITLE),
             'handlers': browserHandlers,
             'browserID': browserID,
             'alias': VIEW_ALIAS.ADVENT_CALENDAR,
             'showCloseBtn': False,
             'showWaiting': True,
             'showActionBtn': False}
            browser = self.browserCtrl.getBrowser(browserID)
            browser.useSpecialKeys = False
            if invokedFrom == CalendarInvokeOrigin.HANGAR:
                showHangar()
            g_eventBus.handleEvent(events.DirectLoadViewEvent(SFViewLoadParams(VIEW_ALIAS.ADVENT_CALENDAR), ctx=ctx), scope=EVENT_BUS_SCOPE.LOBBY)

        title = i18n.makeString(MENU.ADVENTCALENDAR_WINDOW_TITLE)
        yield self.browserCtrl.load(url=url, browserID=browserID, browserSize=browserSize, isAsync=False, useBrowserWindow=False, showBrowserCallback=showBrowserWindow, showCreateWaiting=False, title=title)
