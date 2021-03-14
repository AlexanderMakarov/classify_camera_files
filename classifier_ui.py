import logging
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter.filedialog import askdirectory
from types import FunctionType
from functools import partial
from localization import t, add_translation

# UI to show classifier activity and ask details based on Tkinter and
# https://stackoverflow.com/questions/13318742/python-logging-to-tkinter-text-widget


class WidgetLogger(logging.Handler):
    def __init__(self, widget: tk.Widget):
        logging.Handler.__init__(self)
        self.widget = widget
        self.widget.config(state='disabled')
        self.widget.tag_config("INFO", foreground="black")
        self.widget.tag_config("DEBUG", foreground="grey")
        self.widget.tag_config("WARNING", foreground="orange")
        self.widget.tag_config("WARN", foreground="orange")
        self.widget.tag_config("ERROR", foreground="red")
        self.widget.tag_config("CRITICAL", foreground="red", underline=1)

    def emit(self, record):
        self.widget.config(state='normal')
        self.widget.insert(tk.INSERT, self.format(record) + '\n', record.levelname)
        self.widget.see(tk.END)  # Scroll to the bottom.
        self.widget.config(state='disabled') 
        self.widget.update() # Refresh the widget

class ClassifierUI():
    def __init__(self) -> None:
        add_translation('Camera files classifier by Alexander Makarov.',
                        'Классификатор фото/видео от Александра Макарова.', locale='ru')
        add_translation('Browse', 'Выбрать', locale='ru')
        add_translation('Source folder:', 'Из папки:', locale='ru')
        add_translation('Target folder:', 'В папку:', locale='ru')
        add_translation('Specify folder with camera files',
                        'Укажите папку с файлами фотоаппарата', locale='ru')
        add_translation("Specify folder copy/move files into", "Укажите папку куда переместить/копировать файлы",
                        locale='ru')
        add_translation('Analyze and Copy', 'Анализ и копировать', locale='ru')
        self.root = tk.Tk()
        self.root.title = t('Camera files classifier by Alexander Makarov.')
        self.root.option_add('*tearOff', 'FALSE')  # TODO why?
        # Control frame at top.
        self.control_frame = tk.Frame(self.root)
        # First row to choose source folder.
        self.row1_frame = tk.Frame(self.control_frame)
        self.source_folder_label = tk.Label(self.row1_frame, text=t('Source folder:'))
        self.source_folder = tk.StringVar()
        self.source_folder_entry = tk.Entry(
            self.row1_frame,
            textvariable=self.source_folder,
        )
        self.source_folder_button = tk.Button(
            self.row1_frame,
            text=t('Browse'),
            width=100,
            command=partial(self.ask_folder, t('Specify folder with camera files')),
        )
        self.source_folder_label.grid(sticky=tk.N)
        self.source_folder_entry.grid(fill=tk.X)
        self.source_folder_button.grid(anchor=tk.E)
        self.row1_frame.grid(side=tk.TOP, fill=tk.X)
        # TODO Second row to choose target folder.
        # Third row with TODO
        self.row3_frame = tk.Frame(self.control_frame)
        self.analyze_and_copy_button = tk.Button(
            self.row3_frame,
            text=t('Analyze and Copy'),
        )
        self.control_frame.pack(fill=tk.X)

        # Add text widget to display logging info
        self.log_view = ScrolledText(self.root, state='disabled')
        self.log_view.configure(font='TkFixedFont')
        self.log_view.pack(side=tk.BOTTOM, fill=tk.BOTH)

    def ask_folder(self, dialog_title: str):
        # self.root.withdraw()
        return askdirectory(title=dialog_title)

    def _configure_and_run(self, classifier, command: FunctionType):
        classifier.settings['source_folder'] = self.source_folder.get()
        command()

    def run_mainloop(self, classifier):
        # Fill UI variables with classifier settings.
        self.source_folder.set(classifier.settings['source_folder'])
        # self.target_folder.set(classifier.target_folder)
        # Bind classifier logs output to 'log_view'.
        classifier.logger.addHandler(WidgetLogger(self.log_view))
        # Assign buttons to classifier actions.
        self.analyze_and_copy_button.configure(
            command=partial(self._configure_and_run, classifier, classifier.analyze_all_and_copy))
        self.root.mainloop()
