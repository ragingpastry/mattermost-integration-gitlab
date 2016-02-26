#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Python Future imports
from __future__ import unicode_literals, absolute_import, print_function

# Python System imports
import re

from . import constants


def fix_gitlab_links(base_url, text):
    """
    Fixes gitlab upload links that are relative and makes them absolute
    """

    matches = re.findall(r'(\[[^]]*\]\s*\((/[^)]+)\))', text)

    for (replace_string, link) in matches:
        new_string = replace_string.replace(link, base_url + link)
        text = text.replace(replace_string, new_string)

    return text


def add_markdown_quotes(text):
    """
    Add Markdown quotes around a piece of text
    """

    if not text:
        return ''

    split_desc = text.split('\n')

    for index, line in enumerate(split_desc):
        split_desc[index] = '> ' + line

    return '\n'.join(split_desc)


class BaseEvent(object):

    def __init__(self, data):
        self.data = data
        self.object_kind = data['object_kind']

    @property
    def push_event(self):
        raise NotImplementedError

    def should_report_event(self, report_events):
        return report_events[self.object_kind]

    def format(self):
        raise NotImplementedError

    def gitlab_user_url(self, username):
        base_url = '/'.join(self.data['repository']['homepage'].split('/')[:-2])
        return '{}/u/{}'.format(base_url, username)


class PushEvent(BaseEvent):

    def format(self):

        if self.data['before'] == '0' * 40:
            description = 'the first commit'
        else:
            description = '{} commit'.format(self.data['total_commits_count'])
        if self.data['total_commits_count'] > 1:
            description += "s"

        return '%s pushed %s into the `%s` branch for project [%s](%s).' % (
            self.data['user_name'],
            description,
            self.data['ref'],
            self.data['repository']['name'],
            self.data['repository']['homepage']
        )


class IssueEvent(BaseEvent):

    @property
    def action(self):
        return self.data['object_attributes']['action']

    def should_report_event(self, report_events):
        return super(IssueEvent, self).should_report_event(report_events) and self.action != "update"

    def format(self):
        description = add_markdown_quotes(self.data['object_attributes']['description'])

        if self.action == 'open':
            verbose_action = 'created'
        elif self.action == 'reopen':
            verbose_action = 'reopened'
        elif self.action == 'update':
            verbose_action = 'updated'
        elif self.action == 'close':
            verbose_action = 'closed'
        else:
            raise NotImplementedError("Unsupported action %s for issue event" % self.action)

        text = '#### [%s](%s)\n*[Issue #%s](%s) %s by %s in [%s](%s) on [%s](%s)*\n %s' % (
            self.data['object_attributes']['title'],
            self.data['object_attributes']['url'],
            self.data['object_attributes']['iid'],
            self.data['object_attributes']['url'],
            verbose_action,
            self.data['user']['username'],
            self.data['repository']['name'],
            self.data['repository']['homepage'],
            self.data['object_attributes']['created_at'],
            self.data['object_attributes']['url'],
            description
        )

        base_url = self.data['repository']['homepage']

        return fix_gitlab_links(base_url, text)


class TagEvent(BaseEvent):
    def format(self):
        return '%s pushed tag `%s` to the project [%s](%s).' % (
            self.data['user_name'],
            self.data['ref'],
            self.data['repository']['name'],
            self.data['repository']['homepage']
        )


class NoteEvent(BaseEvent):
    def format(self):
        symbol = ''
        type_grammar = 'a'
        note_type = self.data['object_attributes']['noteable_type'].lower()
        note_id = ''
        parent_title = ''

        if note_type == 'mergerequest':
            symbol = '!'
            note_id = self.data['merge_request']['iid']
            parent_title = self.data['merge_request']['title']
            note_type = 'merge request'
        elif note_type == 'snippet':
            symbol = '$'
            note_id = self.data['snippet']['iid']
            parent_title = self.data['snippet']['title']
        elif note_type == 'issue':
            symbol = '#'
            note_id = self.data['issue']['iid']
            parent_title = self.data['issue']['title']
            type_grammar = 'an'

        subtitle = ''
        if note_type == 'commit':
            subtitle = '%s' % self.data['commit']['id']
        else:
            subtitle = '%s%s - %s' % (symbol, note_id, parent_title)

        description = add_markdown_quotes(self.data['object_attributes']['note'])

        text = '#### **New Comment** on [%s](%s)\n*[%s](%s) commented on %s %s in [%s](%s) on [%s](%s)*\n %s' % (
            subtitle,
            self.data['object_attributes']['url'],
            self.data['user']['username'],
            self.gitlab_user_url(self.data['user']['username']),
            type_grammar,
            note_type,
            self.data['repository']['name'],
            self.data['repository']['homepage'],
            self.data['object_attributes']['created_at'],
            self.data['object_attributes']['url'],
            description
        )

        base_url = self.data['repository']['homepage']

        return fix_gitlab_links(base_url, text)


class MergeEvent(BaseEvent):

    @property
    def action(self):
        return self.data['object_attributes']['action']

    def format(self):

        if self.action == 'open':
            text_action = 'created a'
        elif self.action == 'reopen':
            text_action = 'reopened a'
        elif self.action == 'update':
            text_action = 'updated a'
        elif self.action == 'merge':
            text_action = 'accepted a'
        elif self.action == 'close':
            text_action = 'closed a'
        else:
            raise NotImplementedError('Unsupported action %s for merge event' % self.action)

        text = '#### [!%s - %s](%s)\n*[%s](%s) %s merge request in [%s](%s) on [%s](%s)*' % (
            self.data['object_attributes']['iid'],
            self.data['object_attributes']['title'],
            self.data['object_attributes']['url'],
            self.data['user']['username'],
            self.gitlab_user_url(self.data['user']['username']),
            text_action,
            self.data['object_attributes']['target']['name'],
            self.data['object_attributes']['target']['web_url'],
            self.data['object_attributes']['created_at'],
            self.data['object_attributes']['url']
        )

        if self.action == 'open':
            description = add_markdown_quotes(self.data['object_attributes']['description'])
            text = '%s\n %s' % (
                text,
                description
            )

        base_url = self.data['object_attributes']['target']['web_url']

        return fix_gitlab_links(base_url, text)


class CIEvent(BaseEvent):

    def __init__(self, data):
        self.data = data
        self.object_kind = "ci"

    def format(self):
        icon = ':white_check_mark:' if self.data['build_status'] == "success" else ':x:'
        return '%s %s build for the project [%s](%s) on commit %s.' % (
            icon,
            self.data['build_status'].title(),
            self.data['project_name'],
            self.data['gitlab_url'],
            self.data['sha'],
        )


EVENT_CLASS_MAP = {
    constants.PUSH_EVENT: PushEvent,
    constants.ISSUE_EVENT: IssueEvent,
    constants.TAG_EVENT: TagEvent,
    constants.COMMENT_EVENT: NoteEvent,
    constants.MERGE_EVENT: MergeEvent,
}


def as_event(data):
    if data['object_kind'] in EVENT_CLASS_MAP:
        return EVENT_CLASS_MAP[data['object_kind']](data)
    else:
        raise NotImplementedError('Unsupported event of type %s' % data['object_kind'])
