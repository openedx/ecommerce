from __future__ import absolute_import

import os
import sys
from collections import namedtuple

from six.moves import zip

# We should aspire to create batches of less than 15 python files
# although this is not a strict limit. Setting a target of 10 files,
# will on average yield batches of 10-15.
TARGET_FILE_NUMBER = 10


class Batch(object):
    """
    representation of a `batch` of python files for ticketing purposes

    the `root` of the batch is the greatest common path, given a list of
    files

    a batch is considered `blocked` if there exist other batches that
    contain files deeper in the path than this batch's root. This value
    is used to denote the fact this this batch should not be worked on
    or ticketed until the blocking batch has been completed
    """

    def __init__(self, root):
        self.root = root
        self.files = []
        self.blocked = False

    def __str__(self):
        return "{} :: {}".format(self.root, len(self.files))

    def add(self, file_path):
        self.files.append(file_path)
        self.rebalance_root()

    def remove(self, file_path):
        self.files.remove(file_path)
        self.rebalance_root()

    def contains_file(self, file_path):
        return file_path in self.files

    def contains_dir(self, dir_path):
        return dir_path in self.directories

    @property
    def directories(self):
        """
        return a list of all of the directories contained within this batch
        of files.
        """
        directories = list(set([
            '/'.join(f.split('/')[:-1]) for f in self.files
        ]))
        return sorted(directories)

    @property
    def top_level_directories(self):
        """
        return a list of all of the top level directories in this batch of
        files, that is, all of the directories that are not contained in other
        directories in this batch
        """
        top_level_directories = [d for d in self.directories if len([x for x in self.directories if x in d]) == 1]
        return top_level_directories

    def rebalance_root(self):
        """
        update the root of this batch after a file has been added, in case
        their paths differ. For example:

        if this batch had a root of /a/b/c and we add a file from /a/b/d,
        the newly balanced root should be /a/b
        """
        split_dirs = [d.split('/') for d in self.directories]
        new_root = []
        for level in zip(*split_dirs):
            if not(all([d == level[0] for d in level])):
                break
            new_root.append(level[0])
        self.root = '/'.join(new_root)

    def file_count(self):
        return len(self.files)

    def blocks(self, dirs):
        """
        determine if this batch of files blocks work on another batch of
        files. This is the case when a path (contained in this
        batch) is a child of a directory in the list `dirs`.
        """
        return any([d in self.directories for d in dirs])

    def base_similar(self, other_root):
        """
        determine if this batch has a root that is similar to another- that is,
        it is either the same, is a subdirectory, or they share a common parent
        """
        if self.root == other_root:
            return True
        elif self.root.split('/')[:-1] == other_root.split('/')[:-1]:
            return True
        elif other_root in self.root:
            return True
        else:
            return False


def check_if_blocked(batches, root, dirs):
    """
    check if any of the batches that have already been grouped are
    contained, as sub directories, in a given root and it's children
    directories
    """
    paths = [os.path.join(root, d) for d in dirs]
    return any([b.blocks(paths) for b in batches])


def filter_python_files(files):
    """
    given a list of files, extract the python files
    """
    return [f for f in files if f.endswith('.py')]


def crawl(path, TARGET_FILE_NUMBER):
    """
    crawl a given file path, from the deepest node up, collecting and
    organizing directories containing python files into `Batches` of less
    than `TARGET_FILE_NUMBER` python files.
    """
    batches = []
    in_a_batch = False

    for root, dirs, files in os.walk(path, topdown=False):
        # skip directories that have no python files
        if len(filter_python_files(files)) < 1:
            continue
        if not in_a_batch:
            current_batch = Batch(root)
            in_a_batch = True
        if not current_batch.base_similar(root):
            batches.append(current_batch)
            current_batch = Batch(root)
            in_a_batch = True
        # mark this batch as `blocked` if any of the subdirectories in the
        # current node have already been added to the list of batches
        if check_if_blocked(batches, root, dirs):
            current_batch.blocked = True
        python_files = [os.path.join(root, f) for f in filter_python_files(files)]
        for file_path in python_files:
            current_batch.add(file_path)
        if current_batch.file_count() >= TARGET_FILE_NUMBER:
            batches.append(current_batch)
            in_a_batch = False
    if in_a_batch:
        batches.append(current_batch)
    return batches


def main():
    path = sys.argv[1]
    ticket_number_seed = int(sys.argv[2])
    batches = crawl(path, TARGET_FILE_NUMBER)

    blocked_batches = [b for b in batches if b.blocked]
    ready_batches = [b for b in batches if not b.blocked]

    with open('ready_batches.csv', 'w') as out:
        for b in ready_batches:
            dirs = ':'.join(b.top_level_directories)
            ticket_number = "INCR-{}".format(ticket_number_seed)
            out.write('{},{},{},{}'.format(ticket_number, b.blocked, b.file_count(), dirs))
            out.write('\n')
            ticket_number_seed += 1

    with open('blocked_batches.csv', 'w') as out:
        for b in blocked_batches:
            dirs = ':'.join(b.top_level_directories)
            ticket_number = "INCR-{}".format(ticket_number_seed)
            out.write('{},{},{},{}'.format(ticket_number, b.blocked, b.file_count(), dirs))
            out.write('\n')
            ticket_number_seed += 1

if __name__ == '__main__':
    main()
