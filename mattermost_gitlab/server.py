#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Python Future imports
from __future__ import unicode_literals, absolute_import, print_function

# Python System imports
import requests
import json
import argparse


# Third-party imports
from flask import Flask, request

from . import event_formatter, constants


app = Flask(__name__)


@app.route('/')
def root():
    """
    Home handler
    """

    return "OK"


@app.route('/new_event', methods=['POST'])
def new_event():
    """
    GitLab event handler, handles POST events from a GitLab project
    """

    if request.json is None:
        print('Invalid Content-Type')
        return 'Content-Type must be application/json and the request body must contain valid JSON', 400
    elif 'webhook_url' not in request.args:
        print('Webhook URL not set')
        return 'Webhook URL must be set'

    try:
        event = event_formatter.as_event(request.json)
        webhook_url = request.args['webhook_url']

        if event.should_report_event(app.config['REPORT_EVENTS']):
            text = event.format()
            post_text(text, webhook_url)
    except Exception:
        import traceback
        traceback.print_exc()

    return 'OK'


@app.route('/new_ci_event', methods=['POST'])
def new_ci_event():
    """
    GitLab event handler, handles POST events from a GitLab CI project
    """

    if request.json is None:
        print('Invalid Content-Type')
        return 'Content-Type must be application/json and the request body must contain valid JSON', 400
    elif 'webhook_url' not in request.args:
        print('Webhok URL not set')
        return 'Webhook URL must be set'

    try:
        event = event_formatter.CIEvent(request.json)
        webhook_url = request.args['webhook_url']

        if event.should_report_event(app.config['REPORT_EVENTS']):
            text = event.format()
            post_text(text, webhook_url)
    except Exception:
        import traceback
        traceback.print_exc()

    return 'OK'


def post_text(text, webhook_url):
    """
    Mattermost POST method, posts text to the Mattermost incoming webhook URL
    """

    data = {}
    data['text'] = text.strip()
    if app.config['USERNAME']:
        data['username'] = app.config['USERNAME']
    if app.config['ICON_URL']:
        data['icon_url'] = app.config['ICON_URL']
    if app.config['CHANNEL']:
        data['channel'] = app.config['CHANNEL']

    mattermost_webhook_url = app.config['MATTERMOST_URL'] + '/hooks/' + webhook_url
    headers = {'Content-Type': 'application/json'}
    resp = requests.post(mattermost_webhook_url, headers=headers, data=json.dumps(data))

    if resp.status_code is not requests.codes.ok:
        print('Encountered error posting to Mattermost URL %s, status=%d, response_body=%s' % (app.config['MATTERMOST_WEBHOOK_URL'], resp.status_code, resp.json()))


def parse_args(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('MATTERMOST_URL', help='The Mattermost URL')

    server_options = parser.add_argument_group("Server")
    server_options.add_argument('-p', '--port', type=int, default=5000)
    server_options.add_argument('--host', default='0.0.0.0')

    parser.add_argument('-u', '--username', dest='USERNAME', default='gitlab')
    parser.add_argument('--channel', dest='CHANNEL', default='')  # Leave this blank to post to the default channel of your webhook
    parser.add_argument('--icon', dest='ICON_URL', default='https://gitlab.com/uploads/project/avatar/13083/gitlab-logo-square.png')

    event_options = parser.add_argument_group("Events")

    event_options.add_argument(
        '--push',
        action='store_true',
        dest=constants.PUSH_EVENT,
        help='On pushes to the repository excluding tags'
    )
    event_options.add_argument(
        '--tag',
        action='store_true',
        dest=constants.TAG_EVENT,
        help='On creation of tags'
    )
    event_options.add_argument(
        '--no-issue',
        action='store_false',
        dest=constants.ISSUE_EVENT,
        help='On creation of a new issue'
    )
    event_options.add_argument(
        '--no-comment',
        action='store_false',
        dest=constants.COMMENT_EVENT,
        help='When a new comment is made on commits, merge requests, issues, and code snippets'
    )
    event_options.add_argument(
        '--no-merge-request',
        action='store_false',
        dest=constants.MERGE_EVENT,
        help='When a merge request is created'
    )
    event_options.add_argument(
        '--no-ci',
        action='store_false',
        dest=constants.CI_EVENT,
        help='On Continuous Integration events'
    )

    options = vars(parser.parse_args(args=args))

    host, port = options.pop("host"), options.pop("port")

    options["REPORT_EVENTS"] = {
        constants.PUSH_EVENT: options.pop(constants.PUSH_EVENT),
        constants.TAG_EVENT: options.pop(constants.TAG_EVENT),
        constants.ISSUE_EVENT: options.pop(constants.ISSUE_EVENT),
        constants.COMMENT_EVENT: options.pop(constants.COMMENT_EVENT),
        constants.MERGE_EVENT: options.pop(constants.MERGE_EVENT),
        constants.CI_EVENT: options.pop(constants.CI_EVENT),
    }

    return host, port, options


def main():
    host, port, options = parse_args()
    app.config.update(options)

    app.run(host=host, port=port)


if __name__ == "__main__":

    main()
