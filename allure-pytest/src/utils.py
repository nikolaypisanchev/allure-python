# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import six
import pytest
from itertools import chain, islice
from allure_commons.utils import represent
from allure_commons.utils import format_exception, format_traceback, escape_non_unicode_symbols
from allure_commons.model2 import Status
from allure_commons.model2 import StatusDetails
from allure_commons.types import LabelType


ALLURE_DISPLAY_NAME_MARK = 'allure_display_name'
ALLURE_DESCRIPTION_MARK = 'allure_description'
ALLURE_DESCRIPTION_HTML_MARK = 'allure_description_html'
ALLURE_LABEL_MARK = 'allure_label'
ALLURE_LINK_MARK = 'allure_link'
ALLURE_UNIQUE_LABELS = [
    LabelType.SEVERITY,
    LabelType.FRAMEWORK,
    LabelType.HOST,
    LabelType.SUITE,
    LabelType.PARENT_SUITE,
    LabelType.SUB_SUITE
]


def get_marker_value(item, keyword):
    marker = item.get_closest_marker(keyword)
    return marker.args[0] if marker and marker.args else None


def allure_title(item):
    return get_marker_value(item, ALLURE_DISPLAY_NAME_MARK)


def allure_description(item):
    description = get_marker_value(item, ALLURE_DESCRIPTION_MARK)
    if description:
        return description
    elif hasattr(item, 'function'):
        return item.function.__doc__


def allure_description_html(item):
    return get_marker_value(item, ALLURE_DESCRIPTION_HTML_MARK)


def allure_label(item, label):
    labels = []
    for mark in item.iter_markers(name=ALLURE_LABEL_MARK):
        if mark.kwargs.get("label_type") == label:
            labels.extend(mark.args)
    return labels


def allure_labels(item):
    unique_labels = dict()
    labels = set()
    for mark in item.iter_markers(name=ALLURE_LABEL_MARK):
        label_type = mark.kwargs["label_type"]
        if label_type in ALLURE_UNIQUE_LABELS:
            if label_type not in unique_labels.keys():
                unique_labels[label_type] = mark.args[0]
        else:
            for arg in mark.args:
                labels.add((label_type, arg))
    for k, v in unique_labels.items():
        labels.add((k, v))
    return labels


def allure_links(item):
    for mark in item.iter_markers(name=ALLURE_LINK_MARK):
        yield (mark.kwargs["link_type"], mark.args[0], mark.kwargs["name"])


def pytest_markers(item):
    for keyword in item.keywords.keys():
        if any([keyword.startswith('allure_'), keyword == 'parametrize']):
            continue
        marker = item.get_closest_marker(keyword)
        if marker is None:
            continue

        yield mark_to_str(marker)


def mark_to_str(marker):
    args = [represent(arg) for arg in marker.args]
    kwargs = ['{name}={value}'.format(name=key, value=represent(marker.kwargs[key])) for key in marker.kwargs]
    if marker.name in ('filterwarnings', 'skip', 'skipif', 'xfail', 'usefixtures', 'tryfirst', 'trylast'):
        markstr = '@pytest.mark.{name}'.format(name=marker.name)
    else:
        markstr = '{name}'.format(name=marker.name)
    if args or kwargs:
        parameters = ', '.join(args + kwargs)
        markstr = '{}({})'.format(markstr, parameters)
    return markstr


def allure_package(item):
    parts = item.nodeid.split('::')
    path = parts[0].rsplit('.', 1)[0]
    return path.replace('/', '.')


def allure_name(item, parameters):
    name = escape_name(item.name)
    title = allure_title(item)
    return title.format(**{**parameters, **item.funcargs}) if title else name


def allure_full_name(item):
    parts = item.nodeid.split('::')
    package = allure_package(item)
    clazz = '.{clazz}'.format(clazz=parts[1]) if len(parts) > 2 else ''
    test_with_params = parts[-1]
    test = test_with_params.rsplit("[", 1)[0]
    full_name = '{package}{clazz}#{test}'.format(package=package, clazz=clazz, test=test)
    return escape_name(full_name)


def allure_suite_labels(item):
    head, possibly_clazz, tail = islice(chain(item.nodeid.split('::'), [None], [None]), 3)
    clazz = possibly_clazz if tail else None
    file_name, path = islice(chain(reversed(head.rsplit('/', 1)), [None]), 2)
    module = file_name.split('.')[0]
    package = path.replace('/', '.') if path else None
    pairs = dict(zip([LabelType.PARENT_SUITE, LabelType.SUITE, LabelType.SUB_SUITE], [package, module, clazz]))
    labels = dict(allure_labels(item))
    default_suite_labels = []
    for label, value in pairs.items():
        if label not in labels.keys() and value:
            default_suite_labels.append((label, value))

    return default_suite_labels


def escape_name(name):
    if six.PY2:
        try:
            name.decode('string_escape').encode('unicode_escape')
        except UnicodeDecodeError:
            return name.decode('string_escape').decode('utf-8')
    return name.encode('ascii', 'backslashreplace').decode('unicode_escape')


def get_outcome_status(outcome):
    _, exception, _ = outcome.excinfo or (None, None, None)
    return get_status(exception)


def get_outcome_status_details(outcome):
    exception_type, exception, exception_traceback = outcome.excinfo or (None, None, None)
    return get_status_details(exception_type, exception, exception_traceback)


def get_status(exception):
    if exception:
        if isinstance(exception, AssertionError) or isinstance(exception, pytest.fail.Exception):
            return Status.FAILED
        elif isinstance(exception, pytest.skip.Exception):
            return Status.SKIPPED
        return Status.BROKEN
    else:
        return Status.PASSED


def get_status_details(exception_type, exception, exception_traceback):
    message = escape_non_unicode_symbols(format_exception(exception_type, exception))
    trace = escape_non_unicode_symbols(format_traceback(exception_traceback))
    return StatusDetails(message=message, trace=trace) if message or trace else None


def get_pytest_report_status(pytest_report):
    pytest_statuses = ('failed', 'passed', 'skipped')
    statuses = (Status.FAILED, Status.PASSED, Status.SKIPPED)
    for pytest_status, status in zip(pytest_statuses, statuses):
        if getattr(pytest_report, pytest_status):
            return status
