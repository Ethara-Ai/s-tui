#!/usr/bin/python

# Copyright (C) 2017-2025 Alex Manuskin, Gil Tsuker
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA
#
# This implementation was inspired by Ian Ward
# Urwid web site: http://excess.org/urwid/

"""CPU stress and monitoring utility"""

import argparse
import atexit
import configparser
import contextlib
import logging
import os
import signal
import subprocess
import sys
import time
import timeit
from collections import OrderedDict, defaultdict

import psutil
import urwid

# Menus
from s_tui.about_menu import AboutMenu
from s_tui.builtin_stress_menu import BuiltinStressMenu
from s_tui.builtin_stresser import BuiltinStresser
from s_tui.help_menu import HELP_MESSAGE, HelpMenu

# Helpers
from s_tui.helper_functions import (
    __version__,
    cat,
    get_processor_name,
    get_user_config_dir,
    get_user_config_file,
    kill_child_processes,
    make_user_config_dir,
    output_to_csv,
    output_to_json,
    output_to_terminal,
    seconds_to_text,
    str_to_bool,
    user_config_dir_exists,
    user_config_file_exists,
    which,
)
from s_tui.power_profile_menu import (
    SYSFS_AVAIL_EPP,
    SYSFS_AVAIL_GOVERNORS,
    SYSFS_EPP,
    SYSFS_GOVERNOR,
    PowerProfileMenu,
    read_available,
)
from s_tui.sensors_menu import SensorsMenu
from s_tui.sources.fan_source import FanSource
from s_tui.sources.freq_source import FreqSource
from s_tui.sources.rapl_power_source import RaplPowerSource
from s_tui.sources.script_hook_loader import ScriptHookLoader
from s_tui.sources.temp_source import TempSource

# Sources
from s_tui.sources.util_source import UtilSource
from s_tui.stress_menu import StressMenu
from s_tui.sturwid.bar_graph_vector import BarGraphVector
from s_tui.sturwid.summary_text_list import SummaryTextList

# Ui Elements
from s_tui.sturwid.ui_elements import DEFAULT_PALETTE, ViListBox, button, radio_button

UPDATE_INTERVAL = 1
HOOK_INTERVAL = 30 * 1000
DEGREE_SIGN = "\N{DEGREE SIGN}"
ZERO_TIME = seconds_to_text(0)

DEFAULT_LOG_FILE = "_s-tui.log"

DEFAULT_CSV_FILE = "s-tui_log_" + time.strftime("%Y-%m-%d_%H_%M_%S") + ".csv"

VERSION_MESSAGE = (
    "s-tui "
    + __version__
    + " - (C) 2017-2025 Alex Manuskin, Gil Tsuker\n\
    Released under GNU GPLv2"
)

ERROR_MESSAGE = "\n\
        Oops! s-tui has encountered a fatal error\n\
        Please report this bug here: https://github.com/amanusk/s-tui"

graph_controller = None


class MainLoop(urwid.MainLoop):
    """Inherit urwid Mainloop to catch special character inputs"""

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: object) -> None:
        """signal handler for properly exiting Ctrl+C"""
        pass

    def unhandled_input(self, data):  # type: ignore[override]
        pass


class StressController:
    """
    Responsible for storing the data related to stress test options
    and operation
    """

    def __init__(self, stress_installed):
        self.stress_modes = ["Monitor"]
        self.stress_modes.append("s-tui stress")

        if stress_installed:
            self.stress_modes.append("Stress (ext)")

        self.current_mode = self.stress_modes[0]
        self.stress_process = None
        self._builtin_stresser = None

    def get_modes(self):
        """Returns all possible stress_modes for stress operations"""
        pass

    def get_current_mode(self):
        """Returns the current stress test mode, monitor/stress/other"""
        return self.current_mode

    def set_mode(self, mode):
        """Sets a stress test mode monitor/stress/other"""
        pass

    def get_stress_process(self):
        """Returns the current external stress process running"""
        pass

    def set_stress_process(self, proc):
        """Sets the current stress process running"""
        pass

    @property
    def builtin_stresser(self):
        """Lazy-init BuiltinStresser on first use.

        Avoids creating multiprocessing primitives at startup, which can
        fail in restricted environments (e.g. containers without
        /dev/shm).
        """
        pass

    def kill_stress_process(self):
        """Kills the current running stress process"""
        try:
            kill_child_processes(self.stress_process)
        except psutil.NoSuchProcess:
            logging.debug("Stress process no longer exists")
        self.stress_process = None
        if self._builtin_stresser is not None:
            self._builtin_stresser.stop()

    def start_stress(self, stress_cmd):
        """Starts a new stress process with a given cmd"""
        pass

    def start_builtin_stress(self, num_workers, strategy=None):
        """Starts the built-in Python CPU stresser."""
        pass


