#!/usr/bin/env python
#
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
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA

"""A menu to view and change CPU governor and energy performance preference."""

from __future__ import annotations

import glob
import logging
import subprocess
from collections.abc import Callable

import urwid

from s_tui.helper_functions import cat
from s_tui.sturwid.ui_elements import ViListBox

# Sysfs paths (cpu0 used for reading available options and current state)
SYSFS_AVAIL_GOVERNORS = (
    "/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
)
SYSFS_GOVERNOR = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
SYSFS_AVAIL_EPP = (
    "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences"
)
SYSFS_EPP = "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference"

# Glob patterns for writing to all cores
_SYSFS_ALL_GOVERNORS = "/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
_SYSFS_ALL_EPP = "/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"

# Mapping from EPP sysfs value to powerprofilesctl profile name
_EPP_TO_PROFILE = {
    "performance": "performance",
    "balance_performance": "balanced",
    "power": "power-saver",
}


def read_available(path: str) -> list[str]:
    """Read space-separated values from a sysfs file, return empty list on failure."""
    pass


def _read_current(path: str) -> str:
    """Read the current value from a sysfs file."""
    pass


def _write_all_cores(pattern: str, value: str) -> None:
    """Write a value to all matching sysfs paths (requires root)."""
    pass


def _set_epp_via_powerprofilesctl(exe: str, epp_value: str) -> None:
    """Set EPP using powerprofilesctl. Raises OSError on failure."""
    pass


class PowerProfileMenu:
    MAX_TITLE_LEN = 50

    def __init__(
        self,
        return_fn: Callable[[], None],
        powerprofilesctl_exe: str | None,
        can_write_governor: bool,
        can_write_epp: bool,
        available_governors: list[str] | None = None,
        available_epp: list[str] | None = None,
    ) -> None:
        self.return_fn = return_fn
        self.powerprofilesctl_exe = powerprofilesctl_exe
        self.can_write_governor = can_write_governor
        self.can_write_epp = can_write_epp

        # Read available options if not provided
        self.available_governors = (
            available_governors
            if available_governors is not None
            else read_available(SYSFS_AVAIL_GOVERNORS)
        )
        self.available_epp = (
            available_epp
            if available_epp is not None
            else read_available(SYSFS_AVAIL_EPP)
        )

        # Determine what's controllable
        self.governor_controllable = (
            can_write_governor and len(self.available_governors) > 1
        )
        self.epp_controllable = (
            can_write_epp or powerprofilesctl_exe is not None
        ) and len(self.available_epp) > 0

        # Status message area
        self.status_text = urwid.Text("")

        # Build UI
        self.titles: list[urwid.Widget] = []
        self._build_ui()

        self.main_window = urwid.LineBox(
            ViListBox(urwid.SimpleFocusListWalker(self.titles)),
            title="Power Profile",
        )

    def _build_ui(self) -> None:
        pass

    def get_size(self) -> tuple[int, int]:
        return len(self.titles) + 5, self.MAX_TITLE_LEN

    def is_controllable(self) -> bool:
        """Return True if at least one section is controllable."""
        pass

    def refresh_state(self) -> None:
        """Re-read current governor/EPP from sysfs and update radio buttons."""
        pass

    def _get_selected_governor(self) -> str | None:
        """Return the currently selected governor radio button label."""
        pass

    def _get_selected_epp(self) -> str | None:
        """Return the currently selected EPP radio button label."""
        pass

    def on_apply(self, _: object) -> None:
        """Apply the selected governor and/or EPP."""
        pass

    def _apply_epp(self, epp: str) -> None:
        """Apply EPP value using the best available method."""
        pass

    def on_cancel(self, _: object) -> None:
        """Reset radio buttons to current state and close."""
        pass
