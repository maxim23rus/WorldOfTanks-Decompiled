# Embedded file name: scripts/client/gui/Scaleform/daapi/view/lobby/fortifications/FortClanBattleRoom.py
from adisp import process
from constants import PREBATTLE_TYPE_NAMES, PREBATTLE_TYPE, FORT_BUILDING_TYPE, FORT_BUILDING_STATUS
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils import fort_text
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils.FortSoundController import g_fortSoundController
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils.FortViewHelper import FortViewHelper
from gui.Scaleform.daapi.view.lobby.fortifications.fort_utils.fort_text import ALERT_TEXT, MAIN_TEXT, STANDARD_TEXT, MIDDLE_TITLE
from gui.Scaleform.daapi.view.lobby.rally import rally_dps
from gui.Scaleform.daapi.view.meta.FortClanBattleRoomMeta import FortClanBattleRoomMeta
from gui.Scaleform.locale.FORTIFICATIONS import FORTIFICATIONS
from gui.Scaleform.locale.RES_ICONS import RES_ICONS
from gui.prb_control.prb_helpers import UnitListener
from gui.shared.ClanCache import g_clanCache
from gui.shared.fortifications.settings import CLIENT_FORT_STATE
from gui.shared.utils import CONST_CONTAINER, findFirst
from helpers import i18n
import ArenaType
from UnitBase import UNIT_OP
from gui.Scaleform.daapi.view.lobby.rally.vo_converters import makeVehicleVO
from gui.Scaleform.daapi.view.lobby.rally import vo_converters
from gui.prb_control import settings, getBattleID
from gui.prb_control.settings import CTRL_ENTITY_TYPE
from gui.shared import events
from gui.shared.ItemsCache import g_itemsCache
from gui.shared.event_bus import EVENT_BUS_SCOPE

