import sublime
import sublime_plugin
import os, os.path
import re
import functools
import time

rails_root_cache = {}

pattern = r"(?P<file>.*):(?P<line>\d+)"

def do_when(conditional, callback, *args, **kwargs):
    if conditional():
        return callback(*args, **kwargs)
    sublime.set_timeout(functools.partial(do_when, conditional, callback, *args, **kwargs), 50)

def rails_root(directory):
    global rails_root_cache

    retval = False
    leaf_dir = directory

    if leaf_dir in rails_root_cache and rails_root_cache[leaf_dir]['expires'] > time.time():
        return rails_root_cache[leaf_dir]['retval']

    while directory:
        if os.path.exists(os.path.join(directory, 'Guardfile')):
            retval = directory
            break
        parent = os.path.realpath(os.path.join(directory, os.path.pardir))
        if parent == directory:
            # /.. == /
            retval = False
            break
        directory = parent

    rails_root_cache[leaf_dir] = {
        'retval': retval,
        'expires': time.time() + 5
    }

    return retval

class RspecOpenFailuresCommand(sublime_plugin.WindowCommand):
    def run(self):
        # get rails root
        # open tmp/rspec_guard_result
        root_dir = rails_root(self.get_working_dir())

        if not root_dir:
            sublime.error_message("This doesn't look like a rails app")
            return

        # put each line inside the quick_panel to select from
        try:
            filepath = os.path.join(root_dir, "tmp", "rspec_guard_result")
            f = open(filepath)
            self.failures = []
            patt = re.compile(pattern)
            for linenum, line in enumerate(f):
                self.failures.append(line)
            self.window.show_quick_panel(self.failures, self.panel_done, sublime.MONOSPACE_FONT)

        except IOError:
            sublime.error_message("The file `rspec_guard_result` could not be found.\nEither you haven't run your specs through guard, or you are lucky and there were no errors!")
            f = None
        finally:
            if f is not None:
                f.close()

    def panel_done(self, picked):
        if 0 > picked < len(self.failures):
            return

        picked_file = self.failures[picked][2:]
        mo = re.match(pattern, picked_file)
        if mo:
            root = rails_root(self.get_working_dir())
            file_name = os.path.join(root, mo.groupdict()["file"])
            line_num  = mo.groupdict()["line"]
            new_view = self.window.open_file(file_name)
            do_when(lambda: not new_view.is_loading(), lambda: new_view.run_command("goto_line", {"line": line_num}))

    # If there is a file in the active view use that file's directory to
    # search for the Guardfile.  Otherwise, use the only folder that is
    # open.
    def get_working_dir(self):
        file_name = self._active_file_name()
        if file_name:
            return os.path.realpath(os.path.dirname(file_name))
        else:
            try:  # handle case with no open folder
                return self.window.folders()[0]
            except IndexError:
                return ''

    def active_view(self):
        return self.window.active_view()

    def _active_file_name(self):
        view = self.active_view()
        if view and view.file_name() and len(view.file_name()) > 0:
            return view.file_name()