class GraphView(urwid.WidgetPlaceholder):
    """
    A class responsible for providing the application's interface and
    graph display.
    The GraphView can change the state of the graph, since it provides the UI
    The change is state should be reflected in the GraphController
    """

    def __init__(self, controller):
        # constants
        self.left_margin = 0
        self.top_margin = 0

        # main control
        self.controller = controller
        self.main_window_w = []
        # Track per-source update failures to avoid log spam while preserving
        # actionable logs when failures start/stop.
        self.source_update_errors = {}

        # general urwid items
        self.clock_view = urwid.Text(ZERO_TIME, align="center")
        self.governor_view = urwid.Text("", align="center")
        self.epp_view = urwid.Text("", align="center")
        self._update_cpu_policy()
        self.refresh_rate_ctrl = urwid.Edit(
            ("Refresh[s]:"), self.controller.refresh_rate
        )
        self.hline = urwid.AttrMap(urwid.SolidFill(" "), "line")
        self.vline = urwid.WidgetPlaceholder(
            urwid.AttrMap(urwid.SolidFill("|"), "line")  # type: ignore[arg-type]
        )

        self.mode_buttons = []

        self.summary_widget_index = None

        # Visible graphs are the graphs currently displayed, this is a
        # subset of the available graphs for display
        self.graph_place_holder = urwid.WidgetPlaceholder(urwid.Pile([]))  # type: ignore[arg-type]

        # construct the various menus during init phase
        self.stress_menu = StressMenu(self.on_menu_close, self.controller.stress_exe)
        self.builtin_stress_menu = BuiltinStressMenu(self.on_menu_close)
        self.help_menu = HelpMenu(self.on_menu_close)
        self.about_menu = AboutMenu(self.on_menu_close)
        self.graphs_menu = SensorsMenu(
            self.on_graphs_menu_close,
            self.controller.sources,
            self.controller.graphs_default_conf,
        )
        self.summary_menu = SensorsMenu(
            self.on_summary_menu_close,
            self.controller.sources,
            self.controller.summary_default_conf,
        )

        # Create power profile menu if at least one setting is controllable
        self.power_profile_menu = self._create_power_profile_menu()

        # call super
        urwid.WidgetPlaceholder.__init__(self, self.main_window())  # type: ignore[arg-type]
        urwid.connect_signal(self.refresh_rate_ctrl, "change", self.update_refresh_rate)

    def update_refresh_rate(self, _, new_refresh_rate):
        # Special case of 'q' in refresh rate
        pass

    def update_displayed_information(self):
        """Update all the graphs that are being displayed"""

        recoverable_source_errors = (OSError, IOError, TypeError, ValueError)
        debug_mode = self.controller.args.debug or self.controller.args.debug_run

        for source in self.controller.sources:
            source_name = source.get_source_name()
            if any(self.graphs_menu.active_sensors[source_name]) or any(
                self.summary_menu.active_sensors[source_name]
            ):
                try:
                    source.update()
                    previous_error = self.source_update_errors.pop(source_name, None)
                    if previous_error is not None:
                        logging.info(
                            "Source %s recovered from update errors (%s)",
                            source_name,
                            previous_error,
                        )
                except recoverable_source_errors as err:
                    error_name = err.__class__.__name__
                    previous_error = self.source_update_errors.get(source_name)
                    self.source_update_errors[source_name] = error_name
                    if previous_error != error_name:
                        logging.warning(
                            "Source %s update failed with recoverable %s: %s",
                            source_name,
                            error_name,
                            err,
                        )
                    else:
                        logging.debug(
                            "Source %s update still failing with %s",
                            source_name,
                            error_name,
                        )
                except Exception as err:
                    error_name = err.__class__.__name__
                    self.source_update_errors[source_name] = error_name
                    logging.exception(
                        "Source %s update failed with unexpected %s",
                        source_name,
                        error_name,
                    )
                    if debug_mode:
                        raise

        for graph in self.visible_graphs.values():
            try:
                graph.update()
            except IndexError:
                logging.debug("Graph update failed")

        # update graph summery
        for summary in self.visible_summaries.values():
            try:
                summary.update()
            except IndexError:
                logging.debug("Summary update failed")

        self._update_cpu_policy()

        # Only update clock if not is stress mode
        if self.controller.stress_controller.get_current_mode() != "Monitor":
            self.clock_view.set_text(
                seconds_to_text(
                    timeit.default_timer() - self.controller.stress_start_time
                )
            )

    def on_reset_button(self, _):
        """Reset graph data and display empty graph"""
        pass

    def on_menu_close(self):
        """Return to main screen"""
        pass

    def on_graphs_menu_close(self, update):
        """Return to main screen and update sensor that
        are active in the view"""
        pass

    def on_summary_menu_close(self, update):
        """Return to main screen and update sensor that
        are active in the view"""
        pass

    def _open_menu_overlay(self, menu):
        """Helper to open a menu overlay with cached size"""
        pass

    def on_stress_menu_open(self, widget):
        """Open stress options"""
        pass

    def on_builtin_stress_menu_open(self, widget):
        """Open built-in stress options"""
        pass

    def on_help_menu_open(self, widget):
        """Open Help menu"""
        pass

    def on_about_menu_open(self, widget):
        """Open About menu"""
        pass

    def on_graphs_menu_open(self, widget):
        """Open Sensor menu on top of existing frame"""
        pass

    def on_summary_menu_open(self, widget):
        """Open Sensor menu on top of existing frame"""
        pass

    def _create_power_profile_menu(self) -> PowerProfileMenu | None:
        """Create the power profile menu if at least one setting is controllable."""
        pass

    def on_power_profile_menu_open(self, widget):
        """Open Power Profile menu"""
        pass

    def on_mode_button(self, my_button, state):
        """Notify the controller of a new mode setting."""
        pass

    def on_unicode_checkbox(self, w=None, state=False):
        """Enable smooth edges if utf-8 is supported"""
        pass

    def on_save_settings(self, w=None):
        """Calls controller save settings method"""
        pass

    def on_exit_program(self, w=None):
        """Calls controller exit_program method"""
        pass

    def _generate_graph_controls(self):
        """Display sidebar controls. i.e. buttons, and controls"""
        pass

    def _update_cpu_policy(self):
        """Read CPU governor and energy performance preference from sysfs."""
        try:
            self.governor_view.set_text(cat(SYSFS_GOVERNOR, binary=False).strip())
        except OSError:
            self.governor_view.set_text("N/A")
        try:
            self.epp_view.set_text(cat(SYSFS_EPP, binary=False).strip())
        except OSError:
            self.epp_view.set_text("N/A")

    @staticmethod
    def _generate_cpu_stats():
        """Read and display processor name"""
        pass

    def _generate_summaries(self):
        pass

    def show_graphs(self):
        """Show a pile of the graph selected for display"""
        self.graph_place_holder.original_widget = urwid.Pile(
            list(self.visible_graphs.values())
        )

    def main_window(self):
        # initiating the graphs
        pass