class FortClanBattleRoom(FortClanBattleRoomMeta, UnitListener, FortViewHelper):

    class TIMER_GLOW_COLORS(CONST_CONTAINER):
        NORMAL = int('BB6200', 16)
        ALERT = int('BB2B00', 16)

    def __init__(self):
        super(FortClanBattleRoom, self).__init__()
        self.__battleID = None
        self.__battle = None
        self.__allBuildings = None
        self.__prevBuilding = None
        self.__currentBuilding = None
        return

    def onUnitStateChanged(self, unitState, timeLeft):
        self._setActionButtonState()

    def onUnitSettingChanged(self, opCode, value):
        if opCode == UNIT_OP.SET_COMMENT:
            self.as_setCommentS(self.unitFunctional.getCensoredComment())
        elif opCode in [UNIT_OP.CLOSE_SLOT, UNIT_OP.OPEN_SLOT]:
            self._setActionButtonState()

    def onUnitVehicleChanged(self, dbID, vInfo):
        functional = self.unitFunctional
        pInfo = functional.getPlayerInfo(dbID=dbID)
        if pInfo.isInSlot:
            slotIdx = pInfo.slotIdx
            if not vInfo.isEmpty():
                vehicleVO = makeVehicleVO(g_itemsCache.items.getItemByCD(vInfo.vehTypeCD))
                slotCost = vInfo.vehLevel
            else:
                slotState = functional.getSlotState(slotIdx)
                vehicleVO = None
                if slotState.isClosed:
                    slotCost = settings.UNIT_CLOSED_SLOT_COST
                else:
                    slotCost = 0
            self.as_setMemberVehicleS(slotIdx, slotCost, vehicleVO)
        if pInfo.isCreator() or pInfo.isCurrentPlayer():
            self._setActionButtonState()
        return

    def onUnitMembersListChanged(self):
        functional = self.unitFunctional
        if self._candidatesDP:
            self._candidatesDP.rebuild(functional.getCandidates())
        self._updateMembersData()
        self._setActionButtonState()

    def onClientStateChanged(self, state):
        if state.getStateID() == CLIENT_FORT_STATE.HAS_FORT:
            self.__initData()
            self.__makeData()

    def initCandidatesDP(self):
        self._candidatesDP = rally_dps.SortieCandidatesDP()
        self._candidatesDP.init(self.as_getCandidatesDPS(), self.unitFunctional.getCandidates())

    def rebuildCandidatesDP(self):
        self._candidatesDP.rebuild(self.unitFunctional.getCandidates())

    def toggleReadyStateRequest(self):
        self.unitFunctional.doAction()

    def inviteFriendRequest(self):
        self.fireEvent(events.ShowWindowEvent(events.ShowWindowEvent.SHOW_SEND_INVITES_WINDOW, {'prbName': PREBATTLE_TYPE_NAMES[PREBATTLE_TYPE.FORT_BATTLE],
         'ctrlType': CTRL_ENTITY_TYPE.UNIT,
         'showClanOnly': True}), scope=EVENT_BUS_SCOPE.LOBBY)

    def _populate(self):
        super(FortClanBattleRoom, self)._populate()
        self.startFortListening()
        if self.fortState.getStateID() == CLIENT_FORT_STATE.HAS_FORT:
            self.__initData()
            self.__makeData()

    def _dispose(self):
        self.stopFortListening()
        self.__battleID = None
        self.__battle = None
        self.__allBuildings = None
        super(FortClanBattleRoom, self)._dispose()
        return

    def _updateVehiclesLabel(self, minVal, maxVal):
        self.as_setVehiclesTitleS(i18n.makeString(FORTIFICATIONS.SORTIE_ROOM_VEHICLES))

    def _updateRallyData(self):
        functional = self.unitFunctional
        data = vo_converters.makeSortieVO(functional, unitIdx=functional.getUnitIdx(), app=self.app)
        self.as_updateRallyS(data)

    def _getVehicleSelectorDescription(self):
        return FORTIFICATIONS.SORTIE_VEHICLESELECTOR_DESCRIPTION

    def _setActionButtonState(self):
        self.as_setActionButtonStateS(vo_converters.makeSortieClanBattleActionBtnVO(self.unitFunctional))

    def __initData(self):
        fort = self.fortCtrl.getFort()
        self.__battleID = getBattleID()
        self.__battle = fort.getBattle(self.__battleID)
        self.__allBuildings = self.__battle.getAllBuildList()
        self.__prevBuilding = self.__allBuildings[self.__battle.getPrevBuildNum()]
        self.__currentBuilding = self.__allBuildings[self.__battle.getCurrentBuildNum()]

    def __makeData(self):
        self.__makeMainVO()
        self.__setReadyStatus()
        self.__setTimerDelta()
        self.__updateDirections()
        self.__updateHeaderTeamSection()

    @process
    def __makeMainVO(self):
        result = {}
        result['headerDescr'] = fort_text.getText(MAIN_TEXT, i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_MAPTITLE))
        (_, _, arenaTypeID), _ = self.__currentBuilding
        arenaType = ArenaType.g_cache.get(arenaTypeID)
        result['mapName'] = fort_text.getText(MIDDLE_TITLE, arenaType.name)
        result['mapID'] = arenaTypeID
        result['mineClanName'] = g_clanCache.clanTag
        enemyClanDBID, enemyClanAbbev, _ = self.__battle.getOpponentClanInfo()
        result['enemyClanName'] = '[%s]' % enemyClanAbbev
        result['mineClanIcon'] = yield g_clanCache.getClanEmblemID()
        enemyClanEmblemID = 'clanInfo%d' % enemyClanDBID
        result['enemyClanIcon'] = yield g_clanCache.getClanEmblemTextureID(enemyClanDBID, False, enemyClanEmblemID)
        self.as_setBattleRoomDataS(result)

    def __setReadyStatus(self):
        self.as_updateReadyStatusS(False, False)

    def __setTimerDelta(self):
        self.as_setTimerDeltaS({'deltaTime': self.__battle.getAttackTimeLeft(),
         'htmlFormatter': "<font face='$FieldFont' size='18' color='#FFDD99'>###</font>",
         'alertHtmlFormatter': "<font face='$FieldFont' size='18' color='#ff7f00'>###</font>",
         'glowColor': self.TIMER_GLOW_COLORS.NORMAL,
         'alertGlowColor': self.TIMER_GLOW_COLORS.ALERT})

    def __updateDirections(self):
        isAttack = not self.__battle.isDefence()
        (currentBuildingID, _, _), _ = self.__currentBuilding
        if isAttack:
            connectionIcon = RES_ICONS.MAPS_ICONS_LIBRARY_FORTIFICATION_OFFENCE
            connectionIconTTHeader = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BATTLEICON_OFFENCE_TOOLTIP_HEADER)
            connectionIconTTBody = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BATTLEICON_OFFENCE_TOOLTIP_BODY)
            buildingIndicatorTTHeader = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BUILDINGINDICATOR_OFFENCE_TOOLTIP_HEADER)
            buildingIndicatorTTBody = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BUILDINGINDICATOR_OFFENCE_TOOLTIP_BODY, building=i18n.makeString(FORTIFICATIONS.buildings_buildingname(self.UI_BUILDINGS_BIND[currentBuildingID])))
            mineBuildings, mineBaseBuilding = self.__makeBuildingsData(self.__battle.getAttackerBuildList(), self.__battle.getAttackerFullBuildList(), self.__battle.getLootedBuildList())
            enemyBuildings, enemyBaseBuilding = self.__makeBuildingsData(self.__battle.getDefenderBuildList(), self.__battle.getDefenderFullBuildList(), self.__battle.getLootedBuildList(), False)
        else:
            connectionIcon = RES_ICONS.MAPS_ICONS_LIBRARY_FORTIFICATION_DEFENCE
            connectionIconTTHeader = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BATTLEICON_DEFENCE_TOOLTIP_HEADER)
            connectionIconTTBody = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BATTLEICON_DEFENCE_TOOLTIP_BODY)
            buildingIndicatorTTHeader = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BUILDINGINDICATOR_DEFENCE_TOOLTIP_HEADER)
            buildingIndicatorTTBody = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_HEADER_BUILDINGINDICATOR_DEFENCE_TOOLTIP_BODY, building=i18n.makeString(FORTIFICATIONS.buildings_buildingname(self.UI_BUILDINGS_BIND[currentBuildingID])))
            mineBuildings, mineBaseBuilding = self.__makeBuildingsData(self.__battle.getDefenderBuildList(), self.__battle.getDefenderFullBuildList(), self.__battle.getLootedBuildList(), False)
            enemyBuildings, enemyBaseBuilding = self.__makeBuildingsData(self.__battle.getAttackerBuildList(), self.__battle.getAttackerFullBuildList(), self.__battle.getLootedBuildList())
        _, _, enemyClanDir = self.__battle.getOpponentClanInfo()
        isReverse = self.__defineArrowDirection()
        directionsData = {'leftDirection': {'name': i18n.makeString('#fortifications:General/directionName%d' % self.__battle.getDirection()),
                           'isMine': True,
                           'baseBuilding': mineBaseBuilding,
                           'buildings': mineBuildings,
                           'revertArrowDirection': isReverse,
                           'buildingIndicatorTTHeader': buildingIndicatorTTHeader,
                           'buildingIndicatorTTBody': buildingIndicatorTTBody},
         'rightDirection': {'name': i18n.makeString('#fortifications:General/directionName%d' % enemyClanDir),
                            'isMine': False,
                            'baseBuilding': enemyBaseBuilding,
                            'buildings': enemyBuildings,
                            'buildingIndicatorTTHeader': buildingIndicatorTTHeader,
                            'buildingIndicatorTTBody': buildingIndicatorTTBody,
                            'revertArrowDirection': isReverse},
         'connectionIcon': connectionIcon,
         'connectionIconTTHeader': connectionIconTTHeader,
         'connectionIconTTBody': connectionIconTTBody}
        self.as_updateDirectionsS(directionsData)

    def __defineArrowDirection(self):
        if self.__prevBuilding is None:
            return False
        else:
            (prevBuildingID, _, _), prevIsAttacker = self.__prevBuilding
            (curBuildignID, _, _), curIsAttacker = self.__currentBuilding
            if prevIsAttacker != curIsAttacker:
                return False
            currentBuildingList = self.__battle.getAttackerBuildList() if curIsAttacker else self.__battle.getDefenderBuildList()
            result = self.__defineBuildingsOrder(currentBuildingList, prevBuildingID, curBuildignID)
            return result

    def __defineBuildingsOrder(self, buildingList, prevBuildingID, curBuildignID):
        for building in buildingList:
            if building is not None:
                buildingID, buildingRes, _ = building
                if buildingID == prevBuildingID:
                    return True
                if buildingID == curBuildignID:
                    return False

        return False

    def __updateHeaderTeamSection(self):
        isInBattle = self.unitFunctional.getState().isInArena()
        if not isInBattle:
            titleText = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_TEAMSECTIONTITLE_PREPARETEAM)
            titleStyle = STANDARD_TEXT
        else:
            titleText = i18n.makeString(FORTIFICATIONS.FORTCLANBATTLEROOM_TEAMSECTIONTITLE_INBATTLE)
            titleStyle = ALERT_TEXT
        titleText = fort_text.getText(titleStyle, titleText)
        self.as_updateTeamHeaderTextS(titleText)

    def __makeBuildingsData(self, buildingsList, fullBuildingsList, lootedBuildingsList, isAttack = True):
        buildingsData = []
        baseData = None
        for building in fullBuildingsList:
            if building is not None:
                buildingID, status, level, _, _ = building
                buildingData = findFirst(lambda x: x[0] == buildingID, buildingsList)
                isLooted = (buildingData, isAttack) in lootedBuildingsList
                isAvailable = status == FORT_BUILDING_STATUS.READY_FOR_BATTLE
                data = self.__makeBuildingData(buildingID, isAttack, level, isLooted, isAvailable)
                if buildingID == FORT_BUILDING_TYPE.MILITARY_BASE:
                    baseData = data
                else:
                    buildingsData.append(data)
            else:
                buildingsData.append(None)

        return (buildingsData, baseData)

    def __makeBuildingData(self, buildingID, isAttack, level, isLooted, isAvailable):
        (curBuildingId, _, _), curBuildingIsAttack = self.__currentBuilding
        return {'uid': self.UI_BUILDINGS_BIND[buildingID],
         'progress': self._getProgress(buildingID, level),
         'buildingLevel': level,
         'underAttack': curBuildingId == buildingID and curBuildingIsAttack == isAttack,
         'looted': isLooted,
         'isAvailable': isAvailable}

    def onTimerAlert(self):
        g_fortSoundController.playBattleRoomTimerAlert()