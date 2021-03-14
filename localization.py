import i18n  # gettext is too complex for setup with extra files.
import locale


def t(key, **kwargs):
    """
    Modified version of 'i18n.t(key, **kwargs)' function. Differences:
    - Doesn't need in 'fallback' translation - keys are translation (like in iOS). It means that all placeholders are
    supported directly in keys. If current local is 'fallback' then key is added as value and translated as usual.
    - Doesn't try to find translation in files - everything expected to be added into 'i18n.translations.container'.
    :param key: Key to translate.
    :param kwargs: Extra parameters for translation.
    :return Localized value.
    """
    locale = kwargs.pop('locale', i18n.config.get('locale'))
    if i18n.translations.has(key, locale):
        return i18n.translator.translate(key, locale=locale, **kwargs)
    elif locale == i18n.config.get('fallback'):

        # If key not found then add it under current locale to make i18n format it.
        # By default it tries to see in filed and returns key without applying formatting.
        i18n.translations.add(key, key, locale=locale)
        return i18n.translator.translate(key, **kwargs)
    else:
        return key + " [can't translate]"


def setup_localization(lang: str = locale.getdefaultlocale()[0][0:2]):
    """
    Setups localization module.
    :param lang: Locale is simplified to language. Specify it.
    :return: Specified language.
    """
    i18n.set('locale', lang)  # Simplify locale to language.
    i18n.set('fallback', 'en')
    return lang


def add_translation(key: str, value, locale: str):
    """
    See i18n.add_translation function.
    """
    i18n.add_translation(key, value, locale)
