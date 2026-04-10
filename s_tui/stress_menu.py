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

"""A class to control the options of stress in a menu"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

import psutil
import urwid


class StressMenu:
    MAX_TITLE_LEN = 50

    def __init__(self, return_fn: Callable[[], None], stress_exe: str | None) -> None:
        self.return_fn = return_fn

        self.stress_exe = stress_exe

        self.time_out = "none"
        self.sqrt_workers = "1"
        try:
            self.sqrt_workers = str(psutil.cpu_count())
            logging.info("num cpus %s", self.sqrt_workers)
        except OSError as err:
            logging.debug(err)

        self.sync_workers = "0"
        self.memory_workers = "0"
        self.malloc_byte = "256M"
        self.byte_touch_cnt = "4096"
        self.malloc_delay = "none"
        self.no_malloc = False
        self.write_workers = "0"
        self.write_bytes = "1G"

        self.time_out_ctrl = urwid.Edit("Time out [sec]: ", self.time_out)
        self.sqrt_workers_ctrl = urwid.Edit("Sqrt() worker count: ", self.sqrt_workers)
        self.sync_workers_ctrl = urwid.Edit("Sync() worker count: ", self.sync_workers)
        self.memory_workers_ctrl = urwid.Edit(
            "Malloc() / Free() worker count: ", self.memory_workers
        )
        self.malloc_byte_ctrl = urwid.Edit("   Bytes per malloc*: ", self.malloc_byte)
        self.byte_touch_cnt_ctrl = urwid.Edit(
            "   Touch a byte after * bytes: ", self.byte_touch_cnt
        )
        self.malloc_delay_ctrl = urwid.Edit(
            "   Sleep time between Free() [sec]: ", self.malloc_delay
        )
        self.no_malloc_ctrl = urwid.CheckBox(
            '"dirty" the memory \ninstead of free / alloc', self.no_malloc
        )
        self.write_workers_ctrl = urwid.Edit(
            "Write() / Unlink() worker count: ", self.write_workers
        )
        self.write_bytes_ctrl = urwid.Edit("   Byte per Write(): ", self.write_bytes)

        default_button = urwid.Button("Default", on_press=self.on_default)
        default_button._label.align = "center"

        save_button = urwid.Button("Save", on_press=self.on_save)
        save_button._label.align = "center"

        cancel_button = urwid.Button("Cancel", on_press=self.on_cancel)
        cancel_button._label.align = "center"

        if_buttons = urwid.Columns([default_button, save_button, cancel_button])

        title = urwid.Text(("bold text", "  Stress Options  \n"), "center")

        self.titles = [
            title,
            self.time_out_ctrl,
            urwid.Divider("-"),
            self.sqrt_workers_ctrl,
            urwid.Divider("-"),
            self.sync_workers_ctrl,
            urwid.Divider("-"),
            self.memory_workers_ctrl,
            urwid.Divider(),
            self.malloc_byte_ctrl,
            urwid.Divider(),
            self.byte_touch_cnt_ctrl,
            urwid.Divider(),
            self.malloc_delay_ctrl,
            urwid.Divider(),
            self.no_malloc_ctrl,
            urwid.Divider("-"),
            self.write_workers_ctrl,
            urwid.Divider(),
            self.write_bytes_ctrl,
            urwid.Divider("-"),
            if_buttons,
        ]

        self.main_window = urwid.LineBox(urwid.ListBox(self.titles))

    def set_edit_texts(self) -> None:
        pass

    def on_default(self, _):
        pass

    def get_size(self) -> tuple[int, int]:
        return len(self.titles) + 5, self.MAX_TITLE_LEN

    def on_save(self, _):
        pass

    def on_cancel(self, _):
        pass

    def get_stress_cmd(self) -> list[str]:
        pass

    @staticmethod
    def get_pos_num(num: str, default: str) -> str:
        pass

    @staticmethod
    def get_valid_byte(num: str, default: str) -> str:
        """check if the format of number is (num)(G|m|B) i.e 500GB, 200mb. 400
        etc.."""
        pass
