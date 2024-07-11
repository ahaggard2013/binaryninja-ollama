#!/usr/bin/env python2.7

from __future__ import print_function

from datetime import tzinfo, timedelta, datetime
import fnmatch
import glob
import json
import os
import sys
import tempfile
import time
import types


from functools import wraps
from pprint import pprint

import backoff
import click
import link_header
import requests
from requests import request


REQ_BUFFER_SIZE = 65536  # Chunk size when iterating a download body

_github_token_cli_arg = None
_github_api_url = None


class _UTC(tzinfo):
    """UTC"""

    ZERO = timedelta(0)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO


class _NoopProgressReporter(object):
    reportProgress = False

    def __init__(self, label='', length=0):
        self.label = label
        self.length = length

    def update(self, chunk_size):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        pass


progress_reporter_cls = _NoopProgressReporter
"""The progress reporter class to instantiate. This class
is expected to be a context manager with a constructor accepting `label`
and `length` keyword arguments, an `update` method accepting a `chunk_size`
argument and a class attribute `reportProgress` set to True (It can
conveniently be initialized using `sys.stdout.isatty()`)
"""


def _request(*args, **kwargs):
    with_auth = kwargs.pop("with_auth", True)
    token = _github_token_cli_arg
    if not token:
        token = os.environ.get("GITHUB_TOKEN", None)
    if token and with_auth:
        kwargs["auth"] = (token, 'x-oauth-basic')
    for _ in range(3):
        response = request(*args, **kwargs)
        is_travis = os.getenv("TRAVIS",  None) is not None
        if is_travis and 400 <= response.status_code < 500:
            print("Retrying in 1s (%s Client Error: %s for url: %s)" % (
                response.status_code, response.reason, response.url))
            time.sleep(1)
            continue
        break
    return response


