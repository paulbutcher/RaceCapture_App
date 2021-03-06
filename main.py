#!/usr/bin/python
__version__ = "1.2.4"
import sys
if __name__ == '__main__' and sys.platform == 'win32':
    from multiprocessing import freeze_support
    freeze_support()

if __name__ == '__main__':
    import logging
    import argparse
    import kivy
    from kivy.properties import AliasProperty
    from functools import partial
    from kivy.clock import Clock
    from kivy.config import Config
    kivy.require('1.8.0')
    Config.set('graphics', 'width', '1024')
    Config.set('graphics', 'height', '576')
    Config.set('kivy', 'exit_on_escape', 0)
    from kivy.core.window import Window
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.screenmanager import *
    from utils import *
    from installfix_garden_navigationdrawer import NavigationDrawer
    from autosportlabs.racecapture.views.util.alertview import alertPopup
    from autosportlabs.racecapture.views.tracks.tracksview import TracksView
    from autosportlabs.racecapture.views.configuration.rcp.configview import ConfigView
    from autosportlabs.racecapture.views.dashboard.dashboardview import DashboardView
    from autosportlabs.racecapture.views.analysis.analysisview import AnalysisView
    from autosportlabs.racecapture.views.preferences.preferences import PreferencesView
    from autosportlabs.racecapture.menu.mainmenu import MainMenu
    from autosportlabs.comms.commsfactory import comms_factory
    from autosportlabs.racecapture.tracks.trackmanager import TrackManager
    from autosportlabs.racecapture.menu.homepageview import HomePageView
    from autosportlabs.racecapture.settings.systemsettings import SystemSettings
    from autosportlabs.racecapture.settings.prefs import Range
    from toolbarview import ToolbarView

from kivy.app import App, Builder
from autosportlabs.racecapture.config.rcpconfig import RcpConfig
from autosportlabs.racecapture.databus.databus import DataBusFactory, DataBusPump
from autosportlabs.racecapture.api.rcpapi import RcpApi