class GraphController:
    """
    The GraphController holds the state of the graph, this includes the current
    * Operation mode (stress/no-stress)
    * Current selected graphs for display,
    * The state of the radio and selector buttons
    * The current graphs refresh rate

    The controller is generated once, and is updated according to inputs

    GraphController and GraphView are closely intertwined, there is a reference
    to each in the other.
    This is not perfect, but changes in the View reflect on the graph state and
    visa versa
    """

    def _load_config(self, t_thresh):
        """
        Uses configurations defined by user to configure sources for display.
        This should be the only place where sources are initiated

        This returns a list of sources after configurations are applied
        """
        pass

    def _config_stress(self):
        """Configures the possible stress processes and modes"""
        pass

    def __init__(self, args):
        self.conf = None
        self.script_hooks_enabled = True
        self.script_loader = None

        self.refresh_rate = args.refresh_rate

        self.smooth_graph_mode = False

        self.summary_default_conf = defaultdict(dict)
        self.graphs_default_conf = defaultdict(dict)

        self.temp_thresh = None

        possible_sources = self._load_config(args.t_thresh)

        # Needed for use in view
        self.args = args

        self.stress_controller = self._config_stress()

        self.powerprofilesctl_exe = which("powerprofilesctl")

        self.handle_mouse = not args.no_mouse

        self.stress_start_time = 0

        # construct sources
        self.sources = [s for s in possible_sources if s.get_is_available()]

        # The view has a reference to the controller and visa versa
        self.view = GraphView(self)

        # Update csv file to save
        self.csv_file = None
        self.save_csv = args.csv
        if args.csv_file is not None:
            self.csv_file = args.csv_file
            logging.info("Printing output to csv %s", self.csv_file)
        elif args.csv_file is None and args.csv:
            self.csv_file = DEFAULT_CSV_FILE
        # Debug counter
        self.debug_run_counter = 0

    def set_mode(self, mode):
        """Allow our view to set the mode."""
        pass

    def main(self):
        """Starts the main loop and graph animation"""
        loop = MainLoop(
            self.view,
            DEFAULT_PALETTE,
            handle_mouse=self.handle_mouse,
            # screen=urwid.curses_display.Screen()
        )
        self.view.show_graphs()
        self.animate_graph(loop)
        try:
            loop.run()
        except ZeroDivisionError as err:
            # In case of Zero division, we want an error to return, and
            # get a clue where this happens
            logging.debug("Some stat caused divide by zero exception. Exiting")
            logging.error(err, exc_info=True)
            print(ERROR_MESSAGE)
        except AttributeError as err:
            # In this case we restart the loop, to address bug #50, where
            # urwid crashes on multiple presses on 'esc'
            logging.debug("Catch attribute Error in urwid and restart")
            logging.debug(err, exc_info=True)
            self.main()
        except psutil.NoSuchProcess as err:
            # This might happen if the stress process is not found, in this
            # case, we want to know why
            logging.error("No such process error")
            logging.error(err, exc_info=True)
            print(ERROR_MESSAGE)

    def update_stress_mode(self):
        """Updates stress mode according to radio buttons state"""
        pass

    def save_settings(self):
        """Save the current configuration to a user config file"""
        pass

    def exit_program(self):
        """Kill all stress operations upon exit"""
        self.stress_controller.kill_stress_process()
        raise urwid.ExitMainLoop()

    def animate_graph(self, loop, user_data=None):
        """
        Update the graph and schedule the next update
        This is where the magic happens
        """
        self.view.update_displayed_information()

        # Save to CSV if configured
        if (self.save_csv or self.csv_file is not None) and self.csv_file is not None:
            output_to_csv(self.view.summaries, self.csv_file)

        # Set next update
        self.animate_alarm = loop.set_alarm_in(
            float(self.refresh_rate), self.animate_graph
        )

        if self.args.debug_run:
            # refresh rate is a string in float format
            self.debug_run_counter += int(float(self.refresh_rate))
            if self.debug_run_counter >= 8:
                self.exit_program()