def handle_http_error(func):
    @wraps(func)
    def with_error_handling(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            print('Error sending {0} to {1}'.format(
                e.request.method, e.request.url))
            print('<', e.request.method, e.request.path_url)
            for k in sorted(e.request.headers.keys()):
                print('<', k, ':', e.request.headers[k])
            if e.request.body:
                print('<')
                print('<', repr(e.request.body[:35]),
                      '(total {0} bytes of data)'.format(len(e.request.body)))
            print('')
            print('>', e.response.status_code, e.response.reason)
            for k in sorted(e.response.headers.keys()):
                print('>', k.title(), ':', e.response.headers[k])
            if e.response.content:
                print('>')
                print('>', repr(e.response.content[:35]),
                      '(total {0} bytes of data)'.format(
                          len(e.response.content)))
            return 1
    return with_error_handling


def _check_for_credentials(func):
    @wraps(func)
    def with_check_for_credentials(*args, **kwargs):
        has_github_token_env_var = "GITHUB_TOKEN" in os.environ
        has_netrc = requests.utils.get_netrc_auth(github_api_url())
        if (not _github_token_cli_arg
                and not has_github_token_env_var and not has_netrc):
            raise EnvironmentError(
                "This command requires credentials provided by passing "
                "--github-token CLI argument, set using GITHUB_TOKEN "
                "env. variable or using netrc file. For more details, "
                "see https://github.com/j0057/github-release#configuring")
        return func(*args, **kwargs)
    return with_check_for_credentials


def _progress_bar(*args, **kwargs):
    bar = click.progressbar(*args, **kwargs)
    bar.bar_template = "  [%(bar)s]  %(info)s  %(label)s"
    bar.show_percent = True
    bar.show_pos = True

    def formatSize(length):
        if length == 0:
            return '%.2f' % length
        unit = ''
        # See https://en.wikipedia.org/wiki/Binary_prefix
        units = ['k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
        while True:
            if length <= 1024 or len(units) == 0:
                break
            unit = units.pop(0)
            length /= 1024.
        return '%.2f%s' % (length, unit)

    def formatPos(_self):
        pos = formatSize(_self.pos)
        if _self.length is not None:
            pos += '/%s' % formatSize(_self.length)
        return pos

    bar.format_pos = types.MethodType(formatPos, bar)
    return bar


def _recursive_gh_get(href, items):
    """Recursively get list of GitHub objects.

    See https://developer.github.com/v3/guides/traversing-with-pagination/
    """
    response = _request('GET', href)
    response.raise_for_status()
    items.extend(response.json())
    if "link" not in response.headers:
        return
    links = link_header.parse(response.headers["link"])
    rels = {link.rel: link.href for link in links.links}
    if "next" in rels:
        _recursive_gh_get(rels["next"], items)


def _validate_repo_name(ctx, param, value):
    """Callback used to check if repository argument was given."""
    if "/" not in value:
        raise click.BadParameter('Expected format for REPOSITORY is '
                                 '"<org_name>/<project_name>" (e.g "jcfr/sandbox")')
    return value


#
# CLI
#

@click.group()
@click.option("--github-token", envvar='GITHUB_TOKEN', default=None,
              help="[default: GITHUB_TOKEN env. variable]")
@click.option('--github-api-url', envvar='GITHUB_API_URL',
              default='https://api.github.com',
              help='[default: https://api.github.com]')
@click.option("--progress/--no-progress", default=True,
              help="Display progress bar (default: yes).")
def main(github_token, github_api_url, progress):
    """A CLI to easily manage GitHub releases, assets and references."""
    global progress_reporter_cls
    progress_reporter_cls.reportProgress = sys.stdout.isatty() and progress
    if progress_reporter_cls.reportProgress:
        progress_reporter_cls = _progress_bar
    global _github_token_cli_arg
    _github_token_cli_arg = github_token
    set_github_api_url(github_api_url)


@main.group("release")
@click.argument('repo_name', metavar="REPOSITORY", callback=_validate_repo_name)
@click.pass_context
@handle_http_error
def gh_release(ctx, repo_name):
    """Manage releases (list, create, delete, ...) for
    REPOSITORY (e.g jcfr/sandbox)
    """
    ctx.obj = repo_name


# 1.6.0 (deprecated): Remove this bloc
class AssetGroup(click.Group):
    def get_command(self, ctx, cmd_name):
        cmd_name = "delete" if cmd_name == "erase" else cmd_name
        return click.Group.get_command(self, ctx, cmd_name)


@main.group("asset", cls=AssetGroup)
@click.argument('repo_name', metavar="REPOSITORY", callback=_validate_repo_name)
@click.pass_context
@handle_http_error
def gh_asset(ctx, repo_name):
    """Manage release assets (upload, download, ...) for
    REPOSITORY (e.g jcfr/sandbox)
    """
    ctx.obj = repo_name


@main.group("ref")
@click.argument('repo_name', metavar="REPOSITORY", callback=_validate_repo_name)
@click.pass_context
@handle_http_error
def gh_ref(ctx, repo_name):
    """Manage references (list, create, delete, ...) for
    REPOSITORY (e.g jcfr/sandbox)
    """
    ctx.obj = repo_name


#
# General
#

def github_api_url():
    """Return GitHub API URL.

    If no URL has been set, return https://api.github.com unless the
    GITHUB_API_URL environment variable has been set.
    """
    if _github_api_url is None:
        return os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    return _github_api_url


def set_github_api_url(url):
    """Set GitHub API URL.
    """
    global _github_api_url
    _github_api_url = url


#
# Releases
#

def print_release_info(release, title=None, indent=""):
    if title is None:
        title = "release '{0}' info".format(release["tag_name"])
    print(indent + title)
    indent = "  " + indent
    print(indent + 'Tag name      : {tag_name}'.format(**release))
    if release['name']:
        print(indent + 'Name          : {name}'.format(**release))
    print(indent + 'ID            : {id}'.format(**release))
    print(indent + 'Created       : {created_at}'.format(**release))
    print(indent + 'URL           : {html_url}'.format(**release))
    print(indent + 'Author        : {login}'.format(**release['author']))
    print(indent + 'Is published  : {0}'.format(not release['draft']))
    print(indent + 'Is prerelease : {0}'.format(release['prerelease']))
    if release['body']:
        print(indent + 'Release notes :')
        print(indent + release['body'])
    print('')
    for (i, asset) in enumerate(release['assets']):
        print_asset_info(i, asset, indent=indent)


def get_release_type(release):
    """Return the type of the release

    Either 'draft', 'prerelease' (no draft) or 'release' (neither)
    """
    if release['draft']:
        return 'draft'
    if release['prerelease']:
        return 'prerelease'
    return 'release'


@backoff.on_exception(backoff.expo, requests.exceptions.HTTPError, max_time=60)
def get_releases(repo_name, verbose=False):

    releases = []
    _recursive_gh_get(
        github_api_url() + '/repos/{0}/releases'.format(repo_name), releases)

    if verbose:
        list(map(print_release_info,
                 sorted(releases, key=lambda r: r['tag_name'])))
    return releases


@backoff.on_predicate(backoff.expo, lambda x: x is None, max_time=5)
def get_release(repo_name, tag_name):
    """Return release

    .. note::

        If the release is not found (e.g the release was just created and
        the GitHub response is not yet updated), this function is called again by
        leveraging the `backoff` decorator.

        See https://github.com/j0057/github-release/issues/67
    """
    releases = get_releases(repo_name)
    try:
        release = next(r for r in releases if r['tag_name'] == tag_name)
        return release
    except StopIteration:
        return None


def get_release_info(repo_name, tag_name):
    release = get_release(repo_name, tag_name)
    if release is not None:
        return release
    else:
        raise Exception('Release with tag_name {0} not found'.format(tag_name))


def _update_release_sha(repo_name, tag_name, new_release_sha, dry_run):
    """Update the commit associated with a given release tag.

    Since updating a tag commit is not directly possible, this function
    does the following steps:
    * set the release tag to ``<tag_name>-tmp`` and associate it
      with ``new_release_sha``.
    * delete tag ``refs/tags/<tag_name>``.
    * update the release tag to ``<tag_name>`` and associate it
      with ``new_release_sha``.
    """
    if new_release_sha is None:
        return
    refs = get_refs(repo_name, tags=True, pattern="refs/tags/%s" % tag_name)
    if not refs:
        return
    assert len(refs) == 1

    # If sha associated with "<tag_name>" is up-to-date, we are done.
    previous_release_sha = refs[0]["object"]["sha"]
    if previous_release_sha == new_release_sha:
        return

    tmp_tag_name = tag_name + "-tmp"

    # If any, remove leftover temporary tag "<tag_name>-tmp"
    refs = get_refs(repo_name, tags=True, pattern="refs/tags/%s" % tmp_tag_name)
    if refs:
        assert len(refs) == 1
        time.sleep(0.1)
        gh_ref_delete(repo_name,
                      "refs/tags/%s" % tmp_tag_name, dry_run=dry_run)

    # Update "<tag_name>" release by associating it with the "<tag_name>-tmp"
    # and "<new_release_sha>". It will create the temporary tag.
    time.sleep(0.1)
    patch_release(repo_name, tag_name,
                  tag_name=tmp_tag_name,
                  target_commitish=new_release_sha,
                  dry_run=dry_run)

    # Now "<tag_name>-tmp" references "<new_release_sha>", remove "<tag_name>"
    time.sleep(0.1)
    gh_ref_delete(repo_name, "refs/tags/%s" % tag_name, dry_run=dry_run)

    # Finally, update "<tag_name>-tmp" release by associating it with the
    # "<tag_name>" and "<new_release_sha>".
    time.sleep(0.1)
    patch_release(repo_name, tmp_tag_name,
                  tag_name=tag_name,
                  target_commitish=new_release_sha,
                  dry_run=dry_run)

    # ... and remove "<tag_name>-tmp"
    time.sleep(0.1)
    gh_ref_delete(repo_name,
                  "refs/tags/%s" % tmp_tag_name, dry_run=dry_run)


def patch_release(repo_name, current_tag_name, **values):
    dry_run = values.get("dry_run", False)
    verbose = values.get("verbose", False)
    release = get_release_info(repo_name, current_tag_name)
    new_tag_name = values.get("tag_name", release["tag_name"])

    _update_release_sha(
        repo_name,
        new_tag_name,
        values.get("target_commitish", None),
        dry_run
    )

    data = {
        "tag_name": release["tag_name"],
        "target_commitish": release["target_commitish"],
        "name": release["name"],
        "body": release["body"],
        "draft": release["draft"],
        "prerelease": release["prerelease"]
    }

    updated = []
    for key in data:
        if key in values and data[key] != values[key]:
            updated.append("%s: '%s' -> '%s'" % (key, data[key], values[key]))
    if updated:
        print("updating '%s' release: \n  %s" % (
            current_tag_name, "\n  ".join(updated)))
        print("")

    if len(values.get("body", "")) >= 125000:
        raise Exception('Failed to update release {0}. Description has {1} characters and maximum is 125000 characters'.format(
          release["tag_name"], len(values["body"])))

    data.update(values)

    if not dry_run:
        url = github_api_url() + '/repos/{0}/releases/{1}'.format(
            repo_name, release['id'])
        response = _request(
            'PATCH', url,
            data=json.dumps(data),
            headers={'Content-Type': 'application/json'})
        response.raise_for_status()

    # In case a new tag name was provided, remove the old one.
    if current_tag_name != data["tag_name"]:
        gh_ref_delete(
            repo_name, "refs/tags/%s" % current_tag_name,
            tags=True, verbose=verbose, dry_run=dry_run)


def get_assets(repo_name, tag_name, verbose=False):
    release = get_release(repo_name, tag_name)
    if not release:
        raise Exception('Release with tag_name {0} not found'.format(tag_name))

    assets = []
    _recursive_gh_get(github_api_url() + '/repos/{0}/releases/{1}/assets'.format(
        repo_name, release["id"]), assets)

    if verbose:
        for i, asset in enumerate(sorted(assets, key=lambda r: r['name'])):
            print_asset_info(i, asset)

    return assets


def get_asset_info(repo_name, tag_name, filename):
    assets = get_assets(repo_name, tag_name)
    try:
        asset = next(a for a in assets if a['name'] == filename)
        return asset
    except StopIteration:
        raise Exception('Asset with filename {0} not found in '
                        'release with tag_name {1}'.format(filename, tag_name))


@gh_release.command("list")
@click.pass_obj
def _cli_release_list(repo_name):
    """List releases"""
    return get_releases(repo_name, verbose=True)


@gh_release.command("info")
@click.argument("tag_name")
@click.pass_obj
def _cli_release_info(repo_name, tag_name):
    """Get release description"""
    release = get_release_info(repo_name, tag_name)
    print_release_info(release)


@gh_release.command("create")
@click.argument("tag_name")
@click.argument("asset_pattern", nargs=-1)
@click.option("--name")
@click.option("--body", default=None)
@click.option("--publish", is_flag=True, default=False)
@click.option("--prerelease", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--target-commitish")
@click.pass_obj
def cli_release_create(*args, **kwargs):
    """Create a release"""
    gh_release_create(*args, **kwargs)


@_check_for_credentials
def gh_release_create(repo_name, tag_name, asset_pattern=None, name=None, body=None,
                      publish=False, prerelease=False,
                      target_commitish=None, dry_run=False):
    if get_release(repo_name, tag_name) is not None:
        print('release %s: already exists\n' % tag_name)
        return
    data = {
        'tag_name': tag_name,
        'draft': not publish and not prerelease,
        'prerelease': prerelease
    }
    if name is not None:
        data["name"] = name
    if body is not None:
        data["body"] = body
    if target_commitish is not None:
        data["target_commitish"] = target_commitish
    if not dry_run:
        response = _request(
              'POST', github_api_url() + '/repos/{0}/releases'.format(repo_name),
              data=json.dumps(data),
              headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        print_release_info(response.json(),
                           title="created '%s' release" % tag_name)
    else:
        print("created '%s' release (dry_run)" % tag_name)
    if asset_pattern:
        gh_asset_upload(repo_name, tag_name, asset_pattern, dry_run=dry_run)


@gh_release.command("edit")
@click.argument("current_tag_name")
@click.option("--tag-name", default=None)
@click.option("--target-commitish", default=None)
@click.option("--name", default=None)
@click.option("--body", default=None)
@click.option("--draft/--publish", is_flag=True, default=None)
@click.option("--prerelease/--release", is_flag=True, default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_obj
def _cli_release_edit(*args, **kwargs):
    """Edit a release"""
    gh_release_edit(*args, **kwargs)


@_check_for_credentials
def gh_release_edit(repo_name, current_tag_name,
                    tag_name=None, target_commitish=None, name=None,
                    body=None,
                    draft=None, prerelease=None, dry_run=False, verbose=False):
    attributes = {}
    for key in [
        "tag_name", "target_commitish", "name", "body", "draft",
        "prerelease", "dry_run", "verbose"
    ]:
        if locals().get(key, None) is not None:
            attributes[key] = locals()[key]
    patch_release(repo_name, current_tag_name, **attributes)


@gh_release.command("delete")
@click.argument("pattern")
@click.option("--keep-pattern")
@click.option("--release-type", type=click.Choice(['all', 'draft', 'prerelease', 'release']), default='all')
@click.option("--older-than", type=int, default=0)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_obj
def _cli_release_delete(*args, **kwargs):
    """Delete selected release"""
    gh_release_delete(*args, **kwargs)


@_check_for_credentials
def gh_release_delete(repo_name, pattern, keep_pattern=None, release_type='all', older_than=0,
                      dry_run=False, verbose=False):
    releases = get_releases(repo_name)
    candidates = []
    # Get list of candidate releases
    for release in releases:
        if not fnmatch.fnmatch(release['tag_name'], pattern):
            if verbose:
                print('skipping release {0}: do not match {1}'.format(
                    release['tag_name'], pattern))
            continue
        if keep_pattern is not None:
            if fnmatch.fnmatch(release['tag_name'], keep_pattern):
                continue
        if release_type != 'all' and release_type != get_release_type(release):
            if verbose:
                print('skipping release {0}: type {1} is not {2}'.format(
                    release['tag_name'], get_release_type(release), release_type))
            continue
        # Assumes Zulu time.
        # See https://stackoverflow.com/questions/127803/how-to-parse-an-iso-8601-formatted-date
        utc = _UTC()
        rel_date = datetime.strptime(release['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
        rel_age = int((datetime.now(utc) - rel_date).total_seconds() / 60 / 60)  # In hours
        if older_than > rel_age:
            if verbose:
                print('skipping release {0}: created less than {1} hours ago ({2}hrs)'.format(
                    release['tag_name'], older_than, rel_age))
            continue
        candidates.append(release)
    for release in candidates:
        print('deleting release {0}'.format(release['tag_name']))
        if dry_run:
            continue
        url = (github_api_url()
               + '/repos/{0}/releases/{1}'.format(repo_name, release['id']))
        response = _request('DELETE', url)
        response.raise_for_status()
    return len(candidates) > 0


@gh_release.command("publish")
@click.argument("tag_name")
@click.option("--prerelease", is_flag=True, default=False)
@click.pass_obj
def _cli_release_publish(*args, **kwargs):
    """Publish a release setting draft to 'False'"""
    gh_release_publish(*args, **kwargs)


@_check_for_credentials
def gh_release_publish(repo_name, tag_name, prerelease=False):
    patch_release(repo_name, tag_name, draft=False, prerelease=prerelease)


@gh_release.command("unpublish")
@click.argument("tag_name")
@click.option("--prerelease", is_flag=True, default=False)
@click.pass_obj
def _cli_release_unpublish(*args, **kwargs):
    """Unpublish a release setting draft to 'True'"""
    gh_release_unpublish(*args, **kwargs)


@_check_for_credentials
def gh_release_unpublish(repo_name, tag_name, prerelease=False):
    draft = not prerelease
    patch_release(repo_name, tag_name, draft=draft, prerelease=prerelease)


@gh_release.command("release-notes")
@click.argument("tag_name")
@click.pass_obj
def _cli_release_notes(*args, **kwargs):
    """Set release notes"""
    gh_release_notes(*args, **kwargs)


@_check_for_credentials
def gh_release_notes(repo_name, tag_name):
    release = get_release_info(repo_name, tag_name)
    (_, filename) = tempfile.mkstemp(suffix='.md')
    try:
        if release['body']:
            with open(filename, 'w+b') as f:
                body = release['body']
                if sys.version_info[0] >= 3:
                    body = body.encode('utf-8')
                f.write(body)
        if 'EDITOR' not in os.environ:
            raise EnvironmentError(
                "This command requires editor set using EDITOR "
                "env. variable.")
        ret = os.system('{0} {1}'.format(os.environ['EDITOR'], filename))
        if ret:
            raise Exception(
                '{0} returned exit code {1}'.format(os.environ['EDITOR'], ret))
        with open(filename, 'rb') as f:
            body = f.read()
            if sys.version_info[0] >= 3:
                body = body.decode('utf-8')
        if release['body'] == body:
            return
        patch_release(repo_name, tag_name, body=body)
    finally:
        os.remove(filename)


@gh_release.command("debug")
@click.argument("tag_name")
@click.pass_obj
def _cli_release_debug(repo_name, tag_name):
    """Print release detailed information"""
    release = get_release_info(repo_name, tag_name)
    pprint(release)


#
# Assets
#

def print_asset_info(i, asset, indent=""):
    print(indent + "Asset #{i}".format(i=i))
    indent = "  " + indent
    print(indent + "name      : {name}".format(i=i, **asset))
    print(indent + "state     : {state}".format(i=i, **asset))
    print(indent + "uploader  : {login}".format(i=i, **asset['uploader']))
    print(indent + "size      : {size}".format(i=i, **asset))
    print(indent + "URL       : {browser_download_url}".format(i=i, **asset))
    print(indent + "Downloads : {download_count}".format(i=i, **asset))
    print("")


@gh_asset.command("upload")
@click.argument("tag_name")
@click.argument("pattern", nargs=-1)
@click.pass_obj
def _cli_asset_upload(*args, **kwargs):
    """Upload release assets"""
    gh_asset_upload(*args, **kwargs)


class _ProgressFileReader(object):
    """Wrapper used to capture File IO read progress."""
    def __init__(self, stream, reporter):
        self._stream = stream
        self._reporter = reporter

    def read(self, _size):
        _chunk = self._stream.read(_size)
        self._reporter.update(len(_chunk))
        return _chunk

    def __getattr__(self, attr):
        return getattr(self._stream, attr)


def _upload_release_file(
        repo_name, tag_name, upload_url, filename,
        verbose=False, dry_run=False, retry=True):
    already_uploaded = False
    uploaded = False
    basename = os.path.basename(filename)
    # Sanity checks
    assets = get_assets(repo_name, tag_name)
    download_url = None
    for asset in assets:
        if asset["name"] == basename:
            if asset["state"] == "uploaded":
                download_url = asset["browser_download_url"]
                break
            # Remove asset that failed to upload
            # See https://developer.github.com/v3/repos/releases/#response-for-upstream-failure  # noqa: E501
            if asset["state"] == "new":
                print("  deleting %s (invalid asset "
                      "with state set to 'new')" % asset['name'])
                url = (
                    github_api_url()
                    + '/repos/{0}/releases/assets/{1}'.format(
                        repo_name, asset['id'])
                )
                response = _request('DELETE', url)
                response.raise_for_status()

    print("  uploading %s" % filename)

    # Skip if an asset with same name has already been uploaded
    # Trying to upload would give a HTTP error 422
    if download_url:
        already_uploaded = True
        print("  skipping (asset with same name already exists)")
        print("  download_url: %s" % download_url)
        print("")
        return already_uploaded, uploaded, {}
    if dry_run:
        uploaded = True
        print("  download_url: Unknown (dry_run)")
        print("")
        return already_uploaded, uploaded, {}

    url = '{0}?name={1}'.format(upload_url, basename)
    if verbose and not progress_reporter_cls.reportProgress:
        print("  upload_url: %s" % url)
    file_size = os.path.getsize(filename)

    # Attempt upload
    with open(filename, 'rb') as f:
        with progress_reporter_cls(
                label=basename, length=file_size) as reporter:
            response = _request(
                'POST', url,
                headers={'Content-Type': 'application/octet-stream'},
                data=_ProgressFileReader(f, reporter))
            data = response.json()

    if response.status_code == 502 and retry:
        print("  retrying (upload failed with status_code=502)")
        already_uploaded, uploaded, data = _upload_release_file(
            repo_name, tag_name, upload_url, filename,
            verbose=verbose, retry=False)
    else:
        response.raise_for_status()
    asset = data
    print("  download_url: %s" % asset["browser_download_url"])
    print("")
    uploaded = True
    return already_uploaded, uploaded, response.json()


@_check_for_credentials
def gh_asset_upload(repo_name, tag_name, pattern, dry_run=False, verbose=False):
    if not dry_run:
        upload_url = get_release_info(repo_name, tag_name)["upload_url"]
        if "{" in upload_url:
            upload_url = upload_url[:upload_url.index("{")]
    else:
        upload_url = "unknown"

    # Raise exception if no token is specified AND netrc file is found
    # BUT only api.github.com is specified. See #17
    has_github_token = "GITHUB_TOKEN" in os.environ
    has_netrc = requests.utils.get_netrc_auth(github_api_url())
    if not has_github_token and has_netrc:
        if requests.utils.get_netrc_auth(upload_url) is None:
            raise EnvironmentError(
                "Found netrc file but upload URL is missing. "
                "For more details, "
                "see https://github.com/j0057/github-release#configuring")

    if type(pattern) in [list, tuple]:
        filenames = []
        for package in pattern:
            filenames.extend(glob.glob(package))
        filenames = set(filenames)
    elif pattern:
        filenames = glob.glob(pattern)
    else:
        filenames = []

    if len(filenames) > 0:
        print("uploading '%s' release asset(s) "
              "(found %s):" % (tag_name, len(filenames)))

    uploaded = False
    already_uploaded = False

    for filename in filenames:
        already_uploaded, uploaded, _ = _upload_release_file(
            repo_name, tag_name, upload_url, filename, verbose, dry_run)

    if not uploaded and not already_uploaded:
        print("skipping upload of '%s' release assets ("
              "no files match pattern(s): %s)" % (tag_name, pattern))
        print("")


@gh_asset.command("delete")
@click.argument("tag_name")
@click.argument("pattern")
@click.option("--keep-pattern", default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_obj
def _cli_asset_delete(*args, **kwargs):
    """Delete selected release assets"""
    gh_asset_delete(*args, **kwargs)


@_check_for_credentials
def gh_asset_delete(repo_name, tag_name, pattern,
                    keep_pattern=None, dry_run=False, verbose=False):
    # Get assets
    assets = get_assets(repo_name, tag_name)
    # List of assets
    excluded_assets = {}
    matched_assets = []
    matched_assets_to_keep = {}
    for asset in assets:
        if not fnmatch.fnmatch(asset['name'], pattern):
            skip_reason = "do NOT match pattern '%s'" % pattern
            excluded_assets[asset['name']] = skip_reason
            continue
        matched_assets.append(asset)
        if keep_pattern is not None:
            if fnmatch.fnmatch(asset['name'], keep_pattern):
                skip_reason = "match keep_pattern '%s'" % keep_pattern
                matched_assets_to_keep[asset['name']] = skip_reason
                continue
    # Summary
    summary = "matched: %s, matched-but-keep: %s, not-matched: %s" % (
        len(matched_assets),
        len(matched_assets_to_keep),
        len(excluded_assets)
    )
    print("deleting '%s' release asset(s) (%s):" % (tag_name, summary))
    # Perform deletion
    for asset in matched_assets:
        if asset['name'] in matched_assets_to_keep:
            if verbose:
                skip_reason = matched_assets_to_keep[asset['name']]
                print("  skipping %s (%s)" % (asset['name'], skip_reason))
            continue
        print("  deleting %s" % asset['name'])
        if dry_run:
            continue
        url = (
            github_api_url()
            + '/repos/{0}/releases/assets/{1}'.format(repo_name, asset['id'])
        )
        response = _request('DELETE', url)
        response.raise_for_status()
    if len(matched_assets) == 0:
        print("  nothing to delete")
    print("")
    if verbose:
        indent = "  "
        print(indent + "assets NOT matching selection pattern [%s]:" % pattern)
        for asset_name in excluded_assets:
            print(indent + "  " + asset_name)
        print("")


@gh_asset.command("download")
@click.argument("tag_name")
@click.argument("pattern", required=False)
@click.pass_obj
def _cli_asset_download(*args, **kwargs):
    """Download release assets"""
    gh_asset_download(*args, **kwargs)


def _download_file(repo_name, asset):
    response = _request(
        method='GET',
        url=github_api_url() + '/repos/{0}/releases/assets/{1}'.format(
            repo_name, asset['id']),
        allow_redirects=False,
        headers={'Accept': 'application/octet-stream'},
        stream=True)
    while response.status_code == 302:
        response = _request(
            'GET', response.headers['Location'], allow_redirects=False,
            stream=True,
            with_auth=False
        )
    with open(asset['name'], 'w+b') as f:
        with progress_reporter_cls(
                label=asset['name'], length=asset['size']) as reporter:
            for chunk in response.iter_content(chunk_size=REQ_BUFFER_SIZE):
                reporter.update(len(chunk))
                f.write(chunk)


def gh_asset_download(repo_name, tag_name=None, pattern=None):
    releases = get_releases(repo_name)
    downloaded = 0
    for release in releases:
        if tag_name and not fnmatch.fnmatch(release['tag_name'], tag_name):
            continue
        for asset in release['assets']:
            if pattern and not fnmatch.fnmatch(asset['name'], pattern):
                continue
            if os.path.exists(asset['name']):
                absolute_path = os.path.abspath(asset['name'])
                print('release {0}: '
                      'skipping {1}: '
                      'found {2}'.format(
                        release['tag_name'], asset['name'], absolute_path))
                continue
            print('release {0}: '
                  'downloading {1}'.format(release['tag_name'], asset['name']))
            _download_file(repo_name, asset)
            downloaded += 1
    return downloaded


@gh_asset.command("list")
@click.argument("tag_name")
@click.pass_obj
def _cli_asset_list(repo_name, tag_name):
    """List release assets"""
    return get_assets(repo_name, tag_name, verbose=True)


#
# References
#

def print_object_info(ref_object, indent=""):
    print(indent + 'Object')
    print(indent + '  type : {type}'.format(**ref_object))
    print(indent + '  sha  : {sha}'.format(**ref_object))


def print_ref_info(ref, indent=""):
    print(indent + "Reference '{ref}'".format(**ref))
    print_object_info(ref['object'], indent="  " + indent)
    print("")


def get_refs(repo_name, tags=None, pattern=None):

    refs = []
    _recursive_gh_get(
        github_api_url() + '/repos/{0}/git/refs'.format(repo_name), refs)

    # If "tags" is True, keep only "refs/tags/*"
    data = refs
    if tags:
        tag_names = []
        data = []
        for ref in refs:
            if ref['ref'].startswith("refs/tags"):
                data.append(ref)
                tag_names.append(ref["ref"])

        try:
            tags = []
            _recursive_gh_get(
                github_api_url() + '/repos/{0}/git/refs/tags'.format(repo_name), tags)
            for ref in tags:
                if ref["ref"] not in tag_names:
                    data.append(ref)
        except requests.exceptions.HTTPError as exc_info:
            response = exc_info.response
            if response.status_code != 404:
                raise

    # If "pattern" is not None, select only matching references
    filtered_data = data
    if pattern is not None:
        filtered_data = []
        for ref in data:
            if fnmatch.fnmatch(ref['ref'], pattern):
                filtered_data.append(ref)

    return filtered_data


@gh_ref.command("list")
@click.option("--tags", is_flag=True, default=False)
@click.option("--pattern", default=None)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_obj
def _cli_ref_list(*args, **kwargs):
    """List all references"""
    gh_ref_list(*args, **kwargs)


def gh_ref_list(repo_name, tags=None,  pattern=None, verbose=False):
    refs = get_refs(repo_name, tags=tags, pattern=pattern)
    sorted_refs = sorted(refs, key=lambda r: r['ref'])
    if verbose:
        list(map(print_ref_info, sorted_refs))
    else:
        list(map(lambda ref: print(ref['ref']), sorted_refs))
    return sorted_refs


@gh_ref.command("create")
@click.argument("reference")
@click.argument("sha")
@click.pass_obj
def _cli_ref_create(*args, **kwargs):
    """Create reference (e.g heads/foo, tags/foo)"""
    gh_ref_create(*args, **kwargs)


@_check_for_credentials
def gh_ref_create(repo_name, reference, sha):
    data = {
        'ref': "refs/%s" % reference,
        'sha': sha
    }
    response = _request(
          'POST', github_api_url() + '/repos/{0}/git/refs'.format(repo_name),
          data=json.dumps(data),
          headers={'Content-Type': 'application/json'})
    response.raise_for_status()
    print_ref_info(response.json())


@gh_ref.command("delete")
@click.argument("pattern")
@click.option("--keep-pattern", default=None)
@click.option("--tags", is_flag=True, default=False)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.pass_obj
def _cli_ref_delete(*args, **kwargs):
    """Delete selected references"""
    gh_ref_delete(*args, **kwargs)


@_check_for_credentials
def gh_ref_delete(repo_name, pattern, keep_pattern=None, tags=False,
                  dry_run=False, verbose=False):
    removed_refs = []
    refs = get_refs(repo_name, tags=tags)
    for ref in refs:
        if not fnmatch.fnmatch(ref['ref'], pattern):
            if verbose:
                print('skipping reference {0}: '
                      'do not match {1}'.format(ref['ref'], pattern))
            continue
        if keep_pattern is not None:
            if fnmatch.fnmatch(ref['ref'], keep_pattern):
                continue
        print('deleting reference {0}'.format(ref['ref']))
        removed_refs.append(ref['ref'])
        if dry_run:
            continue
        response = _request(
            'DELETE',
            github_api_url() + '/repos/{0}/git/{1}'.format(repo_name, ref['ref']))
        response.raise_for_status()
    return len(removed_refs) > 0


#
# Commits
#

def gh_commit_get(repo_name, sha):
    try:
        response = _request(
            'GET',
            github_api_url() + '/repos/{0}/git/commits/{1}'.format(repo_name, sha))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as exc_info:
        response = exc_info.response
        if response.status_code == 404:
            return None
        else:
            raise


#
# Script entry point
#

if __name__ == '__main__':
    main()
