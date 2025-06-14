#!/usr/bin/env python3

# Docs for AyatanaAppIndicator3 available at
# https://lazka.github.io/pgi-docs/AyatanaAppIndicator3-0.1/classes/Indicator.html

import os
import gi
import signal

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

gi.require_version("GLib", "2.0")
from gi.repository import GLib

try:
	gi.require_version("AppIndicator3", "0.1")
	from gi.repository import AppIndicator3
except ValueError:
	gi.require_version("AyatanaAppIndicator3", "0.1")
	from gi.repository import AyatanaAppIndicator3 as AppIndicator3

class Server:
	def __init__(self, fd):
		GLib.io_add_watch(
			fd,
			GLib.PRIORITY_DEFAULT,
			GLib.IO_IN,
			self.read_callback,
			None                   # usr_data
		)
		self._old_data = b''
		self._indicators = dict()
		self._handlers = {
			"create": self._create,
			"title": self._title,
			"icon": self._icon,
			"label": self._label,
			"hide": self._hide,
			"show": self._show,
			"menu-clear": self._menu_clear,
			"menu-add": self._menu_add,
			"destroy": self._destroy,
		}

	def _create(self, identifier, icon):
		if identifier in self._indicators:
			print("Not creating the same identifier twice")
			return
		indicator = AppIndicator3.Indicator.new(
			identifier, icon,
			AppIndicator3.IndicatorCategory.APPLICATION_STATUS
		)
		indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
		menu = Gtk.Menu()
		menu.set_reserve_toggle_size(False)
		indicator.set_menu(menu)
		self._indicators[identifier] = indicator

	def _title(self, indicator, args):
		indicator.set_title(args)

	def _icon(self, indicator, args):
		indicator.set_icon(args)

	def _label(self, indicator, args):
		if not getattr(indicator, 'set_label', None):
			print(f"Setting label requires libayatanaindicator")
			return
		indicator.set_label(args, args)

	def _hide(self, indicator, args):
		indicator.set_status(AppIndicator3.IndicatorStatus.PASSIVE)

	def _show(self, indicator, args):
		indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

	def _menu_clear(self, indicator, args):
		menu = Gtk.Menu()
		menu.set_reserve_toggle_size(False)
		indicator.set_menu(menu)

	def _menu_add(self, indicator, args):
		cmd, _, label = args.partition(' ')
		menuitem = Gtk.MenuItem.new_with_label(label)
		menuitem.connect('activate', lambda item : self._execute(cmd))
		indicator.get_menu().append(menuitem)

	def _destroy(self, indicator, args):
		# FIXME:
		#        How the heck does one delete a appindicator?
		#
		#        There is neither a .destroy() nor a .stop()
		#        request and .unref() isn't available either.
		#
		#        Simply dropping all (Python) references so it
		#        triggers the gi internal GC handler doesn't
		#        seem to work either.
		#
		del self._indicators[indicator.get_id()]

	def _execute(self, command):
		# We double fork to reparent the child process to pid 1

		pid = os.fork()
		if pid < 0:
			print("Failed to fork()")
			return

		if pid != 0:
			# main process
			os.waitpid(pid, 0)
			return

		# child process
		try:
			c_pid = os.posix_spawnp(
				command, (command,), os.environ,
				# Not supported on my Python version so can't test.
				#
				# The named pipe uses O_CLOEXEC but not sure if
				# glib opens random fds internally and if they
				# also set O_CLOEXEC.
				#
				# /proc/$c_pid/fd/ looks fine and only seems
				# to inherit stdin, stdout and stderr.
				#
				#file_actions=((os.POSIX_SPAWN_CLOSEFROM, 3),),
				setsid=True,      # create new session
				setsigmask=set(),
				setsigdef=signal.valid_signals(),
			)
			if c_pid < 0:
				print("posix_spawnp failed")
				exit(1)
		except Exception as e:
			print(f"Got exception when starting {command}", type(e), e)
			raise
		finally:
			exit(0)

	def process_command(self, identifier, command, args):
		if command not in self._handlers:
			print(f"Invalid command: '{command}'")
			return
		if command == "create":
			return self._handlers[command](identifier, args)

		indicator = self._indicators.get(identifier, None)
		if not indicator:
			print(f"Unknown indicator: '{identifier}'")
			return
		return self._handlers[command](indicator, args)

	def read_callback(self, fd, flags, usr_data):
		try:
			data = os.read(fd, 4096)
		except Exception as e:
			print("Failed to read data from named pipe:", e)
			self.shutdown()
			return False

		if not data:
			print(f"Could not read from fd {fd}")
			self.shutdown()
			return False

		data = self._old_data + data
		*lines, self._old_data = data.split(b'\n')
		for line in lines:
			line = line.decode()
			identifier, _, line = line.partition(' ')
			command, _, args = line.partition(' ')
			self.process_command(identifier, command, args)
		return True

	def start(self):
		Gtk.main()

	def shutdown(self):
		Gtk.main_quit()

if __name__ == '__main__':
	import sys
	if len(sys.argv) != 2:
		print(f"Usage: {sys.argv[0]} <named_pipe>")
		sys.exit(1)

	fd = -1
	clean_pipe = False
	try:
		# We do need to open the pipe for writing as well,
		# otherwise glib gets mad by not handling IO_HUP correctly.
		fd = os.open(sys.argv[1], os.O_RDWR | os.O_CLOEXEC)
	except FileNotFoundError:
		clean_pipe = True
		os.mkfifo(sys.argv[1])
		fd = os.open(sys.argv[1], os.O_RDWR | os.O_CLOEXEC)

	try:
		server = Server(fd)
		server.start()
	finally:
		os.close(fd)
		if clean_pipe:
			os.remove(sys.argv[1])
