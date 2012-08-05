# Copyright (C) 2009, 2010, 2011  Roman Zimbelmann <romanz@lavabit.com>
# This software is distributed under the terms of the GNU GPL version 3.

"""
The main function responsible to initialize the FM object and stuff.
"""

import os.path

def main():
	"""initialize objects and run the filemanager"""
	import locale
	import ranger
	import sys
	from ranger.core.shared import (EnvironmentAware, FileManagerAware,
			SettingsAware)
	from ranger.core.fm import FM

	if not sys.stdin.isatty():
		sys.stderr.write("Error: Must run ranger from terminal\n")
		raise SystemExit(1)

	try:
		locale.setlocale(locale.LC_ALL, '')
	except:
		print("Warning: Unable to set locale.  Expect encoding problems.")

	# so that programs can know that ranger spawned them:
	level = 'RANGER_LEVEL'
	if level in os.environ and os.environ[level].isdigit():
		os.environ[level] = str(int(os.environ[level]) + 1)
	else:
		os.environ[level] = '1'

	if not 'SHELL' in os.environ:
		os.environ['SHELL'] = 'bash'

	ranger.arg = arg = parse_arguments()
	if arg.copy_config is not None:
		fm = FM()
		fm.copy_config_files(arg.copy_config)
		return 1 if arg.fail_unless_cd else 0
	if arg.list_tagged_files:
		fm = FM()
		try:
			f = open(fm.confpath('tagged'), 'r')
		except:
			pass
		else:
			for line in f.readlines():
				if len(line) > 2 and line[1] == ':':
					if line[0] in arg.list_tagged_files:
						sys.stdout.write(line[2:])
				elif len(line) > 0 and '*' in arg.list_tagged_files:
					sys.stdout.write(line)
		return 1 if arg.fail_unless_cd else 0

	SettingsAware._setup(clean=arg.clean)

	if arg.selectfile:
		arg.selectfile = os.path.abspath(arg.selectfile)
		arg.targets.insert(0, os.path.dirname(arg.selectfile))

	targets = arg.targets or ['.']
	target = targets[0]
	if arg.targets:
		if target.startswith('file://'):
			target = target[7:]
		if not os.access(target, os.F_OK):
			print("File or directory doesn't exist: %s" % target)
			return 1
		elif os.path.isfile(target):
			def print_function(string):
				print(string)
			from ranger.ext.rifle import Rifle
			fm = FM()
			if not arg.clean and os.path.isfile(fm.confpath('rifle.conf')):
				rifleconf = fm.confpath('rifle.conf')
			else:
				rifleconf = fm.relpath('config/rifle.conf')
			rifle = Rifle(rifleconf)
			rifle.reload_config()
			rifle.execute(targets, number=ranger.arg.mode, flags=ranger.arg.flags)
			return 1 if arg.fail_unless_cd else 0

	crash_traceback = None
	try:
		# Initialize objects
		from ranger.core.environment import Environment
		fm = FM()
		FileManagerAware.fm = fm
		EnvironmentAware.env = Environment(target)
		fm.tabs = dict((n+1, os.path.abspath(path)) for n, path \
				in enumerate(targets[:9]))
		load_settings(fm, arg.clean)

		if arg.list_unused_keys:
			from ranger.ext.keybinding_parser import (special_keys,
					reversed_special_keys)
			maps = fm.ui.keymaps['browser']
			for key in sorted(special_keys.values(), key=lambda x: str(x)):
				if key not in maps:
					print("<%s>" % reversed_special_keys[key])
			for key in range(33, 127):
				if key not in maps:
					print(chr(key))
			return 1 if arg.fail_unless_cd else 0

		if fm.env.username == 'root':
			fm.settings.preview_files = False
			fm.settings.use_preview_script = False
		if not arg.debug:
			from ranger.ext import curses_interrupt_handler
			curses_interrupt_handler.install_interrupt_handler()

		if arg.selectfile:
			fm.select_file(arg.selectfile)

		# Run the file manager
		fm.initialize()
		fm.ui.initialize()

		if arg.cmd:
			for command in arg.cmd:
				fm.execute_console(command)

		if ranger.arg.profile:
			import cProfile
			import pstats
			profile = None
			ranger.__fm = fm
			cProfile.run('ranger.__fm.loop()', '/tmp/ranger_profile')
			profile = pstats.Stats('/tmp/ranger_profile', stream=sys.stderr)
		else:
			fm.loop()
	except Exception:
		import traceback
		crash_traceback = traceback.format_exc()
	except SystemExit as error:
		return error.args[0]
	finally:
		if crash_traceback:
			try:
				filepath = fm.env.cf.path if fm.env.cf else "None"
			except:
				filepath = "None"
		try:
			fm.ui.destroy()
		except (AttributeError, NameError):
			pass
		if ranger.arg.profile and profile:
			profile.strip_dirs().sort_stats('cumulative').print_callees()
		if crash_traceback:
			print("ranger version: %s, executed with python %s" %
					(ranger.__version__, sys.version.split()[0]))
			print("Locale: %s" % '.'.join(str(s) for s in locale.getlocale()))
			try:
				print("Current file: %s" % filepath)
			except:
				pass
			print(crash_traceback)
			print("ranger crashed.  " \
				"Please report this traceback at:")
			print("http://savannah.nongnu.org/bugs/?group=ranger&func=additem")
			return 1
		return 0