def main():
    args = get_args()
    # Print version and exit
    if args.version:
        print(VERSION_MESSAGE)
        sys.exit(0)

    # Setup logging util
    log_file = DEFAULT_LOG_FILE
    if args.debug_run:
        args.debug = True

    log_formatter = logging.Formatter(
        "%(asctime)s [%(funcName)s()] [%(levelname)-5.5s]  %(message)s"
    )
    root_logger = logging.getLogger()

    if args.debug or args.debug_file is not None:
        level = logging.DEBUG
        if args.debug_file is not None:
            log_file = args.debug_file
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(log_formatter)
        root_logger.addHandler(file_handler)
    else:
        level = logging.ERROR
    root_logger.setLevel(level)

    if args.terminal or args.json:
        logging.info("Printing single line to terminal")
        sources = [
            FreqSource(),
            TempSource(),
            UtilSource(),
            RaplPowerSource(),
            FanSource(),
        ]
        if args.terminal:
            output_to_terminal(sources)
        elif args.json:
            output_to_json(sources)

    global graph_controller
    graph_controller = GraphController(args)
    atexit.register(graph_controller.stress_controller.kill_stress_process)
    graph_controller.main()


def get_args():
    parser = argparse.ArgumentParser(
        description=HELP_MESSAGE, formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        "-d",
        "--debug",
        default=False,
        action="store_true",
        help="Output debug log to _s-tui.log",
    )
    parser.add_argument(
        "--debug-file",
        default=None,
        help="Use a custom debug file. Default: " + "_s-tui.log",
    )
    # This is mainly to be used for testing purposes
    parser.add_argument(
        "-dr",
        "--debug_run",
        default=False,
        action="store_true",
        help="Run for 5 seconds and quit",
    )
    parser.add_argument(
        "-c", "--csv", action="store_true", default=False, help="Save stats to csv file"
    )
    parser.add_argument(
        "--csv-file",
        default=None,
        help="Use a custom CSV file. Default: " + "s-tui_log_<TIME>.csv",
    )
    parser.add_argument(
        "-t",
        "--terminal",
        action="store_true",
        default=False,
        help="Display a single line of stats without tui",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="Display a single line of stats in JSON format",
    )
    parser.add_argument(
        "-nm",
        "--no-mouse",
        action="store_true",
        default=False,
        help="Disable Mouse for TTY systems",
    )
    parser.add_argument(
        "-v", "--version", default=False, action="store_true", help="Display version"
    )
    parser.add_argument(
        "-tt",
        "--t_thresh",
        default=None,
        help="High Temperature threshold. Default: 80",
    )
    parser.add_argument(
        "-r",
        "--refresh-rate",
        dest="refresh_rate",
        default="2.0",
        help="Refresh rate in seconds. Default: 2.0",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    main()
