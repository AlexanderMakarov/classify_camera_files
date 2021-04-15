import logging
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import filedialog
from types import FunctionType
from functools import partial
from localization import t, add_translation
import threading

# UI to show classifier activity and ask details based on Tkinter and
# https://stackoverflow.com/questions/13318742/python-logging-to-tkinter-text-widget


class WidgetLogger(logging.Handler):
    def __init__(self, widget: tk.Widget):
        logging.Handler.__init__(self)
        self.widget = widget
        self.widget.config(state='disabled')
        self.widget.tag_config("DEBUG", foreground="grey")
        self.widget.tag_config("INFO", foreground="black")
        self.widget.tag_config("WARNING", foreground="orange")
        self.widget.tag_config("WARN", foreground="orange")
        self.widget.tag_config("ERROR", foreground="red")
        self.widget.tag_config("CRITICAL", foreground="red", underline=1)

    def emit(self, record):
        self.widget.config(state='normal')
        self.widget.insert(tk.INSERT, self.format(record) + '\n', record.levelname)
        self.widget.see(tk.END)  # Scroll to the bottom.
        # self.widget.config(state='disabled') 
        self.widget.update() # Refresh the widget


class LogScrolledText(ScrolledText):
    def __init__(self, root, **kw):
        ScrolledText.__init__(self, root, **kw)
        self.configure(font='TkFixedFont')
        self.bind('<Control-c>', self.copy)

    def copy(self, event=None):
        self.clipboard_clear()
        text = self.get("sel.first", "sel.last")
        self.clipboard_append(text)