def parse_arguments():
	"""Parse the program arguments"""
	from optparse import OptionParser
	from os.path import expanduser
	from ranger import CONFDIR, USAGE, VERSION
	from ranger.ext.openstruct import OpenStruct

	if 'XDG_CONFIG_HOME' in os.environ and os.environ['XDG_CONFIG_HOME']:
		default_confdir = os.environ['XDG_CONFIG_HOME'] + '/ranger'
	else:
		default_confdir = CONFDIR

	parser = OptionParser(usage=USAGE, version=VERSION)

	parser.add_option('-d', '--debug', action='store_true',
			help="activate debug mode")
	parser.add_option('-c', '--clean', action='store_true',
			help="don't touch/require any config files. ")
	parser.add_option('--copy-config', type='string', metavar='which',
			help="copy the default configs to the local config directory. "
			"Possible values: all, rc, rifle, commands, options, scope")
	parser.add_option('--fail-unless-cd', action='store_true',
			help="experimental: return the exit code 1 if ranger is" \
					"used to run a file (with `ranger filename`)")
	parser.add_option('-r', '--confdir', type='string',
			metavar='dir', default=default_confdir,
			help="the configuration directory. (%default)")
	parser.add_option('-m', '--mode', type='int', default=0, metavar='n',
			help="if a filename is supplied, run it with this mode")
	parser.add_option('-f', '--flags', type='string', default='',
			metavar='string',
			help="if a filename is supplied, run it with these flags.")
	parser.add_option('--choosefile', type='string', metavar='TARGET',
			help="Makes ranger act like a file chooser. When opening "
			"a file, it will quit and write the name of the selected "
			"file to TARGET.")
	parser.add_option('--choosefiles', type='string', metavar='TARGET',
			help="Makes ranger act like a file chooser for multiple files "
			"at once. When opening a file, it will quit and write the name "
			"of all selected files to TARGET.")
	parser.add_option('--choosedir', type='string', metavar='TARGET',
			help="Makes ranger act like a directory chooser. When ranger quits"
			", it will write the name of the last visited directory to TARGET")
	parser.add_option('--list-unused-keys', action='store_true',
			help="List common keys which are not bound to any action.")
	parser.add_option('--selectfile', type='string', metavar='filepath',
			help="Open ranger with supplied file selected.")
	parser.add_option('--list-tagged-files', type='string', default=None,
			metavar='tag',
			help="List all files which are tagged with the given tag, default: *")
	parser.add_option('--profile', action='store_true',
			help="Print statistics of CPU usage on exit.")
	parser.add_option('--cmd', action='append', type='string', metavar='COMMAND',
			help="Execute COMMAND after the configuration has been read. "
			"Use this option multiple times to run multiple commands.")

	options, positional = parser.parse_args()
	arg = OpenStruct(options.__dict__, targets=positional)
	arg.confdir = expanduser(arg.confdir)

	return arg


def load_settings(fm, clean):
	from ranger.core.actions import Actions
	import ranger.core.shared
	import ranger.api.commands
	from ranger.config import commands

	# Load default commands
	fm.commands = ranger.api.commands.CommandContainer()
	exclude = ['settings']
	include = [name for name in dir(Actions) if name not in exclude]
	fm.commands.load_commands_from_object(fm, include)
	fm.commands.load_commands_from_module(commands)

	if not clean:
		allow_access_to_confdir(ranger.arg.confdir, True)

		# Load custom commands
		try:
			import commands
			fm.commands.load_commands_from_module(commands)
		except ImportError:
			pass

		# Load rc.conf
		custom_conf = fm.confpath('rc.conf')
		default_conf = fm.relpath('config', 'rc.conf')
		load_default_rc = fm.settings.load_default_rc

		if load_default_rc:
			fm.source(default_conf)
		if os.access(custom_conf, os.R_OK):
			fm.source(custom_conf)

		# XXX Load plugins (experimental)
		try:
			plugindir = fm.confpath('plugins')
			plugins = [p[:-3] for p in os.listdir(plugindir) \
					if p.endswith('.py') and not p.startswith('_')]
		except:
			pass
		else:
			if not os.path.exists(fm.confpath('plugins', '__init__.py')):
				f = open(fm.confpath('plugins', '__init__.py'), 'w')
				f.close()

			ranger.fm = fm
			for plugin in sorted(plugins):
				try:
					module = __import__('plugins', fromlist=[plugin])
					fm.log.append("Loaded plugin '%s'." % module)
				except Exception as e:
					fm.log.append("Error in plugin '%s'" % plugin)
					import traceback
					for line in traceback.format_exception_only(type(e), e):
						fm.log.append(line)
			ranger.fm = None

		allow_access_to_confdir(ranger.arg.confdir, False)
	else:
		fm.source(fm.relpath('config', 'rc.conf'))


def allow_access_to_confdir(confdir, allow):
	import sys
	from errno import EEXIST

	if allow:
		try:
			os.makedirs(confdir)
		except OSError as err:
			if err.errno != EEXIST:  # EEXIST means it already exists
				print("This configuration directory could not be created:")
				print(confdir)
				print("To run ranger without the need for configuration")
				print("files, use the --clean option.")
				raise SystemExit()
		if not confdir in sys.path:
			sys.path[0:0] = [confdir]
	else:
		if sys.path[0] == confdir:
			del sys.path[0]
