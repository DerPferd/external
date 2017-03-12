#!/usr/bin/env python

from __future__ import print_function
import os
import re
import sys
import json
from subprocess import Popen, PIPE


ZIM_ICON = "zim"
MATCH_THRESHOLD = 60
MATCH_PAGE_THRESHOLD = 60


class Notebook():
    def __init__(self, path):
        self.path = path
        self.__set_name()

    def __set_name(self):
        self.name = None
        nbfile = os.path.join(self.path, "notebook.zim")
        if os.path.exists(nbfile):
            r = re.search(r'name=(.*)', open(nbfile, "r").read())
            if r:
                gs = r.groups()
                if gs:
                    self.name = gs[0]


class Page():
    def __init__(self, path, name, directory=None):
        self.path = path
        self.name = name
        self.dir = directory


def get_zim_notebooks():
    nbroot = os.path.join(os.path.expanduser("~"), "Notebooks")
    nbdirs = os.listdir(nbroot)
    notebooks = []
    for d in nbdirs:
        nb = Notebook(os.path.join(nbroot, d))
        if nb.name:  # This should always be the case because every notebook should have a name
            notebooks += [nb]
    return notebooks


def get_zim_pages_for_notebook(nb):
    pages = []
    to_search = []
    sub = filter(lambda x: x[0] != "." and x.endswith(".txt"), os.listdir(nb.path))
    sub_paths = map(lambda x: os.path.join(nb.path, x), sub)
    for page_path in filter(lambda x: os.path.isfile(x), sub_paths):
        page_dir = page_path[:page_path.rindex(".")]
        if os.path.exists(page_dir) and os.path.isdir(page_dir):
            page = Page(page_path, os.path.basename(page_dir), page_dir)
            to_search += [page]
        else:
            page = Page(page_path, os.path.basename(page_dir))
        pages += [page]

    while to_search:
        cur = to_search.pop()
        sub = filter(lambda x: x[0] != "." and x.endswith(".txt"), os.listdir(cur.dir))
        sub_paths = map(lambda x: os.path.join(cur.dir, x), sub)
        for page_path in filter(lambda x: os.path.isfile(x), sub_paths):
            page_dir = page_path[:page_path.rindex(".")]
            if os.path.exists(page_dir) and os.path.isdir(page_dir):
                page = Page(page_path, cur.name + ":" + os.path.basename(page_dir), page_dir)
                to_search += [page]
            else:
                page = Page(page_path, cur.name + ":" + os.path.basename(page_dir))
            pages += [page]

    return pages


def metadata():
    return {"iid": "org.albert.extension.external/v2.0",
            "version": "0.0.1",
            "name": "Zim Plugin",
            "trigger": "z",
            "author": "Jonathan Beaulieu <123.jonathan@gmail.com>",
            "dependencies": []}


def _init():
    # check if we can import fuzzywizzy
    import fuzzywuzzy
    print("Found fuzzywuzzy version", fuzzywuzzy.__version__, file=sys.stderr)
    sys.exit(0)  # All is good


def _del():
    return


def begin():
    return


def end():
    return


def make_action(name="Open", command="zim", args=[]):
    return {"name": name, "command": command, "arguments": args}


def make_item(_id, name, descr, actions, icon=ZIM_ICON):
    return {"id": _id, "name": name, "description": descr, "icon": icon,
            "actions": actions}


def query(s):
    from fuzzywuzzy import process

    # TODO(derpferd): Maybe this can be done less than on every query
    notebooks = get_zim_notebooks()
    notebooks_by_name = dict(map(lambda x: (x.name, x), notebooks))

    # remove the trigger
    if s[:3] == "zim":
        s = s[3:]
    elif s[:1] == "z":
        s = s[1:]
    s = s.strip()

    items = []
    variables = {}

    # TODO(derpferd): Add good support for multi-word notebook names
    # Options
    # - z/zim o/open
    # - z/zim NotebookName
    # - z/zim NotebookName Page
    # - z/zim NotebookName Query

    if len(s.split()):
        first_word = s.split()[0]
        query = " ".join(s.split()[1:])
    else:
        first_word = ""
        query = ""

    # Zim Open
    if not first_word or first_word in "open":
        action = make_action()
        items += [make_item("open.zim", "Open Zim", "Open Zim", [action])]

    # Zim Notebook by name
    matches = process.extractBests(first_word, notebooks_by_name.keys(), limit=3)
    for name, score in matches:
        if score > MATCH_THRESHOLD:
            action = make_action(args=[name])
            items += [make_item("zim." + name, name, "Open " + name, [action])]

    # Pick the best match as the notebook to search
    notebook = None
    pages = None
    pages_by_name = None
    if matches[0][1] > MATCH_THRESHOLD:
        notebook = notebooks_by_name[matches[0][0]]
        pages = get_zim_pages_for_notebook(notebook)
        pages_by_name = dict(map(lambda x: (x.name, x), pages))

    # Zim Page by name
    if notebook:
        matches = process.extractBests(query, pages_by_name.keys(), limit=3)
        for name, score in matches:
            if score > MATCH_PAGE_THRESHOLD:
                action = make_action(args=[notebook.name, name])
                items += [make_item("zim." + notebook.name + "." + name, "Open " + name,
                                    "Open zim to " + name + " in " + notebook.name,
                                    [action])]

    # Notebook search
    if notebook:
        # Call zim --search NOTEBOOK QUERY
        p = Popen(["zim", "--search", notebook.name, query], stdin=PIPE,
                  stdout=PIPE, stderr=PIPE)
        output, err = p.communicate()
        for line in output.split(b'\n'):
            if line not in pages_by_name:
                continue
            _id = "zim." + notebook.name + "." + line
            if _id in map(lambda x: x["id"], items):
                continue
            action = make_action(args=[notebook.name, line])
            items += [{"id": _id,
                       "name": "Open " + line,
                       "description": "Open zim to " + line + " in " + notebook.name,
                       "icon": ZIM_ICON,
                       "actions": [action]}]

    return {"items": items, "variables": variables}


def main():
    op = os.environ["ALBERT_OP"]
    res = {}
    if op == "METADATA":
        res = metadata()
    elif op == "INITIALIZE":
        res = _init()
    elif op == "FINALIZE":
        res = _del()
    elif op == "SETUPSESSION":
        res = begin()
    elif op == "TEARDOWNSESSION":
        res = end()
    elif op == "QUERY":
        res = query(os.environ["ALBERT_QUERY"])

    if res:
        print(json.dumps(res))


main()