# Python bytecode 2.7 (decompiled from Python 2.7)
# Embedded file name: scripts/client/gui/Scaleform/daapi/view/bootcamp/BCPreBattleTimer.py
from gui.Scaleform.daapi.view.battle.shared.prebattle_timers.timer_base import PreBattleTimerBase

class BCPreBattleTimer(PreBattleTimerBase):

    def updateBattleCtx(self, battleCtx):
        self.as_setWinConditionTextS(battleCtx.getArenaWinString())

    def as_setMessageS(self, msg):
        pass
