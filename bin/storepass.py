#!/usr/bin/env python

import click
import collections
import Crypto.Cipher.AES
import hashlib
import json
import os
import pickle
import pyperclip
import random
import subprocess


DEFAULTPATH = os.path.expanduser('~/.storepass-data')


def encrypt(text, password):
    """
    AES (CFB) encrypt 'text' with 'password'.
    """
    key = hashlib.sha1(password).hexdigest()[:32]
    iv = os.urandom(16)
    aes_obj = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CFB, iv)
    return iv + aes_obj.encrypt(text)


def decrypt(encoded, password):
    """
    Decrypt an AES (CFB) encrypted string with a 16-byte prepended IV.
    """
    key = hashlib.sha1(password).hexdigest()[:32]
    iv = encoded[:16]
    aes_obj = Crypto.Cipher.AES.new(key, Crypto.Cipher.AES.MODE_CFB, iv)
    return aes_obj.decrypt(encoded[16:])


def write_database(pd, password):
    """
    Serialize, encrypt and store object to file.
    """
    try:
        enc = [pd.keys(), encrypt(pickle.dumps(pd), password)]
        with open(DEFAULTPATH, 'wb') as output_file:
            pickle.dump(enc, output_file, -1)
        return True
    except:
        return False


def read_database(password):
    """
    Read, decrypt and deserialize object from file.
    """
    try:
        enc = pickle.load(open(DEFAULTPATH, 'rb'))[1]
        return pickle.loads(decrypt(enc, password))
    except:
        return False


def read_database_labels():
    """
    Read database labels from file.
    """
    try:
        return pickle.load(open(os.path.expanduser(DEFAULTPATH), 'rb'))[0]
    except:
        return False


def paste_to_clipboard(text, timeout=0):
    """
    Copy text to clipboard.
    """
    pyperclip.copy(text)
    if timeout:
        command = 'sleep {} && python -c "import pyperclip;pyperclip.copy(\'\');"'.format(timeout)
        subprocess.Popen(command, stdin=subprocess.PIPE, shell=True)


def random_password(length):
    """
    Generates a random password.
    """
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz01234567890-=!@#$%^&_+'
    return ''.join(random.sample(letters[:52], 1) + random.sample(letters, length - 2) +
                   random.sample(letters[:52], 1))


def paths_to_tree(subset):
    """
    Construct a tree structure from paths using defaultdict.
    """
    def tree():
        return collections.defaultdict(tree)

    def add(t, path):
        for node in path:
            t = t[node]

    t = tree()
    for path in subset:
        add(t, path.split('/'))
    return t


def print_tree(tree, indent=0):
    """
    Recursively print tree structure.
    """
    for k in sorted(tree):
        click.echo(indent * '|   ' + '|-- ' + k)
        print_tree(tree[k], indent=indent + 1)


def get_database():
    """
    Ask user for master password and read in database.
    """
    if os.path.isfile(DEFAULTPATH):
        master = click.prompt('Enter master password', hide_input=True)
        pd = read_database(master)
        if not isinstance(pd, dict):
            click.echo('Unable to decrypt database.')
            raise click.Abort()
        return pd, master
    else:
        click.echo('No password database found.\nUse the \'init\' command to initialize one.')
        raise click.Abort()


def get_labels():
    """
    Read labels from database.
    """
    if os.path.isfile(DEFAULTPATH):
        labels = read_database_labels()
        if not isinstance(labels, list):
            click.echo('Unable to decrypt database.')
            raise click.Abort()
        return labels
    else:
        click.echo('No password database found.\nUse the \'init\' command to initialize one.')
        raise click.Abort()


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def cli():
    """
    Encrypt and store passwords in a file.

    Use the 'init' command to initialize a password database, encrypted with a
    master password, the 'store' command to add a password, and the 'get'
    command to retrieve a password and copy to clipboard.

    Passwords can be printed out using the 'ls' command. Passwords are stored
    with a corresponding label. If this label contains forward slashes then
    the 'ls' command will print a directory structure.

    The database is encrypted using AES encryption (CFB mode) with a randomly
    generated IV and a key generated by SHA1 hashing the master password.
    """
    pass


@cli.command()
def init():
    """
    Initialize database.
    """
    if os.path.isfile(DEFAULTPATH):
        click.confirm('A password database already exists at "{}".\nDo you want to overwrite it?'
                      .format(DEFAULTPATH), abort=True)
    else:
        click.echo('A new password database will be created.')

    password = click.prompt('Enter new master password', hide_input=True, confirmation_prompt=True)
    if write_database(dict(), password):
        click.echo('Initialized new password database.')
    else:
        click.echo('Error: Unable to initialize new password database.')