class ClassifierUI():
    def __init__(self):
        add_translation('Camera files classifier by Alexander Makarov',
                        'Классификатор фото/видео от Александра Макарова', locale='ru')
        add_translation('Browse', 'Выбрать', locale='ru')
        add_translation('Source folder:', 'Из папки:', locale='ru')
        add_translation('Target folder:', 'В папку:', locale='ru')
        add_translation('Specify folder with camera files',
                        'Укажите папку с файлами фотоаппарата', locale='ru')
        add_translation("Specify folder copy/move files into", "Укажите папку куда переместить/копировать файлы",
                        locale='ru')
        add_translation('Is replace target', 'Перезаписать', locale='ru')
        add_translation('Analyze and Copy', 'Анализ и копировать', locale='ru')
        add_translation('Analyze and Move', 'Анализ и переместить', locale='ru')
        add_translation('Analyze Only', 'Анализ только', locale='ru')
        add_translation('Classifier error: %{error}', 'Ошибка классификатора: %{error}', locale='ru')
        self.root = tk.Tk()
        self.root.title(t('Camera files classifier by Alexander Makarov'))
        # Control frame at top.
        self.control_frame = tk.Frame(self.root)
        # 1 row to choose source folder.
        self.source_folder_label = tk.Label(
            self.control_frame,
            text=t('Source folder:')
        )
        self.source_folder = tk.StringVar()
        self.source_folder_entry = tk.Entry(
            self.control_frame,
            textvariable=self.source_folder,
        )
        self.source_folder_button = tk.Button(
            self.control_frame,
            text=t('Browse'),
            command=partial(self.ask_folder, t('Specify folder with camera files'), self.source_folder),
        )
        # 2 row to choose target folder.
        self.target_folder_label = tk.Label(
            self.control_frame,
            text=t('Target folder:')
        )
        self.target_folder = tk.StringVar()
        self.target_folder_entry = tk.Entry(
            self.control_frame,
            textvariable=self.target_folder,
        )
        self.target_folder_button = tk.Button(
            self.control_frame,
            text=t('Browse'),
            command=partial(self.ask_folder, t('Specify folder copy/move files into'), self.target_folder),
        )
        # 3 row with extra settings.
        self.is_replace_label = tk.Label(
            self.control_frame,
            text=t('Is replace target')
        )
        self.is_replace = tk.IntVar()
        self.is_replace_check = tk.Checkbutton(
            self.control_frame,
            variable=self.is_replace,
            onvalue=1, offvalue=0
        )
        # 4 row with action buttons.
        self.analyze_and_copy_button = tk.Button(
            self.control_frame,
            text=t('Analyze and Copy'),
        )
        self.analyze_and_move_button = tk.Button(
            self.control_frame,
            text=t('Analyze and Move'),
        )
        self.analyze_button = tk.Button(
            self.control_frame,
            text=t('Analyze Only'),
        )
        # Put controls on grid.
        row=0
        self.source_folder_label.grid(
            row=row, column=0, sticky=tk.E
        )
        self.source_folder_entry.grid(
            row=row, column=1, sticky=tk.EW
        )
        self.source_folder_button.grid(
            row=row, column=2
        )
        row=1
        self.target_folder_label.grid(
            row=row, column=0, sticky=tk.E
        )
        self.target_folder_entry.grid(
            row=row, column=1, sticky=tk.EW
        )
        self.target_folder_button.grid(
            row=row, column=2
        )
        row=2
        self.is_replace_label.grid(
            row=row, column=0, sticky=tk.E
        )
        self.is_replace_check.grid(
            row=row, column=1, sticky=tk.W
        )
        row=3
        self.analyze_and_copy_button.grid(
            row=row, column=0, sticky=tk.EW
        )
        self.analyze_and_move_button.grid(
            row=row, column=1, sticky=tk.W
        )
        self.analyze_button.grid(
            row=row, column=2, sticky=tk.E
        )
        # Put control frame on grid.
        self.control_frame.grid(
            row=0, column=0, sticky=tk.W+tk.N+tk.E
        )
        self.control_frame.columnconfigure(1, weight=10)  # Middle column expand to fill window.
        # Add text widget to display logging info under control frame. Put on grid.
        self.log_view = LogScrolledText(self.root)
        self.log_view.grid(
            row=1, column=0, sticky=tk.NSEW
        )
        # Full the whole window with both top widgets on horizontal, expand log view on vertical.
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

    def ask_folder(self, dialog_title: str, variable: tk.StringVar):
        folder = filedialog.askdirectory(title=dialog_title)
        if folder:
            variable.set(folder)

    def _configure_and_run(self, classifier, command: FunctionType, force_verbose=False):
        if force_verbose:
            verbose = classifier.settings.get('verbose')
            classifier.settings['verbose'] = True
        classifier.settings['source_folder'] = self.source_folder.get()
        classifier.settings['target_folder'] = self.target_folder.get()
        classifier.settings['is_replace_target'] = True if self.is_replace.get() == 1 else False

        # Run command in separate thread to don't freeze UI.
        try:
            threading.Thread(target=command()).start()
        except Exception as e:
            classifier.logger.error(t('Classifier error: %{error}', error=e), exc_info=True)

        # Restore 'verbose' setting for classifier.
        if force_verbose:
            classifier.settings['verbose'] = verbose

    def run_mainloop(self, classifier):
        # Fill UI variables with classifier settings.
        self.source_folder.set(classifier.settings['source_folder'])
        self.target_folder.set(classifier.settings['target_folder'])
        self.is_replace.set(1 if classifier.settings['is_replace_target'] else 0)
        # Bind classifier logs output to 'log_view'.
        classifier.logger.addHandler(WidgetLogger(self.log_view))
        # Assign buttons to classifier actions.
        self.analyze_and_copy_button.configure(
            command=partial(self._configure_and_run, classifier, classifier.analyze_all_and_copy))
        self.analyze_and_move_button.configure(
            command=partial(self._configure_and_run, classifier, classifier.analyze_all_and_move))
        self.analyze_button.configure(
            command=partial(self._configure_and_run, classifier, classifier.analyze_all, True))
        self.root.mainloop()
