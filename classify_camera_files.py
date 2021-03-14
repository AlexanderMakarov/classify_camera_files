#!/usr/bin/env python3
import argparse
import os
import datetime
import csv
import sys
import logging
from typing import Any, List, Dict, Set, Callable, AnyStr, Iterable
from PIL import Image, ExifTags
import collections
import shutil
from localization import t, setup_localization, add_translation
import locale


class ClassifyCameraFiles():
    SUPPORTED_EXTENSIONS_PER_TYPE = {
        "Image": ['.jpg', '.jpeg', '.tiff'],
        "Video": ['.mov', '.mp4', '.avi', '.3gp'],
    }
    SUPPORTED_FILE_ATTRIBUTES = [
        "FileCTime",  # File creation time.
        "FileMTime"  # File modification time.
    ]
    SUPPORTED_EXIF_TAGS = [
        'DateTimeOriginal',
        'Make',
        'Model',
        'Orientation',  # https://www.impulseadventure.com/photo/exif-orientation.html
        'ExposureTime',  # https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/exposuretime.html
        'Flash',  # https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/flash.html
        # https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/scenecapturetype.html
        'SceneCaptureType',
        'LightSource',  # Rare cameras support it.
        'ISOSpeedRatings',  # https://en.wikipedia.org/wiki/Film_speed#ISO_12232
        # Mostly for smartphones and even here people prefer disable it.
        'GPSInfo',
        'DigitalZoomRatio',  # May be useful for smartphones.
        'Software',
    ]
    DEFAULT_TARGET_FOLDER = 'classified_files'
    DEFAULT_RESULTS_FILE = "classify_camera_files_analyze_results.csv"
    MIN_FOLDER_FILES_COUNT = 3
    MAX_TIME_BETWEEN_FILES_IN_FOLDER_MINUTES = 60

    def __init__(self, logger: logging.Logger, settings: Dict={}) -> None:
        self.logger = logger
        self.settings = {}
        self.settings['source_folder'] = settings.get('source_folder', os.getcwd())
        self.settings['results_file_path'] = settings.get(
            'results_file', self.DEFAULT_RESULTS_FILE)
        self.settings['target_folder'] = settings.get(
            'target_folder', os.path.join(os.getcwd(), self.DEFAULT_TARGET_FOLDER))
        self.settings['is_replace_target'] = settings.get('is_recreate_target', False)
        self.settings['min_folder_files_count'] = settings.get(
            'min_folder_files_count', self.MIN_FOLDER_FILES_COUNT)
        self.settings['max_minutes_between_files_in_folder'] = settings.get(
            'max_minutes_between_files_in_folder', self.MAX_TIME_BETWEEN_FILES_IN_FOLDER_MINUTES)
        self.settings['lang'] = settings.get('lang', 'en')
        self.settings['verbose'] = settings.get('verbose', True)

        # Each file in folder with extracted features.
        self.analyze_results: List[Dict] = []
        # List of folders to create with "from" -> "to" pathes.
        self.classified_files: Dict[AnyStr, List] = {}

        # Setup localization. Note that Russian case is played via "few".
        add_translation("No resutls to analyze, make sure that they are loaded.",
                        'Нет результатов анализа, проверьте что они загружены.', locale='ru')
        add_translation('Landscape', {
                        'one': 'Ландшафтная', 'few': 'Ландшафтная', 'many': 'Ландшафтной'}, locale='ru')
        add_translation('Portrait', {
                        'one': 'Портретная', 'few': 'Портретная', 'many': 'Портретной'}, locale='ru')
        add_translation(
            'Dark', {'one': 'Тёмный', 'few': 'Тёмных', 'many': 'Тёмные'}, locale='ru')
        add_translation(
            'Light', {'one': 'Светлый', 'few': 'Светлых', 'many': 'Светлые'}, locale='ru')
        add_translation('Unknown orientation',
                        'Неизвестная ориентация', locale='ru')
        add_translation("Looking through '%{source_folder}'...",
                        "Анализирую '%{source_folder}'...", locale='ru')
        add_translation("Analyzed %{files_number} files from '%{source_folder}' in %{duration}.",
                        "Анализировано %{files_number} файлов в '%{source_folder}' за %{duration}.", locale='ru')
        add_translation(
            "Found %{files_number} files docs with %{keys} fields in '%{file_path}'.",
            "Найдено %{files_number} описаний файлов с %{keys} полями в '%{file_path}'.",
            locale='ru'
        )
        add_translation(
            "Found nothing in '%{file_path}'.", "Ничего не найдено в %{file_path}.", locale='ru')
        add_translation(
            "Dumped %{files_number} files analyze results with %{possible_keys} columns into '%{file_path}'.",
            "Сохранено %{files_number} результатов анализа файлов с %{possible_keys} полями в '%{file_path}'",
            locale='ru'
        )
        add_translation("all %{label}", "все %{label}", locale='ru')
        add_translation("mixed %{label1} and %{label2}",
                        "смешаны %{label1} и %{label2}", locale='ru')
        add_translation("mostly %{label}", "больше %{label}", locale='ru')
        add_translation("Wrong DateTimeOriginal value in %{file_path} file: %{e}",
                        "Неверное значение DateTimeOriginal в %{file_path} файле: %{e}", locale='ru')
        add_translation(" files on ", " файлов в ", locale='ru')
        add_translation(
            "Skipping %{skipped_from_buckets_files} files as 'nothing common' in %{last_bucket_timestamp}"
            "...%{start_bucket_timestamp}",
            "Пропускаю %{skipped_from_buckets_files} файлов как 'ничего общего' в %{last_bucket_timestamp}"
            "...%{start_bucket_timestamp}",
            locale='ru'
        )
        add_translation("    Camera: %{camera_model_counter}",
                        "    Камера: %{camera_model_counter}", locale='ru')
        add_translation("    Brightness: %{brightness_counter}",
                        "    Яркость: %{brightness_counter}", locale='ru')
        add_translation("    Orientation: %{orientation_counter}",
                        "    Ориентация: %{orientation_counter}", locale='ru')
        add_translation("Total %{folders_len} folders and %{files_number} 'nothing common' files.",
                        "Итого %{folders_len} папок и %{files_number} 'ничего общего' файлов.", locale='ru')
        add_translation("Copying %{files_number} files into %{folder_name}...",
                        "Копирую %{files_number} файлов в %{folder_name}...", locale='ru')
        add_translation("Moving %{files_number} files into %{folder_name}...",
                        "Переношу %{files_number} файлов в %{folder_name}...", locale='ru')
        add_translation(
            "Created %{folders_number} folders and copied %{files_number} files into '%{folder}' in %{duration}.",
            "Создано %{folders_number} папок и скопировано %{files_number} файлов в '%{folder}' за %{duration}.",
            locale='ru'
        )
        add_translation(
            "Created %{folders_number} folders and moved %{files_number} files into '%{folder}' in %{duration}.",
            "Создано %{folders_number} папок и перенесено %{files_number} файлов в '%{folder}' за %{duration}.",
            locale='ru'
        )
        add_translation("ClassifyCameraFiles: started with settings %{settings}",
                        "ClassifyCameraFiles: запущен с настройками %{settings}", locale='ru')

    def _parse_file_metadata(self, file_path: str) -> Dict:
        return {  # Sync with SUPPORTED_FILE_ATTRIBUTES.
            "FileCTime": datetime.datetime.fromtimestamp(os.path.getctime(file_path)).replace(microsecond=0),
            "FileMTime": datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).replace(microsecond=0),
        }

    # TODO try faster? https://pypi.org/project/ExifRead/
    def _parse_exif_tags(self, file_path: str) -> Dict:
        parsed_tags = {}
        for k, v in dict(Image.open(file_path).getexif()).items():
            if k in ExifTags.TAGS:
                string_tag_name = ExifTags.TAGS[k]
                if string_tag_name in self.SUPPORTED_EXIF_TAGS:
                    parsed_tags[string_tag_name] = repr(v)
        return parsed_tags

    def _analyze(self, parsers: Dict[AnyStr, Callable]):
        start_time = datetime.datetime.now()
        self.logger.info(t("Looking through '%{source_folder}'...", source_folder=self.settings['source_folder']))
        for root, _, files in os.walk(os.path.abspath(self.settings['source_folder'])):
            for file in files:
                file_path = os.path.join(root, file)
                file_ext: str = os.path.splitext(file_path)[1]
                for type, extensions in self.SUPPORTED_EXTENSIONS_PER_TYPE.items():
                    type_parsers = parsers.get(type)
                    if type_parsers and file_ext.lower() in extensions:
                        file_features: Dict = {"Path": file_path}
                        for parser in type_parsers:
                            new_fields = parser(file_path)
                            file_features.update(new_fields)
                        if self.settings.get('verbose'):
                            self.logger.info(f"  {file_path} -> {file_features}")
                        self.analyze_results.append(file_features)
        return t("Analyzed %{files_number} files from '%{source_folder}' in %{duration}.",
                 files_number=len(self.analyze_results), source_folder=self.settings['source_folder'],
                 duration=(datetime.datetime.now() - start_time))

    def _save_results(self):
        possible_keys: Set = set()
        for result in self.analyze_results:
            possible_keys.update(list(result.keys()))
        with open(self.settings['results_file_path'], 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=possible_keys)
            writer.writeheader()
            for result in self.analyze_results:
                writer.writerow(result)
        return t("Dumped %{files_number} files analyze results with %{possible_keys} columns into '%{file_path}'.",
                 files_number=len(self.analyze_results), possible_keys=possible_keys,
                 file_path=self.settings['results_file_path'])

    def _read_results(self):
        with open(self.settings['results_file_path'], 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            self.analyze_results = [x for x in reader]
        if self.analyze_results:
            return t("Found %{files_number} files docs with %{keys} fields in '%{file_path}'.",
                     files_number=len(self.analyze_results), keys=self.analyze_results[0].keys(),
                     file_path=self.settings['results_file_path'])
        else:
            return t("Found nothing in '%{file_path}'.", file_path=self.settings['results_file_path'])

    @staticmethod
    def _choose_right_label_from_counter(counter: collections.Counter, labels: Iterable[str],
                                         fallback_label: str) -> str:
        # Build something like "all dark", "mostly dark" or "mixed dark and light".
        total = sum(counter.values())
        near_half = []
        for label in labels:
            value = counter.get(label, 0)
            if value == 0:
                continue
            ratio = value / total
            if ratio > 0.95:
                return t("all %{label}", label=t(label, count=9))
            elif ratio > 0.5:
                return t("mostly %{label}", label=t(label, count=2))
            elif 0.35 < ratio <= 0.5:
                near_half.append(label)
        if len(near_half) == 2:
            return t("mixed %{label1} and %{label2}", label1=t(near_half[0], count=2), label2=t(near_half[1], count=2))
        elif len(near_half) == 1:
            return t("mostly %{label}", label=t(near_half[0], count=9))
        return fallback_label

    def _classify(self):
        if not self.analyze_results:  # Ensure that list of results is not empty.
            raise ValueError(t("No resutls to analyze, make sure that they are loaded."))

        # Use simple time density strategy - if distance between files small then put into one folder.
        # 1: Construct new '_timestamp' feature with parsed date of file creation. Sort results by it.
        for result in self.analyze_results:
            timestamp = None
            datetime_original = result.get("DateTimeOriginal", "")
            if datetime_original:
                try:
                    timestamp = datetime.datetime.strptime(
                        datetime_original.strip("'"), "%Y:%m:%d %H:%M:%S")
                except ValueError as e:
                    self.logger.warn(t("Wrong DateTimeOriginal value in %{file_path} file: %{e}",
                                       file_path=result['Path'], e=e))

            # "FileCTime" must be specified and used as fallback value. Crash if absent or wrong format - expected.
            if not timestamp:
                timestamp = datetime.datetime.strptime(
                    result.get("FileCTime"), "%Y-%m-%d %H:%M:%S.%f")
            result['_timestamp'] = timestamp
        timestamped = sorted(self.analyze_results,
                             key=lambda x: x['_timestamp'])

        # 2: Pack results into buckets by timestamp.
        timestamp_buckets: Dict[int, List] = {}
        start_bucket_datetime = None
        current_bucket_datetime = datetime.datetime.fromtimestamp(0)
        in_folder_gap = datetime.timedelta(
            minutes=self.settings['max_minutes_between_files_in_folder'])
        for result in timestamped:
            timestamp = result['_timestamp']
            if timestamp - current_bucket_datetime > in_folder_gap:
                start_bucket_datetime = timestamp
                timestamp_buckets[start_bucket_datetime] = [result]
                current_bucket_datetime = timestamp
            else:
                timestamp_buckets[start_bucket_datetime].append(result)
                current_bucket_datetime = timestamp

        # 3: Analyze each bucket to find out sizes. Buckets with few files makes no sense.
        out_of_bucket_files = []
        last_bucket_timestamp = None
        last_out_of_bucket_size = 0
        for start_bucket_timestamp, results in timestamp_buckets.items():
            camera_model_counter = collections.Counter()
            brightness_counter = collections.Counter()
            orientation_counter = collections.Counter()
            for result in results:
                brightness = None
                orientation = None

                # Camera name.
                # For camera model just concatenate 'Make' and 'Model' EXIF tag values (if exist).
                make = result.get('Make', "").strip("'")
                model = result.get('Model', "").strip("'")
                camera_name = ""
                if make:
                    camera_name = make
                    if model:
                        camera_name += "-" + model
                elif model:
                    camera_name = model
                if camera_name:
                    result['_camera'] = camera_name
                camera_model_counter[camera_name] += 1

                # 'SceneCaptureType' EXIF tag contains weird grouped but useful values:
                # 1 = Landscape, 2 = Portrait, 3 = Night scene
                scene_capture_type = result.get('SceneCaptureType', "")
                if scene_capture_type == '1':
                    orientation = 'Landscape'
                elif scene_capture_type == '2':
                    orientation == 'Portrait'
                elif scene_capture_type == '3':
                    brightness = 'Dark'

                # Brightness.
                # Good metric of brightness is ISOSpeedRatings. 500 is a border (experimentally).
                if not brightness:
                    iso_speed_ratings = result.get('ISOSpeedRatings', "")
                    if iso_speed_ratings:
                        brightness = 'Dark' if int(iso_speed_ratings) >= 500 else 'Light'

                # If flash was used and was detected by camera sensor then it is also points on dark place.
                # See https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/exif/flash.html
                if not brightness:
                    brightness = 'Dark' if result.get('Flash', "") in ['9', '15', '25', '31'] else 'Light'
                brightness_counter[brightness] += 1

                # Orientation.
                # Simplify orientation to horisontal and vertical.
                if not orientation:
                    orientation = result.get('Orientation', "")
                    if orientation:
                        orientation = 'Landscape' if orientation in ['1', '3'] else 'Portrait'
                if not orientation:
                    orientation = 'Unknown orientation'
                else:
                    result['_orientation'] = orientation
                orientation_counter[orientation] += 1

                # Build file name.
                file_name = os.path.basename(result['Path'])
                result['_name'] = f"{result['_timestamp']} {t(brightness, count=1)} {t(orientation, count=1)}"\
                                  f" {camera_name} {file_name}"

            # Skip too small buckets.
            if len(results) < self.MIN_FOLDER_FILES_COUNT:

                # Too little files to join them into separate folder. Leave them in 'nothing common' bucket.
                out_of_bucket_files.extend(results)
                continue

            # Build folder name.
            bucket_name = f"{start_bucket_timestamp} {len(results):3}{t(' files on ')}"\
                          f"{results[-1]['_timestamp'] - start_bucket_timestamp}"
            brightness_label = self._choose_right_label_from_counter(
                brightness_counter, ('Dark', 'Light'), "")
            if brightness_label:
                bucket_name += f" {brightness_label}"
            orientation_label = self._choose_right_label_from_counter(
                orientation_counter, ('Portrait', 'Landscape'), "")
            if orientation_label:
                bucket_name += f" {orientation_label}"

            # Build (from -> to) per file in folder.
            self.classified_files[bucket_name] = [
                (x['Path'], x['_name']) for x in results]

            # Print bucket details if need.
            if self.settings.get('verbose'):
                skipped_from_buckets_files = len(
                    out_of_bucket_files) - last_out_of_bucket_size
                if skipped_from_buckets_files > 0:
                    self.logger.info(t("Skipping %{skipped_from_buckets_files} files as 'nothing common' in "
                                       "%{last_bucket_timestamp}...%{start_bucket_timestamp}",
                                       skipped_from_buckets_files=skipped_from_buckets_files,
                                       last_bucket_timestamp=last_bucket_timestamp,
                                       start_bucket_timestamp=start_bucket_timestamp))
                self.logger.info(f"{bucket_name}:\n"
                                 + t("    Camera: %{camera_model_counter}",
                                     camera_model_counter=camera_model_counter)
                                 + t("    Brightness: %{brightness_counter}",
                                     brightness_counter=brightness_counter)
                                 + t("    Orientation: %{orientation_counter}",
                                     orientation_counter=orientation_counter))

            # Update 'out of bucket' variables.
            last_bucket_timestamp = results[-1]['_timestamp']
            last_out_of_bucket_size = len(out_of_bucket_files)
        folders_len = len(self.classified_files)
        for result in out_of_bucket_files:
            self.classified_files[None] = [
                (x['Path'], x['_name']) for x in out_of_bucket_files]
        return t("Total %{folders_len} folders and %{files_number} 'nothing common' files.", folders_len=folders_len,
                 files_number=len(out_of_bucket_files))

    def _make_folder(self):
        if self.settings['is_replace_target'] and os.path.exists(self.settings['target_folder']):
            shutil.rmtree(self.settings['target_folder'])
            os.makedirs(self.settings['target_folder'])

    def _copy(self):
        created_folders = 0
        copied_files = 0
        start_date = datetime.datetime.now()
        self._make_folder()
        for folder_name, files_actions in self.classified_files.items():
            folder_path = os.path.join(
                self.settings['target_folder'], folder_name) if folder_name else self.settings['target_folder']
            if not os.path.exists(folder_path):
                os.mkdir(folder_path)
            # Yes, folder may be not created but count expected results, not actions.
            created_folders += 1
            self.logger.info(t("Copying %{files_number} files into %{folder_name}...", files_number=len(files_actions),
                    folder_name=(folder_name if folder_name else folder_path)))
            for action in files_actions:
                shutil.copyfile(action[0], os.path.join(
                    folder_path, action[1]))
                copied_files += 1
        return t("Created %{folders_number} folders and copied %{files_number} files into '%{folder}' in %{duration}.",
                 folders_number=created_folders, files_number=copied_files, folder=self.settings['target_folder'],
                 duration=(datetime.datetime.now() - start_date))

    def _move(self):
        created_folders = 0
        moved_files = 0
        start_date = datetime.datetime.now()
        self._make_folder()
        for folder_name, files_actions in self.classified_files.items():
            folder_path = os.path.join(
                self.settings['target_folder'], folder_name) if folder_name else self.settings['target_folder']
            if not os.path.exists(folder_path):
                os.mkdir(folder_path)
            # Yes, folder may be not created but count expected results, not actions.
            created_folders += 1
            self.logger.info(t("Moving %{files_number} files into %{folder_name}...", files_number=len(files_actions),
                    folder_name=(folder_name if folder_name else folder_path)))
            for action in files_actions:
                shutil.move(action[0], os.path.join(folder_path, action[1]))
                moved_files += 1
        return t("Created %{folders_number} folders and moved %{files_number} files into '%{folder}' in %{duration}.",
                 folders_number=created_folders, folder=moved_files, target_folder=self.settings['target_folder'],
                 duration=(datetime.datetime.now() - start_date))

    def analyze_all(self):
        self.logger.info("------------------------------------")
        self.logger.info(t("ClassifyCameraFiles: started with settings %{settings}", settings=self.settings))
        self.logger.info(self._analyze({
            "Image": [self._parse_file_metadata, self._parse_exif_tags],
            "Video": [self._parse_file_metadata]  # TODO parse info from video.
        }))
        self.logger.info(self._save_results())

    def classify_in_console(self):
        self.logger.info("------------------------------------")
        self.logger.info(t("ClassifyCameraFiles: started with settings %{settings}", settings=self.settings))
        self.logger.info(self._read_results())
        self.logger.info(self._classify())

    def move(self):
        self.logger.info("------------------------------------")
        self.logger.info(t("ClassifyCameraFiles: started with settings %{settings}", settings=self.settings))
        self.logger.info(self._read_results())
        self.logger.info(self._classify())
        self.logger.info(self._move())

    def copy(self):
        self.logger.info("------------------------------------")
        self.logger.info(t("ClassifyCameraFiles: started with settings %{settings}", settings=self.settings))
        self.logger.info(self._read_results())
        self.logger.info(self._classify())
        self.logger.info(self._copy())

    def analyze_all_and_copy(self):
        self.analyze_all()
        self.logger.info(self._read_results())
        self.logger.info(self._classify())
        self.logger.info(self._copy())

    def analyze_all_and_move(self):
        self.analyze_all()
        self.logger.info(self._read_results())
        self.logger.info(self._classify())
        self.logger.info(self._move())


class ReadableDirAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir = values
        if not os.path.isdir(prospective_dir):
            raise argparse.ArgumentTypeError(
                t("%{prospective_dir} is not a valid path", prospective_dir=prospective_dir))
        if os.access(prospective_dir, os.R_OK):
            setattr(namespace, self.dest, prospective_dir)
        else:
            raise argparse.ArgumentTypeError(
                t("%{prospective_dir} is not a readable path", prospective_dir=prospective_dir))


def setup_logging():
    logging.addLevelName(logging.WARNING, 'WARN')
    logging.basicConfig(level=logging.INFO, format='%(levelname)-5s: %(message)s') 
    return logging.getLogger()


if __name__ == "__main__":
    add_translation("%{prospective_dir} is not a valid path",
                    "%{prospective_dir} неправильный путь", locale='ru')
    add_translation("%{prospective_dir} is not a readable path",
                    "%{prospective_dir} недоступный путь", locale='ru')
    if len(sys.argv) == 1:  # If no arguments - run UI.
        import classifier_ui
        lang = setup_localization()
        logger = setup_logging()
        ui = classifier_ui.ClassifierUI()
        ui.run_mainloop(ClassifyCameraFiles(logger, {'verbose': False}))
    else:
        ACTIONS = {  # TODO print somehow and with localization maybe.
            'full': {
                'desc': 'Analyze by all metrics, save CSV with result, copy data.',
                'method_to_run': "analyze_all_and_copy",
            },
            'analyze-all': {
                'desc': 'Analyze by all metrics, save CSV with result.',
                'method_to_run': "analyze_all",
            },
            'move': {
                'desc': 'Read CSV with anylize result and move files.',
                'method_to_run': "move",
            },
            'copy': {
                'desc': 'Read CSV with anylize result and copy files.',
                'method_to_run': "copy",
            },
            'classify': {
                'desc': 'Read CSV with anylize result, classify and print results.',
                'method_to_run': "classify_in_console",
            },
        }
        parser = argparse.ArgumentParser(
            description='Traverse specified folder recursively, classifies files from camera (photos and videos), '
                        'moves them to new folders with names based on classses. Uses EXIF tags and creation time.'
        )
        parser.add_argument('-s', '--source-folder', dest='source_folder', action=ReadableDirAction, required=False,
                            help='Path to folder with not classified files. Will be traversed recursively.')
        parser.add_argument('-t', '--target-folder', dest='target_folder', type=str,
                            default=ClassifyCameraFiles.DEFAULT_TARGET_FOLDER,
                            help='Path to folder move/copy files into. '
                                 'Folder will be created with nested folders per class.')
        parser.add_argument('-r', '--recreate-target', dest='is_recreate_target', action='store_true',
                            help='Flag to pre-clean target folder on copy/move action.')
        parser.add_argument('-a', '--action', dest='action', choices=ACTIONS.keys(), default='full',
                            help='Action to do. By default "full" aka analyze, dump results, copy files.')
        parser.add_argument('-f', '--results-file', dest='results_file', type=str, required=False,
                            default=ClassifyCameraFiles.DEFAULT_RESULTS_FILE,
                            help='Path to CSV file save analyze results into.')
        parser.add_argument('--min-folder-files-count', dest='min_folder_files_count', type=int,
                            default=ClassifyCameraFiles.MIN_FOLDER_FILES_COUNT,
                            help='Minimal files which should have folder. '
                                'If folder appears to have less files then they go to "nothing common" folder.')
        parser.add_argument('--max-minutes-between-files-in-folder', dest='max_minutes_between_files_in_folder',
                            type=int, default=ClassifyCameraFiles.MAX_TIME_BETWEEN_FILES_IN_FOLDER_MINUTES,
                            help='Maximum time gap in minutes between filed to put them in one folder.')
        parser.add_argument('--language', dest='lang', type=str, default=locale.getdefaultlocale()[0][0:2],
                            help='Specify language for output. By default is used system locale.')
        logger = setup_logging()
        args = parser.parse_args()
        setup_localization(args.lang)
        worker = ClassifyCameraFiles(logger, vars(args))
        getattr(worker, ACTIONS[args.action]['method_to_run'])()