@cli.command()
@click.argument('label')
@click.option('--generate', '-g', default=0, help='Generate a random password of given length.')
def store(label, generate):
    """
    Add or update an entry.

    LABEL is the path-like tag for the password.

    This command will prompt for the entry's password.
    """
    labels = get_labels()
    if label in labels:
        click.confirm('Entry already exists. Update?', abort=True)
    pd, master = get_database()
    if generate:
        password = random_password(generate)
        paste_to_clipboard(password, timeout=45)
        click.echo('Password generated and copied to clipboard.\n'
                   'The clipboard will clear in 45 seconds.')
    else:
        password = click.prompt('Enter password for entry', hide_input=True,
                                confirmation_prompt=True)
    pd[label] = password
    click.echo('Stored label and password.')
    if not write_database(pd, master):
        click.echo('Error: Unable to encrypt database to file.')


@cli.command()
@click.argument('label')
@click.option('--clipboard/--no-clipboard', default=True,
              help='Whether to paste to clipboard or print to terminal.')
def get(label, clipboard):
    """
    Retrieve password from database.

    LABEL is the path-like tag for the password.

    The retrieved password will be copied to the clipboard unless otherwise
    specified.
    """
    labels = get_labels()
    subset = [k for k in labels if not label or k.startswith(label)]
    if len(subset) == 1:
        label = subset[0]
    if label in labels:
        pd, master = get_database()
        if clipboard:
            paste_to_clipboard(pd[label], timeout=45)
            click.echo('Password copied to clipboard.\nThe clipboard will clear in 45 seconds.')
        else:
            click.echo('The password is: {}'.format(pd[label]))
    elif subset:
        click.echo('More than one entry.')
    else:
        click.echo('Entry does not exist.')


@cli.command()
@click.argument('label', required=False)
@click.option('--flat', '-f', is_flag=True, default=False)
def ls(label, flat):
    """
    List stored entries.

    LABEL is the path-like tag for the password.
    """
    labels = get_labels()
    subset = [k for k in labels if not label or k.startswith(label)]
    if subset:
        click.echo('Password Database')
        if flat:
            click.echo('\n'.join(sorted(subset)))
        else:
            print_tree(paths_to_tree(subset))
    elif label:
        click.echo('No entries starting with "{}".'.format(label))
    else:
        click.echo('No entries to show.')


@cli.command()
@click.argument('label')
def rm(label):
    """
    Remove stored entries.

    LABEL is the path-like tag for the password.
    """
    labels = get_labels()
    subset = [k for k in sorted(labels) if k.startswith(label)]
    if len(subset) > 0:
        entries = '\n '.join(k for k in subset)
        click.confirm('Are you sure you want to delete the following entries?\n {}\n'
                      .format(entries), abort=True)
        pd, master = get_database()
        for k in subset:
            del pd[k]
        click.echo('Removed {} entries.'.format(len(subset)))
        if not write_database(pd, master):
            click.echo('Error: Unable to encrypt database to file.')
    else:
        click.echo('No entries starting with "{}".'.format(label))


@cli.command()
@click.argument('old-label')
@click.argument('new-label')
def mv(old_label, new_label):
    """
    Rename a password label.
    """
    labels = get_labels()
    if old_label in labels:
        click.confirm('Are you sure you want to rename "{}" to "{}"?'
                      .format(old_label, new_label), abort=True)
        pd, master = get_database()
        pd[new_label] = pd[old_label]
        del pd[old_label]
        click.echo('Renamed entry.')
        if not write_database(pd, master):
            click.echo('Error: Unable to encrypt database to file.')
    elif new_label in labels:
        click.echo('Entry already exists.')
    else:
        click.echo('Entry does not exist.')


@cli.command(name='set-key')
def set_key():
    """
    Update master password.
    """
    pd, master = get_database()
    password = click.prompt('Enter new master password for database', type=str, hide_input=True,
                            confirmation_prompt=True)
    if write_database(pd, password):
        click.echo('Successfully changed master password.')
    else:
        click.echo('Error: Unable to change master password.')


@cli.command()
@click.argument('filename', type=click.Path(exists=True))
@click.option('--overwrite', '-w', is_flag=True)
def load(filename, overwrite):
    """
    Load password database from a JSON file.
    """
    if overwrite and not click.confirm('This will overwrite the current password database!'
                                       '\nDo you wish to continue?'):
        raise click.Abort()
    with open(filename, 'r') as f:
        data = json.load(f)
    pd, master = get_database()
    if overwrite:
        pd = data
    else:
        for entry in data:
            if (entry in pd and click.confirm('Entry "{}" exists. Update?'.format(entry))) \
               or (entry not in pd):
                pd[entry] = data[entry]
    if write_database(pd, master):
        click.echo('Password database updated.')
    else:
        click.echo('Error: Unable to encrypt database to file.')


@cli.command()
@click.option('--filename', '-f', type=click.Path(), default='storepass.json')
def dump(filename):
    """
    Dump passwords to a JSON file.
    """
    if not click.confirm('This operation will dump all passwords unencrypted!'
                         '\nDo you wish to continue?'):
        raise click.Abort()
    pd, master = get_database()
    with open(filename, 'w') as f:
        json.dump(pd, f, indent=4, sorted=True)
    click.echo('Password database dumped to {}'.format(filename))


if __name__ == '__main__':
    cli()