class RaceCaptureApp(App):

    #container for all settings
    settings = None

    #Central RCP configuration object
    rc_config  = RcpConfig()

    #RaceCapture serial I/O
    _rc_api = RcpApi()

    #dataBus provides an eventing / polling mechanism to parts of the system that care
    _data_bus = None

    #pumps data from rcApi to dataBus. kind of like a bridge
    dataBusPump = DataBusPump()

    #Track database manager
    trackManager = None

    #Application Status bars
    statusBar = None

    #Main Views
    configView = None

    #main navigation menu
    mainNav = None

    #Main Screen Manager
    screenMgr = None

    #main view references for dispatching notifications
    mainViews = None

    #application arguments - initialized upon startup
    app_args = []

    use_kivy_settings = False

    def __init__(self, **kwargs):
        super(RaceCaptureApp, self).__init__(**kwargs)
        #self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        #self._keyboard.bind(on_key_down=self._on_keyboard_down)
        self.settings = SystemSettings(self.user_data_dir)
        self._data_bus = DataBusFactory().create_standard_databus(self.settings.systemChannels)        

        Window.bind(on_key_down=self._on_keyboard_down)
        self.register_event_type('on_tracks_updated')
        self.processArgs()
        self.settings.appConfig.setUserDir(self.user_data_dir)
        self.trackManager = TrackManager(user_dir=self.user_data_dir)

    def _on_keyboard_down(self, keyboard, keycode, *args):
        if keycode == 27:
            self.switchMainView('home')

    def processArgs(self):
        parser = argparse.ArgumentParser(description='Autosport Labs Race Capture App')
        parser.add_argument('-p','--port', help='Port', required=False)
        if sys.platform == 'win32':
            parser.add_argument('--multiprocessing-fork', required=False, action='store_true')

        self.app_args = vars(parser.parse_args())

    def getAppArg(self, name):
        return self.app_args.get(name, None)

    def loadCurrentTracksSuccess(self):
        print('Curent Tracks Loaded')
        Clock.schedule_once(lambda dt: self.notifyTracksUpdated())

    def loadCurrentTracksError(self, details):
        alertPopup('Error Loading Tracks', str(details))

    def init_data(self):
        self.trackManager.init(None, self.loadCurrentTracksSuccess, self.loadCurrentTracksError)

    def _serial_warning(self):
        alertPopup('Warning', 'Command failed. Ensure you have selected a correct serial port')

    #Logfile
    def on_poll_logfile(self, instance):
        try:
            self._rc_api.getLogfile()
        except:
            pass


    def on_set_logfile_level(self, instance, level):
        try:
            self._rc_api.setLogfileLevel(level, None, self.on_set_logfile_level_error)
        except:
            logging.exception('')
            self._serial_warning()

    def on_set_logfile_level_error(self, detail):
        alertPopup('Error', 'Error Setting Logfile Level:\n\n' + str(detail))

    #Run Script
    def on_run_script(self, instance):
        self._rc_api.runScript(self.on_run_script_complete, self.on_run_script_error)

    def on_run_script_complete(self, result):
        print('run script complete: ' + str(result))

    def on_run_script_error(self, detail):
        alertPopup('Error Running', 'Error Running Script:\n\n' + str(detail))

    #Write Configuration
    def on_write_config(self, instance, *args):
        rcpConfig = self.rc_config
        try:
            self._rc_api.writeRcpCfg(rcpConfig, self.on_write_config_complete, self.on_write_config_error)
            self.showActivity("Writing configuration")
        except:
            logging.exception('')
            self._serial_warning()

    def on_write_config_complete(self, result):
        self.rc_config.stale = False
        Clock.schedule_once(lambda dt: self.configView.dispatch('on_config_written'))

    def on_write_config_error(self, detail):
        alertPopup('Error Writing', 'Could not write configuration:\n\n' + str(detail))

    #Read Configuration
    def on_read_config(self, instance, *args):
        try:
            self._rc_api.getRcpCfg(self.rc_config, self.on_read_config_complete, self.on_read_config_error)
            self.showActivity("Reading configuration")
        except:
            logging.exception('')
            self._serial_warning()

    def on_read_config_complete(self, rcpCfg):
        Clock.schedule_once(lambda dt: self.configView.dispatch('on_config_updated', self.rc_config))
        self.rc_config.stale = False
        self.showActivity('')

    def on_read_config_error(self, detail):
        alertPopup('Error Reading', 'Could not read configuration:\n\n' + str(detail))


    def on_tracks_updated(self, track_manager):
        for view in self.mainViews.itervalues():
            view.dispatch('on_tracks_updated', track_manager)

    def notifyTracksUpdated(self):
        self.dispatch('on_tracks_updated', self.trackManager)

    def on_main_menu_item(self, instance, value):
        self.switchMainView(value)

    def on_main_menu(self, instance, *args):
        self.mainNav.toggle_state()

    def showMainView(self, viewKey):
        try:
            self.screenMgr.current = viewKey
        except Exception as detail:
            print('Failed to load main view ' + str(viewKey) + ' ' + str(detail))

    def switchMainView(self, viewKey):
            self.mainNav.anim_to_state('closed')
            Clock.schedule_once(lambda dt: self.showMainView(viewKey), 0.25)

    def showStatus(self, status, isAlert):
        self.statusBar.dispatch('on_status', status, isAlert)

    def showActivity(self, status):
        self.statusBar.dispatch('on_activity', status)

    def _setX(self, x):
        pass

    def _getX(self):
        pass

    def on_start(self):
        Clock.schedule_once(lambda dt: self.init_data())
        Clock.schedule_once(lambda dt: self.init_rc_comms())

    def on_stop(self):
        self._rc_api.cleanup_comms()

    def build(self):
        Builder.load_file('racecapture.kv')
        statusBar = kvFind(self.root, 'rcid', 'statusbar')
        statusBar.bind(on_main_menu=self.on_main_menu)
        self.statusBar = statusBar

        mainMenu = kvFind(self.root, 'rcid', 'mainMenu')
        mainMenu.bind(on_main_menu_item=self.on_main_menu_item)

        self.mainNav = kvFind(self.root, 'rcid', 'mainNav')

        #reveal_below_anim
        #reveal_below_simple
        #slide_above_anim
        #slide_above_simple
        #fade_in
        self.mainNav.anim_type = 'slide_above_anim'

        configView = ConfigView(name='config',
                                rcpConfig=self.rc_config,
                                rc_api=self._rc_api,
                                dataBusPump=self.dataBusPump,
                                settings=self.settings)
        configView.bind(on_read_config=self.on_read_config)
        configView.bind(on_write_config=self.on_write_config)
        configView.bind(on_run_script=self.on_run_script)
        configView.bind(on_poll_logfile=self.on_poll_logfile)
        configView.bind(on_set_logfile_level=self.on_set_logfile_level)

        rcComms = self._rc_api
        rcComms.addListener('logfile', lambda value: Clock.schedule_once(lambda dt: configView.on_logfile(value)))
        rcComms.on_progress = lambda value: statusBar.dispatch('on_progress', value)
        rcComms.on_rx = lambda value: statusBar.dispatch('on_rc_rx', value)
        rcComms.on_tx = lambda value: statusBar.dispatch('on_rc_tx', value)

        tracksView = TracksView(name='tracks')

        dashView = DashboardView(name='dash', dataBus=self._data_bus, settings=self.settings)

        homepageView = HomePageView(name='home')
        homepageView.bind(on_select_view = lambda instance, viewKey: self.switchMainView(viewKey))

        analysisView = AnalysisView(name='analysis', data_bus=self._data_bus, settings=self.settings)
        preferences_view = PreferencesView(self.settings, name='preferences')

        screenMgr = kvFind(self.root, 'rcid', 'main')

        #NoTransition
        #SlideTransition
        #SwapTransition
        #FadeTransition
        #WipeTransition
        #FallOutTransition
        #RiseInTransition
        screenMgr.transition=NoTransition()

        screenMgr.add_widget(homepageView)
        screenMgr.add_widget(configView)
        screenMgr.add_widget(tracksView)
        screenMgr.add_widget(dashView)
        screenMgr.add_widget(analysisView)
        screenMgr.add_widget(preferences_view)

        self.mainViews = {'config' : configView,
                          'tracks': tracksView,
                          'dash': dashView,
                          'analysis': analysisView,
                          'preferences': preferences_view}

        self.screenMgr = screenMgr

        self.configView = configView
        self.icon = ('resource/images/app_icon_128x128.ico' if sys.platform == 'win32' else 'resource/images/app_icon_128x128.png')

    def init_rc_comms(self):
        port = self.getAppArg('port')
        comms = comms_factory(port)
        rc_api = self._rc_api
        rc_api.detect_win_callback = self.rc_detect_win
        rc_api.detect_fail_callback = self.rc_detect_fail
        rc_api.detect_activity_callback = self.rc_detect_activity
        rc_api.init_comms(comms)
        rc_api.run_auto_detect()


    def rc_detect_win(self, rcpVersion):
        self.showStatus("{} v{}.{}.{}".format(rcpVersion.friendlyName, rcpVersion.major, rcpVersion.minor, rcpVersion.bugfix), False)
        self.dataBusPump.startDataPump(self._data_bus, self._rc_api)

        if self.rc_config.loaded == False:
            Clock.schedule_once(lambda dt: self.on_read_config(self))
        else:
            self.showActivity('Connected')

    def rc_detect_fail(self):
        self.showStatus("Could not detect RaceCapture/Pro", True)
        Clock.schedule_once(lambda dt: self._rc_api.run_auto_detect(), 1.0)

    def rc_detect_activity(self, info):
        self.showActivity('Searching {}'.format(info))

    def open_settings(self, *largs):
        self.switchMainView('preferences')


if __name__ == '__main__':
    RaceCaptureApp().run()
