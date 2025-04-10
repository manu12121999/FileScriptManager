import gi
import json
import os
from pathlib import Path
import subprocess


gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango


CONFIG_PATH = Path.home() / ".local/share/script_manager/file_actions.json"
PYTHON_DIR = Path.home() / ".local/share/script_manager/python_scripts"
SCRIPTS_DIR = Path.home() / ".local/share/nautilus/scripts"

DEFAULT_ACTIONS = {
    "bash":
        [
            {
                "name": "Demo",
                "filetypes": "*.*",
                "run_in_terminal": True,
                "command": 'echo print filename:"$f" print directory "$d", print basename: "$b", print basename w/o ext: "${b_noext}"',
            },
            {
                "name": "Compress MP4",
                "filetypes": "*.mp4",
                "run_in_terminal": True,
                "command": 'ffmpeg -i "$f" -vcodec libx264 -crf 28 "$d/${b_noext}_compressed.mp4"',  
            },
            {
                "name": "Convert to MP4",
                "filetypes": "*.webm",
                "run_in_terminal": True,
                "command": 'ffmpeg -i "$f" -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -c:a aac "$d/${b_noext}.mp4"',
            },
            {
                "name": "PNG to JPG",
                "filetypes": "*.png",
                "run_in_terminal": False,
                "command": 'mogrify -format jpg "$f" ',
            }
        ],
    "python":
        [
            {
                "name": "Demo",
                "filetypes": "*",
                "run_in_terminal": True,
                "filepath": ""
            },
        ]
    }

default_python_script="""# this is a simple template
import sys
import time
FILENAME, DIRNAME, BASENAME = sys.argv[1:4]
print("filename:", FILENAME)

time.sleep(2)
"""

deleted_scripts = []

def load_actions():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return DEFAULT_ACTIONS.copy()

def save_actions(actions, python_scripts):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "w") as f:
        json.dump({"bash": actions, "python": python_scripts}, f, indent=2)

    for file in deleted_scripts:
        try:
            Path(SCRIPTS_DIR, file).unlink()
        except FileNotFoundError:
            pass

    for action in actions:
        script_path = SCRIPTS_DIR / f"{action['name']}"
        with open(script_path, "w") as f:
            f.write(generate_script(action["command"], action["run_in_terminal"]))
        os.chmod(script_path, 0o755)

    for py in python_scripts:
        python_script_path = PYTHON_DIR / f"{py['name'].replace(' ', '')}.py"
        bash_script_path = SCRIPTS_DIR / f"py {py['name'].replace('_', ' ')}"
        with open(python_script_path, "w") as f:
            f.write(default_python_script)
        with open(bash_script_path, "w") as f:
            python_calling_script=generate_script(f'python3 {str(python_script_path)} "$f" "$d" "$b" ', py["run_in_terminal"])
            f.write(python_calling_script)
            #f.write(f"#!/bin/bash\ngnome-terminal -- bash -c \"python3 {str(python_script_path)} \\\"$@\\\"\" -- \"$@\"")
        os.chmod(bash_script_path, 0o755)

def generate_script(command_template, run_in_terminal):
    if run_in_terminal:
        command = (
            'gnome-terminal -- bash -c "'
            'f=\\"$1\\"; d=\\"$2\\"; b=\\"$3\\"; b_noext=\\"$4\\"; '
            + command_template.replace('"', '\\"') +
            '; echo Done.; sleep 5" _ "$f" "$d" "$b" "$b_noext"'
        )
    else:
        command = command_template

    return f"""#!/bin/bash
for f in "$@"; do
  f="$(realpath "$f")"
  d="$(dirname "$f")"
  b="$(basename "$f")"
  b_noext="${{b%.*}}"
  {command}
done
"""


class FileActionsApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="File Actions")
        self.selection="bash"

        self.set_default_size(1100, 500)
        self.set_border_width(10)
        
        all_actions = load_actions()
        self.bash_actions = all_actions["bash"]
        self.python_actions = all_actions["python"]


        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)
        
        ##########################################
        ##########  First Scrollbox  #############
        ##########################################

        # Title
        bash_title = Gtk.Label(label="Bash Actions")
        vbox.pack_start(bash_title, False, False, 0)

        # Bash Script TreeView
        self.store = Gtk.ListStore(str, str, bool, str) # name, filetypes, run_in_terminal, command
        for action in self.bash_actions:
            self.store.append([action["name"], action["filetypes"], action["run_in_terminal"], action["command"]])

        self.treeview = Gtk.TreeView(model=self.store)
        self.treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.treeview.get_selection().connect("changed", self.on_bash_selection_changed)


        
        # NAME AND FILETYPES
        for i, column_title in enumerate(["Name", "Filetypes"]):
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", True)
            renderer.connect("edited", self.on_cell_edited, i)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.treeview.append_column(column)


        # RUN IN TERMINAL COLUMN
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.set_property("activatable", True)
        renderer_toggle.connect("toggled", self.on_checkbox_toggled)
        column_toggle = Gtk.TreeViewColumn("Run in Terminal", renderer_toggle, active=2)
        self.treeview.append_column(column_toggle)

        # COMMAND COLUMN
        renderer = Gtk.CellRendererText()
        renderer.set_property("editable", True)
        renderer.connect("edited", self.on_cell_edited, 3)
        column = Gtk.TreeViewColumn("Command", renderer, text=3)
        self.treeview.append_column(column)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.add(self.treeview)
        vbox.pack_start(scrolled, True, True, 0)
        
        ##########################################
        ##########  Second Scrollbox  ############
        ##########################################

        # Title
        python_title = Gtk.Label(label="Python Actions")
        vbox.pack_start(python_title, False, False, 0)

        # Python Script TreeView
        self.python_store = Gtk.ListStore(str, str, bool) # name, filetypes, run_in_terminal
        for action in self.python_actions:
            self.python_store.append([action["name"], action["filetypes"], action["run_in_terminal"]])

        self.python_treeview = Gtk.TreeView(model=self.python_store)
        self.python_treeview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.python_treeview.get_selection().connect("changed", self.on_python_selection_changed)


        # NAME and FILETYPES columns
        for i, column_title in enumerate(["Name", "Filetypes"]):
            renderer = Gtk.CellRendererText()
            renderer.set_property("editable", True)
            renderer.connect("edited", self.on_python_cell_edited, i)
            column = Gtk.TreeViewColumn(column_title, renderer, text=i)
            self.python_treeview.append_column(column)

        # RUN IN TERMINAL column
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.set_property("activatable", True)
        renderer_toggle.connect("toggled", self.on_python_checkbox_toggled)
        column_toggle = Gtk.TreeViewColumn("Run in Terminal", renderer_toggle, active=2)
        self.python_treeview.append_column(column_toggle)

	    # FILEPATH OPEN BUTTON column
        button_column = Gtk.TreeViewColumn("Open")
        button_renderer = Gtk.CellRendererText()
        button_column.pack_start(button_renderer, True)
        button_column.set_cell_data_func(button_renderer, self.render_open_button)
        self.python_treeview.append_column(button_column)

        self.python_treeview.connect("row-activated", self.on_python_open_clicked)

        scrolled2 = Gtk.ScrolledWindow()
        scrolled2.set_vexpand(True)
        scrolled2.add(self.python_treeview)
        vbox.pack_start(scrolled2, True, True, 0)
        
        ##########################################
        ##########  Buttons  ############
        ##########################################

        # Buttons
        button_box = Gtk.Box(spacing=6)
        add_btn = Gtk.Button(label="Add sh command")
        add_btn.connect("clicked", self.add_action)
        button_box.pack_start(add_btn, False, False, 0)
        
        add_py_btn = Gtk.Button(label="Add python script")
        add_py_btn.connect("clicked", self.add_python_action)
        button_box.pack_start(add_py_btn, False, False, 0)
        
        delete_btn = Gtk.Button(label="Delete Selected Action")
        delete_btn.connect("clicked", self.delete_action)
        button_box.pack_start(delete_btn, False, False, 0)

        save_btn = Gtk.Button(label="Save")
        save_btn.connect("clicked", self.save_all)
        button_box.pack_end(save_btn, False, False, 0)

        vbox.pack_start(button_box, False, False, 0)




    # Bash callbacks
    def on_checkbox_toggled(self, renderer, path):
        active = self.store[path][2]
        self.store[path][2] = not active

    def on_cell_edited(self, widget, path, text, column):
        if column == 0: # mark old name to be removed
            global deleted_scripts
            old_name = self.store[path][column]
            deleted_scripts.append(old_name)
        self.store[path][column] = text

    def add_action(self, widget):
        self.store.append(["New Action", "*.*", False, "echo \"$f\""])

    # Python callbacks
    def on_python_checkbox_toggled(self, renderer, path):
        active = self.python_store[path][2]
        self.python_store[path][2] = not active

    def on_python_cell_edited(self, widget, path, text, column):
        self.python_store[path][column] = text

    def render_open_button(self, column, cell, model, iter, data=None):
        cell.set_property("text", "Open")
        cell.set_property("foreground", "blue")
        cell.set_property("underline", Pango.Underline.SINGLE)

    # When the "open" button of a row of python scripts is pressed 
    def on_python_open_clicked(self, treeview, path, column):
        
        selection = self.python_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            name = model[treeiter][0]
            
            script_path = PYTHON_DIR / f"{name.replace(' ', '')}.py"
            if not script_path.exists():
                with open(script_path, "w") as f:
                    f.write(default_python_script)
                os.chmod(script_path, 0o755)
            try:
                subprocess.Popen(['xdg-open', str(script_path)])
            except Exception as e:
                print(f"Failed to open file: {e}")


    def get_python_filter(self):
        file_filter = Gtk.FileFilter()
        file_filter.set_name("Python files")
        file_filter.add_pattern("*.py")
        return file_filter
    
    # add a new row to the treeview
    def add_python_action(self, widget):
        self.python_store.append(["New Script", "*.*", True])

    # makes sure to deselect other rows (rows in other treeview)
    def on_bash_selection_changed(self, selection):
        # Deselect any selected row in the Python treeview
        if self.selection!="bash":
            self.python_treeview.get_selection().unselect_all()
            self.selection="bash"
        
    # makes sure to deselect other rows (rows in other treeview)
    def on_python_selection_changed(self, selection):
        # Deselect any selected row in the Bash treeview
        if self.selection!="python":
            self.treeview.get_selection().unselect_all()
            self.selection="python"
    
    # Occurs when the button "delete row" is pressed. Removes the selected row from the treeview
    def delete_action(self, widget):
        selection = self.treeview.get_selection() if self.selection=="bash" else self.python_treeview.get_selection()
        model, treeiter = selection.get_selected()
        if treeiter is not None:
            global deleted_scripts
            deleted_name = model[treeiter][0]
            if self.selection=="python":
                deleted_name=f"py {deleted_name}"
            deleted_scripts.append(deleted_name)
            model.remove(treeiter)

    # Occurs when the save button is pressed. Saves the config as json and makes scripts
    def save_all(self, widget):
        actions = []
        for row in self.store:
            actions.append({
                "name": row[0],
                "filetypes": row[1],
                "run_in_terminal": row[2],
                "command": row[3]
            })

        python_actions = []
        for row in self.python_store:
            python_actions.append({
                "name": row[0],
                "filetypes": row[1],
                "run_in_terminal": row[2],
            })
        save_actions(actions, python_actions)

win = FileActionsApp()
win.connect("destroy", Gtk.main_quit)
win.show_all()
Gtk.main()
